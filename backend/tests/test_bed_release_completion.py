from datetime import date, datetime, timezone
from pathlib import Path
from queue import Queue
from threading import Barrier, Thread
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.dml import Update

from app.api.dependencies.database import get_db
from app.db.base import Base
from app.main import app
from app.models import (
    Admission,
    AdmissionStatus,
    Bed,
    BedStatus,
    Patient,
    User,
    UserRole,
    WorkflowEvent,
)
from app.services.bed_query_service import BedQueryService
from app.services.bed_release_service import BedReleaseService


@pytest.fixture
def completion_case(db_session):
    def build(
        *,
        bed_status=BedStatus.VACATING,
        admission_status=AdmissionStatus.DISCHARGING,
        current_patient=True,
        admission_patient_matches=True,
        admission_bed_matches=True,
    ):
        suffix = uuid4().hex
        ward_admin = User(
            name="Ward Admin",
            email=f"completion-admin-{suffix}@example.test",
            role=UserRole.WARD_ADMIN,
        )
        doctor = User(
            name="Dr. Completion",
            email=f"completion-doctor-{suffix}@example.test",
            role=UserRole.DOCTOR,
        )
        receiving_admin = User(
            name="Receiving Admin",
            email=f"completion-receiving-{suffix}@example.test",
            role=UserRole.RECEIVING_ADMIN,
        )
        patient = Patient(
            patient_code=f"COMP-{suffix}",
            first_name="Completion",
            last_name="Patient",
            date_of_birth=date(1980, 3, 4),
            gender="Female",
        )
        other_patient = Patient(
            patient_code=f"COMP-OTHER-{suffix}",
            first_name="Other",
            last_name="Patient",
            date_of_birth=date(1981, 5, 6),
            gender="Male",
        )
        bed = Bed(ward="General Medicine", bed_number=f"COMP-{suffix}", status=bed_status)
        other_bed = Bed(
            ward="General Medicine",
            bed_number=f"COMP-OTHER-{suffix}",
            status=BedStatus.OCCUPIED,
        )
        db_session.add_all(
            [ward_admin, doctor, receiving_admin, patient, other_patient, bed, other_bed]
        )
        db_session.flush()
        if current_patient:
            bed.current_patient_id = patient.id
        admission = Admission(
            patient_id=patient.id if admission_patient_matches else other_patient.id,
            admission_date=datetime(2026, 8, 10, tzinfo=timezone.utc),
            primary_diagnosis="Pneumonia",
            attending_doctor_id=doctor.id,
            status=admission_status,
            bed_id=bed.id if admission_bed_matches else other_bed.id,
        )
        db_session.add(admission)
        db_session.flush()
        return {
            "bed": bed,
            "admission": admission,
            "patient": patient,
            "ward_admin": ward_admin,
            "doctor": doctor,
            "receiving_admin": receiving_admin,
        }

    return build


def _bed_events(db, bed_id):
    return (
        db.query(WorkflowEvent)
        .filter(
            WorkflowEvent.entity_type == "bed",
            WorkflowEvent.entity_id == bed_id,
        )
        .order_by(WorkflowEvent.id)
        .all()
    )


def test_patient_departed_atomically_clears_assignment_and_discharges_admission(
    db_session, completion_case,
):
    """Leaving assignment present or admission discharging must fail."""
    case = completion_case()

    cleaning = BedReleaseService(db_session).patient_departed(
        case["bed"].id, case["ward_admin"]
    )

    db_session.refresh(case["admission"])
    assert cleaning.status is BedStatus.CLEANING
    assert cleaning.current_patient_id is None
    assert case["admission"].status is AdmissionStatus.DISCHARGED
    assert case["admission"].bed_id == case["bed"].id
    assert [event.event_type for event in _bed_events(
        db_session, case["bed"].id,
    )] == ["patient_departed_bed", "bed_cleaning_started"]


def test_patient_departed_events_retain_departing_context_and_exact_payload(
    db_session, completion_case,
):
    """Dropping the cleared patient's identity or actor context must fail."""
    case = completion_case()

    BedReleaseService(db_session).patient_departed(case["bed"].id, case["doctor"])

    events = _bed_events(db_session, case["bed"].id)
    assert len(events) == 2
    for event in events:
        assert event.status == "pending"
        assert set(event.payload) == {
            "bed_id",
            "patient_id",
            "admission_id",
            "previous_status",
            "new_status",
            "timestamp",
            "actor_user_id",
            "actor_name",
            "actor_role",
        }
        assert event.payload | {"timestamp": "ignored"} == {
            "bed_id": case["bed"].id,
            "patient_id": case["patient"].id,
            "admission_id": case["admission"].id,
            "previous_status": "vacating",
            "new_status": "cleaning",
            "timestamp": "ignored",
            "actor_user_id": case["doctor"].id,
            "actor_name": "Dr. Completion",
            "actor_role": "doctor",
        }
        assert datetime.fromisoformat(event.payload["timestamp"]).tzinfo is not None


def test_cleaning_complete_makes_the_unassigned_bed_available(db_session, completion_case):
    """Reassigning the bed or leaving it cleaning must fail."""
    case = completion_case(
        bed_status=BedStatus.CLEANING,
        admission_status=AdmissionStatus.DISCHARGED,
        current_patient=False,
    )

    available = BedReleaseService(db_session).cleaning_complete(
        case["bed"].id, case["ward_admin"]
    )

    assert available.status is BedStatus.AVAILABLE
    assert available.current_patient_id is None
    db_session.refresh(case["admission"])
    assert case["admission"].status is AdmissionStatus.DISCHARGED
    assert case["admission"].bed_id == case["bed"].id
    events = _bed_events(db_session, case["bed"].id)
    assert [event.event_type for event in events] == ["bed_available"]
    assert len(events) == 1
    assert events[0].payload | {"timestamp": "ignored"} == {
        "bed_id": case["bed"].id,
        "patient_id": case["patient"].id,
        "admission_id": case["admission"].id,
        "previous_status": "cleaning",
        "new_status": "available",
        "timestamp": "ignored",
        "actor_user_id": case["ward_admin"].id,
        "actor_name": "Ward Admin",
        "actor_role": "ward_admin",
    }


def test_completion_routes_return_precommit_operational_details(client, completion_case):
    """Returning stale ownership or omitting transition history must fail."""
    departure = completion_case()
    response = client.post(
        f"/api/beds/{departure['bed'].id}/patient-departed",
        headers={"X-User-Id": str(departure["ward_admin"].id)},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cleaning"
    assert response.json()["current_patient_id"] is None
    assert response.json()["admission_id"] == departure["admission"].id
    assert response.json()["admission_status"] == "discharged"
    assert [item["event_type"] for item in response.json()["transition_history"][:2]] == [
        "bed_cleaning_started",
        "patient_departed_bed",
    ]

    cleaning = completion_case(
        bed_status=BedStatus.CLEANING,
        admission_status=AdmissionStatus.DISCHARGED,
        current_patient=False,
    )
    response = client.post(
        f"/api/beds/{cleaning['bed'].id}/cleaning-complete",
        headers={"X-User-Id": str(cleaning["ward_admin"].id)},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "available"
    assert response.json()["current_patient_id"] is None
    assert response.json()["admission_id"] == cleaning["admission"].id
    assert response.json()["transition_history"][0]["event_type"] == "bed_available"


@pytest.mark.parametrize(
    ("method", "case_options"),
    [
        ("patient_departed", {"bed_status": BedStatus.OCCUPIED}),
        (
            "cleaning_complete",
            {"bed_status": BedStatus.VACATING, "admission_status": AdmissionStatus.DISCHARGING},
        ),
    ],
)
def test_completion_rejects_forbidden_transition_shortcuts(
    db_session, completion_case, method, case_options,
):
    """Allowing occupied-to-cleaning or vacating-to-available must fail."""
    case = completion_case(**case_options)

    with pytest.raises(HTTPException) as error:
        getattr(BedReleaseService(db_session), method)(case["bed"].id, case["ward_admin"])

    assert error.value.status_code == 409
    assert _bed_events(db_session, case["bed"].id) == []


@pytest.mark.parametrize("method", ["patient_departed", "cleaning_complete"])
def test_completion_repeats_are_conflicts_without_duplicate_events(
    isolated_completion_db_path, method,
):
    """Treating completion as idempotent and duplicating audit records must fail."""
    if method == "patient_departed":
        initial_status = BedStatus.VACATING
        expected_types = ("patient_departed_bed", "bed_cleaning_started")
    else:
        initial_status = BedStatus.CLEANING
        expected_types = ("bed_available",)
    engine, SessionLocal, (bed_id, actor_id, _, _) = _committed_completion_case(
        isolated_completion_db_path, bed_status=initial_status
    )
    first = SessionLocal()
    repeated = SessionLocal()
    try:
        getattr(BedReleaseService(first), method)(bed_id, first.get(User, actor_id))
        with pytest.raises(HTTPException) as error:
            getattr(BedReleaseService(repeated), method)(
                bed_id, repeated.get(User, actor_id)
            )
        assert error.value.status_code == 409
    finally:
        first.close()
        repeated.close()

    verifier = SessionLocal()
    try:
        assert [event.event_type for event in _bed_events(verifier, bed_id)] == list(
            expected_types
        )
    finally:
        verifier.close()
        engine.dispose()


@pytest.mark.parametrize(
    "case_options",
    [
        {"current_patient": False},
        {"admission_patient_matches": False},
        {"admission_bed_matches": False},
        {"admission_status": AdmissionStatus.ADMITTED},
    ],
)
def test_patient_departed_rejects_inconsistent_ownership(
    db_session, completion_case, case_options,
):
    """Discharging another patient/admission or an unassigned bed must fail."""
    case = completion_case(**case_options)

    with pytest.raises(HTTPException) as error:
        BedReleaseService(db_session).patient_departed(case["bed"].id, case["ward_admin"])

    assert error.value.status_code == 409
    assert _bed_events(db_session, case["bed"].id) == []


def test_cleaning_complete_rejects_a_cleaning_bed_with_a_patient(db_session, completion_case):
    """Making an assigned cleaning bed available must fail."""
    case = completion_case(
        bed_status=BedStatus.CLEANING,
        admission_status=AdmissionStatus.DISCHARGED,
    )

    with pytest.raises(HTTPException) as error:
        BedReleaseService(db_session).cleaning_complete(case["bed"].id, case["ward_admin"])

    assert error.value.status_code == 409
    assert _bed_events(db_session, case["bed"].id) == []


@pytest.mark.parametrize("method", ["patient_departed", "cleaning_complete"])
def test_completion_service_defensively_rejects_disallowed_roles(
    db_session, completion_case, method,
):
    """Direct service calls must not bypass operational role checks."""
    options = {}
    if method == "cleaning_complete":
        options = {
            "bed_status": BedStatus.CLEANING,
            "admission_status": AdmissionStatus.DISCHARGED,
            "current_patient": False,
        }
    case = completion_case(**options)

    with pytest.raises(HTTPException) as error:
        getattr(BedReleaseService(db_session), method)(
            case["bed"].id, case["receiving_admin"]
        )

    assert error.value.status_code == 403


@pytest.mark.parametrize("route", ["patient-departed", "cleaning-complete"])
def test_completion_routes_reject_disallowed_roles(client, completion_case, route):
    """HTTP routes must independently reject receiving administrators."""
    options = {}
    if route == "cleaning-complete":
        options = {
            "bed_status": BedStatus.CLEANING,
            "admission_status": AdmissionStatus.DISCHARGED,
            "current_patient": False,
        }
    case = completion_case(**options)

    response = client.post(
        f"/api/beds/{case['bed'].id}/{route}",
        headers={"X-User-Id": str(case["receiving_admin"].id)},
    )

    assert response.status_code == 403


@pytest.mark.parametrize("method", ["patient_departed", "cleaning_complete"])
def test_completion_returns_not_found_for_missing_beds(db_session, completion_case, method):
    """Turning a missing target into a generic conflict must fail."""
    case = completion_case()

    with pytest.raises(HTTPException) as error:
        getattr(BedReleaseService(db_session), method)(999999, case["ward_admin"])

    assert error.value.status_code == 404


def test_unrestricted_status_patch_route_is_removed(client, completion_case):
    """A generic status mutation that bypasses the state machine must stay unavailable."""
    case = completion_case()

    response = client.patch(
        f"/api/beds/{case['bed'].id}/status",
        json={"status": "available"},
    )

    assert response.status_code in {404, 405}


@pytest.fixture
def isolated_completion_db_path():
    path = Path(__file__).parent / f".bed-completion-{uuid4()}.db"
    yield path
    if path.exists():
        path.unlink()


def _committed_completion_case(db_path, *, bed_status=BedStatus.VACATING):
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    suffix = uuid4().hex
    actor = User(
        name="Ward Admin",
        email=f"isolated-completion-{suffix}@example.test",
        role=UserRole.WARD_ADMIN,
    )
    patient = Patient(
        patient_code=f"ISO-COMP-{suffix}",
        first_name="Isolated",
        last_name="Patient",
        date_of_birth=date(1982, 7, 8),
        gender="Female",
    )
    bed = Bed(ward="General Medicine", bed_number=f"ISO-COMP-{suffix}", status=bed_status)
    session.add_all([actor, patient, bed])
    session.flush()
    if bed_status == BedStatus.VACATING:
        bed.current_patient_id = patient.id
    admission = Admission(
        patient_id=patient.id,
        admission_date=datetime(2026, 8, 10, tzinfo=timezone.utc),
        primary_diagnosis="Pneumonia",
        attending_doctor_id=actor.id,
        status=(
            AdmissionStatus.DISCHARGING
            if bed_status == BedStatus.VACATING
            else AdmissionStatus.DISCHARGED
        ),
        bed_id=bed.id,
    )
    session.add(admission)
    session.commit()
    ids = bed.id, actor.id, admission.id, patient.id
    session.close()
    return engine, SessionLocal, ids


def test_patient_departed_success_persists_the_full_tuple_for_a_fresh_session(
    isolated_completion_db_path,
):
    """Returning success before the complete departure transaction commits must fail."""
    engine, SessionLocal, (bed_id, actor_id, admission_id, _) = _committed_completion_case(
        isolated_completion_db_path
    )
    request_session = SessionLocal()
    try:
        BedReleaseService(request_session).patient_departed(
            bed_id, request_session.get(User, actor_id)
        )
    finally:
        request_session.close()

    verifier = SessionLocal()
    try:
        bed = verifier.get(Bed, bed_id)
        admission = verifier.get(Admission, admission_id)
        assert bed.status is BedStatus.CLEANING
        assert bed.current_patient_id is None
        assert admission.status is AdmissionStatus.DISCHARGED
        assert admission.bed_id == bed_id
        assert [event.event_type for event in _bed_events(verifier, bed_id)] == [
            "patient_departed_bed",
            "bed_cleaning_started",
        ]
    finally:
        verifier.close()
        engine.dispose()


def test_cleaning_complete_success_persists_the_full_tuple_for_a_fresh_session(
    isolated_completion_db_path,
):
    """Returning success before the available-bed transaction commits must fail."""
    engine, SessionLocal, (bed_id, actor_id, admission_id, _) = _committed_completion_case(
        isolated_completion_db_path, bed_status=BedStatus.CLEANING
    )
    request_session = SessionLocal()
    try:
        BedReleaseService(request_session).cleaning_complete(
            bed_id, request_session.get(User, actor_id)
        )
    finally:
        request_session.close()

    verifier = SessionLocal()
    try:
        bed = verifier.get(Bed, bed_id)
        admission = verifier.get(Admission, admission_id)
        assert bed.status is BedStatus.AVAILABLE
        assert bed.current_patient_id is None
        assert admission.status is AdmissionStatus.DISCHARGED
        assert admission.bed_id == bed_id
        assert [event.event_type for event in _bed_events(verifier, bed_id)] == [
            "bed_available"
        ]
    finally:
        verifier.close()
        engine.dispose()


@pytest.mark.parametrize("losing_table", ["beds", "admissions"])
def test_patient_departed_conditional_loser_rolls_back_every_change(
    isolated_completion_db_path, monkeypatch, losing_table,
):
    """Either lost compare-and-swap must leave bed, admission, and events unchanged."""
    engine, SessionLocal, (bed_id, actor_id, admission_id, _) = _committed_completion_case(
        isolated_completion_db_path
    )
    session = SessionLocal()
    original_execute = session.execute

    def lose_update(statement, *args, **kwargs):
        if isinstance(statement, Update) and statement.table.name == losing_table:
            return SimpleNamespace(rowcount=0)
        return original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(session, "execute", lose_update)
    try:
        with pytest.raises(HTTPException) as error:
            BedReleaseService(session).patient_departed(
                bed_id, session.get(User, actor_id)
            )
        assert error.value.status_code == 409
    finally:
        session.close()

    verifier = SessionLocal()
    try:
        assert verifier.get(Bed, bed_id).status is BedStatus.VACATING
        assert verifier.get(Bed, bed_id).current_patient_id is not None
        assert verifier.get(Admission, admission_id).status is AdmissionStatus.DISCHARGING
        assert _bed_events(verifier, bed_id) == []
    finally:
        verifier.close()
        engine.dispose()


def test_cleaning_complete_conditional_loser_rolls_back_event(
    isolated_completion_db_path, monkeypatch,
):
    """A lost cleaning compare-and-swap must not make the bed available or emit an event."""
    engine, SessionLocal, (bed_id, actor_id, _, _) = _committed_completion_case(
        isolated_completion_db_path, bed_status=BedStatus.CLEANING
    )
    session = SessionLocal()
    original_execute = session.execute

    def lose_bed_update(statement, *args, **kwargs):
        if isinstance(statement, Update) and statement.table.name == "beds":
            return SimpleNamespace(rowcount=0)
        return original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(session, "execute", lose_bed_update)
    try:
        with pytest.raises(HTTPException) as error:
            BedReleaseService(session).cleaning_complete(
                bed_id, session.get(User, actor_id)
            )
        assert error.value.status_code == 409
    finally:
        session.close()

    verifier = SessionLocal()
    try:
        assert verifier.get(Bed, bed_id).status is BedStatus.CLEANING
        assert _bed_events(verifier, bed_id) == []
    finally:
        verifier.close()
        engine.dispose()


def test_stale_departure_session_rechecks_and_conflicts_without_duplicate_events(
    isolated_completion_db_path,
):
    """A session caching vacating state must not complete departure twice."""
    engine, SessionLocal, (bed_id, actor_id, _, _) = _committed_completion_case(
        isolated_completion_db_path
    )
    winner = SessionLocal()
    stale = SessionLocal()
    try:
        assert stale.get(Bed, bed_id).status is BedStatus.VACATING
        BedReleaseService(winner).patient_departed(bed_id, winner.get(User, actor_id))
        with pytest.raises(HTTPException) as error:
            BedReleaseService(stale).patient_departed(bed_id, stale.get(User, actor_id))
        assert error.value.status_code == 409
    finally:
        winner.close()
        stale.close()

    verifier = SessionLocal()
    try:
        assert verifier.get(Bed, bed_id).status is BedStatus.CLEANING
        assert [event.event_type for event in _bed_events(verifier, bed_id)] == [
            "patient_departed_bed",
            "bed_cleaning_started",
        ]
    finally:
        verifier.close()
        engine.dispose()


def test_stale_cleaning_session_rechecks_and_conflicts_without_duplicate_events(
    isolated_completion_db_path,
):
    """A session caching cleaning state must not complete cleaning twice."""
    engine, SessionLocal, (bed_id, actor_id, admission_id, _) = _committed_completion_case(
        isolated_completion_db_path, bed_status=BedStatus.CLEANING
    )
    winner = SessionLocal()
    stale = SessionLocal()
    try:
        assert stale.get(Bed, bed_id).status is BedStatus.CLEANING
        BedReleaseService(winner).cleaning_complete(bed_id, winner.get(User, actor_id))
        with pytest.raises(HTTPException) as error:
            BedReleaseService(stale).cleaning_complete(bed_id, stale.get(User, actor_id))
        assert error.value.status_code == 409
    finally:
        winner.close()
        stale.close()

    verifier = SessionLocal()
    try:
        bed = verifier.get(Bed, bed_id)
        admission = verifier.get(Admission, admission_id)
        assert bed.status is BedStatus.AVAILABLE
        assert bed.current_patient_id is None
        assert admission.status is AdmissionStatus.DISCHARGED
        assert admission.bed_id == bed_id
        assert [event.event_type for event in _bed_events(verifier, bed_id)] == [
            "bed_available"
        ]
    finally:
        verifier.close()
        engine.dispose()


def test_two_session_departure_race_has_one_winner_and_one_controlled_conflict(
    isolated_completion_db_path,
):
    """Concurrent departure reads must still produce one atomic transition."""
    engine, SessionLocal, (bed_id, actor_id, _, _) = _committed_completion_case(
        isolated_completion_db_path
    )
    update_barrier = Barrier(2)
    outcomes = Queue()

    def race_departure():
        session = SessionLocal()
        original_execute = session.execute

        def synchronize_update(statement, *args, **kwargs):
            if isinstance(statement, Update) and statement.table.name == "beds":
                update_barrier.wait(timeout=5)
            return original_execute(statement, *args, **kwargs)

        session.execute = synchronize_update
        try:
            result = BedReleaseService(session).patient_departed(
                bed_id, session.get(User, actor_id)
            )
            outcomes.put(("ok", result.status.value))
        except HTTPException as error:
            outcomes.put(("http", error.status_code))
        except Exception as error:
            outcomes.put(("error", type(error).__name__))
        finally:
            session.close()

    threads = [Thread(target=race_departure), Thread(target=race_departure)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    verifier = SessionLocal()
    try:
        assert all(not thread.is_alive() for thread in threads)
        assert sorted([outcomes.get_nowait(), outcomes.get_nowait()]) == [
            ("http", 409),
            ("ok", "cleaning"),
        ]
        assert verifier.get(Bed, bed_id).status is BedStatus.CLEANING
        assert [event.event_type for event in _bed_events(verifier, bed_id)] == [
            "patient_departed_bed",
            "bed_cleaning_started",
        ]
    finally:
        verifier.close()
        engine.dispose()


def test_two_session_cleaning_race_has_one_winner_and_one_controlled_conflict(
    isolated_completion_db_path,
):
    """Concurrent cleaning reads must still produce one durable transition."""
    engine, SessionLocal, (bed_id, actor_id, admission_id, _) = _committed_completion_case(
        isolated_completion_db_path, bed_status=BedStatus.CLEANING
    )
    update_barrier = Barrier(2)
    outcomes = Queue()

    def race_cleaning():
        session = SessionLocal()
        original_execute = session.execute

        def synchronize_update(statement, *args, **kwargs):
            if isinstance(statement, Update) and statement.table.name == "beds":
                update_barrier.wait(timeout=5)
            return original_execute(statement, *args, **kwargs)

        session.execute = synchronize_update
        try:
            result = BedReleaseService(session).cleaning_complete(
                bed_id, session.get(User, actor_id)
            )
            outcomes.put(("ok", result.status.value))
        except HTTPException as error:
            outcomes.put(("http", error.status_code))
        except Exception as error:
            outcomes.put(("error", type(error).__name__))
        finally:
            session.close()

    threads = [Thread(target=race_cleaning), Thread(target=race_cleaning)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    verifier = SessionLocal()
    try:
        assert all(not thread.is_alive() for thread in threads)
        assert sorted([outcomes.get_nowait(), outcomes.get_nowait()]) == [
            ("http", 409),
            ("ok", "available"),
        ]
        bed = verifier.get(Bed, bed_id)
        admission = verifier.get(Admission, admission_id)
        assert bed.status is BedStatus.AVAILABLE
        assert bed.current_patient_id is None
        assert admission.status is AdmissionStatus.DISCHARGED
        assert admission.bed_id == bed_id
        assert [event.event_type for event in _bed_events(verifier, bed_id)] == [
            "bed_available"
        ]
    finally:
        verifier.close()
        engine.dispose()


@pytest.mark.parametrize("failure", ["event", "refresh", "commit"])
def test_patient_departed_rolls_back_all_state_on_persistence_failure(
    isolated_completion_db_path, monkeypatch, failure,
):
    """Event, refresh, or commit failure must preserve the fresh-session vacating state."""
    engine, SessionLocal, (bed_id, actor_id, admission_id, patient_id) = (
        _committed_completion_case(isolated_completion_db_path)
    )
    session = SessionLocal()
    original_flush = session.flush

    if failure == "event":
        def fail_event_flush(*args, **kwargs):
            if any(
                isinstance(item, WorkflowEvent)
                and item.event_type == "patient_departed_bed"
                for item in session.new
            ):
                raise SQLAlchemyError("departure event flush failed")
            return original_flush(*args, **kwargs)

        monkeypatch.setattr(session, "flush", fail_event_flush)
    elif failure == "refresh":
        monkeypatch.setattr(
            session,
            "refresh",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                SQLAlchemyError("departure refresh failed")
            ),
        )
    else:
        monkeypatch.setattr(
            session,
            "commit",
            lambda: (_ for _ in ()).throw(SQLAlchemyError("departure commit failed")),
        )

    try:
        with pytest.raises(SQLAlchemyError):
            BedReleaseService(session).patient_departed(
                bed_id, session.get(User, actor_id)
            )
    finally:
        session.close()

    verifier = SessionLocal()
    try:
        bed = verifier.get(Bed, bed_id)
        assert bed.status is BedStatus.VACATING
        assert bed.current_patient_id == patient_id
        assert verifier.get(Admission, admission_id).status is AdmissionStatus.DISCHARGING
        assert _bed_events(verifier, bed_id) == []
    finally:
        verifier.close()
        engine.dispose()


@pytest.mark.parametrize("failure", ["event", "refresh", "commit"])
def test_cleaning_complete_rolls_back_all_state_on_persistence_failure(
    isolated_completion_db_path, monkeypatch, failure,
):
    """Event, refresh, or commit failure must preserve fresh-session cleaning state."""
    engine, SessionLocal, (bed_id, actor_id, admission_id, _) = (
        _committed_completion_case(
            isolated_completion_db_path, bed_status=BedStatus.CLEANING
        )
    )
    session = SessionLocal()
    original_flush = session.flush

    if failure == "event":
        def fail_event_flush(*args, **kwargs):
            if any(
                isinstance(item, WorkflowEvent) and item.event_type == "bed_available"
                for item in session.new
            ):
                raise SQLAlchemyError("available event flush failed")
            return original_flush(*args, **kwargs)

        monkeypatch.setattr(session, "flush", fail_event_flush)
    elif failure == "refresh":
        monkeypatch.setattr(
            session,
            "refresh",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                SQLAlchemyError("cleaning refresh failed")
            ),
        )
    else:
        monkeypatch.setattr(
            session,
            "commit",
            lambda: (_ for _ in ()).throw(SQLAlchemyError("cleaning commit failed")),
        )

    try:
        with pytest.raises(SQLAlchemyError):
            BedReleaseService(session).cleaning_complete(
                bed_id, session.get(User, actor_id)
            )
    finally:
        session.close()

    verifier = SessionLocal()
    try:
        bed = verifier.get(Bed, bed_id)
        admission = verifier.get(Admission, admission_id)
        assert bed.status is BedStatus.CLEANING
        assert bed.current_patient_id is None
        assert admission.status is AdmissionStatus.DISCHARGED
        assert admission.bed_id == bed_id
        assert _bed_events(verifier, bed_id) == []
    finally:
        verifier.close()
        engine.dispose()


def test_departure_detail_failure_occurs_before_commit_and_rolls_back(
    isolated_completion_db_path, monkeypatch,
):
    """A response snapshot failure must not leave a durable departure transition."""
    engine, SessionLocal, (bed_id, actor_id, admission_id, patient_id) = (
        _committed_completion_case(isolated_completion_db_path)
    )
    request_session = SessionLocal()

    def override_get_db():
        yield request_session

    monkeypatch.setattr(
        BedQueryService,
        "get_bed",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            SQLAlchemyError("departure detail failed")
        ),
    )
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as isolated_client:
            response = isolated_client.post(
                f"/api/beds/{bed_id}/patient-departed",
                headers={"X-User-Id": str(actor_id)},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    verifier = SessionLocal()
    try:
        assert response.status_code == 500
        assert response.json()["error"]["message"] == "Unable to confirm patient departure"
        bed = verifier.get(Bed, bed_id)
        assert bed.status is BedStatus.VACATING
        assert bed.current_patient_id == patient_id
        assert verifier.get(Admission, admission_id).status is AdmissionStatus.DISCHARGING
        assert _bed_events(verifier, bed_id) == []
    finally:
        request_session.close()
        verifier.close()
        engine.dispose()


def test_cleaning_detail_failure_occurs_before_commit_and_rolls_back(
    isolated_completion_db_path, monkeypatch,
):
    """A failed available-bed snapshot must keep cleaning state durable."""
    engine, SessionLocal, (bed_id, actor_id, admission_id, _) = _committed_completion_case(
        isolated_completion_db_path, bed_status=BedStatus.CLEANING
    )
    request_session = SessionLocal()

    def override_get_db():
        yield request_session

    monkeypatch.setattr(
        BedQueryService,
        "get_bed",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            SQLAlchemyError("cleaning detail failed")
        ),
    )
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as isolated_client:
            response = isolated_client.post(
                f"/api/beds/{bed_id}/cleaning-complete",
                headers={"X-User-Id": str(actor_id)},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    verifier = SessionLocal()
    try:
        assert response.status_code == 500
        assert response.json()["error"]["message"] == "Unable to complete bed cleaning"
        bed = verifier.get(Bed, bed_id)
        admission = verifier.get(Admission, admission_id)
        assert bed.status is BedStatus.CLEANING
        assert bed.current_patient_id is None
        assert admission.status is AdmissionStatus.DISCHARGED
        assert admission.bed_id == bed_id
        assert _bed_events(verifier, bed_id) == []
    finally:
        request_session.close()
        verifier.close()
        engine.dispose()
