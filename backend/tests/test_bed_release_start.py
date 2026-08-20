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

from app.api.dependencies.auth import get_current_user_stub
from app.api.dependencies.database import get_db
from app.db.base import Base
from app.main import app
from app.models import (
    Admission,
    AdmissionStatus,
    Bed,
    BedStatus,
    DischargeReport,
    DischargeReportStatus,
    Patient,
    User,
    UserRole,
    WorkflowEvent,
)
from app.services.bed_release_service import BedReleaseService
from app.services.bed_query_service import BedQueryService


@pytest.fixture
def release_case(db_session):
    def build(
        *,
        bed_status=BedStatus.OCCUPIED,
        admission_status=AdmissionStatus.DISCHARGING,
        report_status=DischargeReportStatus.APPROVED,
        current_patient=True,
        admission_patient_matches=True,
        admission_bed_matches=True,
        approval_event=True,
        approval_trusted=True,
        approval_entity_type="discharge_report",
        approval_entity_id=None,
        report_exists=True,
    ):
        suffix = uuid4().hex
        ward_admin = User(
            name="Ward Admin", email=f"ward-admin-{suffix}@example.test", role=UserRole.WARD_ADMIN,
        )
        doctor = User(name="Dr. Release", email=f"doctor-{suffix}@example.test", role=UserRole.DOCTOR)
        receiving_admin = User(
            name="Receiving Admin",
            email=f"receiving-admin-{suffix}@example.test",
            role=UserRole.RECEIVING_ADMIN,
        )
        patient = Patient(
            patient_code=f"REL-{suffix}", first_name="Release", last_name="Patient",
            date_of_birth=date(1985, 2, 3), gender="Female", blood_group="O+",
        )
        other_patient = Patient(
            patient_code=f"OTHER-{suffix}", first_name="Other", last_name="Patient",
            date_of_birth=date(1990, 4, 5), gender="Male", blood_group="A+",
        )
        bed = Bed(ward="General Medicine", bed_number=f"REL-{suffix}", status=bed_status)
        other_bed = Bed(ward="General Medicine", bed_number=f"OTHER-{suffix}", status=BedStatus.OCCUPIED)
        db_session.add_all([ward_admin, doctor, receiving_admin, patient, other_patient, bed, other_bed])
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
        report = None
        if report_exists:
            report = DischargeReport(
                patient_id=admission.patient_id,
                admission_id=admission.id,
                generated_content="Approved discharge report",
                generation_provider="replicate",
                generation_model="openai/gpt-5.6-luna",
                status=report_status,
                approved_by=doctor.id if report_status == DischargeReportStatus.APPROVED else None,
                approved_at=(
                    datetime(2026, 8, 19, 8, tzinfo=timezone.utc)
                    if report_status == DischargeReportStatus.APPROVED else None
                ),
            )
            db_session.add(report)
            db_session.flush()
        if approval_event and report is not None:
            approval_time = report.approved_at or datetime(2026, 8, 19, 8, tzinfo=timezone.utc)
            db_session.add(WorkflowEvent(
                event_type="report_approved",
                entity_type=approval_entity_type,
                entity_id=report.id if approval_entity_id is None else approval_entity_id,
                status="pending",
                trusted_provenance=approval_trusted,
                payload={
                    "report_id": report.id,
                    "patient_id": report.patient_id,
                    "admission_id": report.admission_id,
                    "approved_by": report.approved_by,
                    "approved_at": approval_time.isoformat(),
                },
                created_at=approval_time,
            ))
        db_session.flush()
        return {
            "bed": bed,
            "admission": admission,
            "report": report,
            "patient": patient,
            "ward_admin": ward_admin,
            "doctor": doctor,
            "receiving_admin": receiving_admin,
        }

    return build


def _release_events(db, bed_id):
    return db.query(WorkflowEvent).filter_by(
        event_type="bed_release_started", entity_type="bed", entity_id=bed_id,
    ).all()


def _release_payload(case, **overrides):
    payload = {
        "bed_id": case["bed"].id,
        "patient_id": case["patient"].id,
        "admission_id": case["admission"].id,
        "report_id": case["report"].id,
        "previous_status": "occupied",
        "new_status": "vacating",
        "timestamp": datetime(2026, 8, 19, 9, tzinfo=timezone.utc).isoformat(),
        "actor_user_id": case["ward_admin"].id,
        "actor_name": case["ward_admin"].name,
        "actor_role": case["ward_admin"].role.value,
    }
    payload.update(overrides)
    return payload


def _add_release_event(db, case, *, trusted_provenance=True, **payload_overrides):
    payload = _release_payload(case, **payload_overrides)
    db.add(WorkflowEvent(
        event_type="bed_release_started",
        entity_type="bed",
        entity_id=case["bed"].id,
        status="pending",
        trusted_provenance=trusted_provenance,
        payload=payload,
        created_at=datetime.fromisoformat(payload["timestamp"]),
    ))
    db.flush()


def test_start_release_moves_only_the_bed_to_vacating(db_session, release_case):
    """Clearing assignment or discharging the admission at release start must fail."""
    case = release_case()

    result = BedReleaseService(db_session).start_release(case["bed"].id, case["ward_admin"])

    db_session.refresh(case["admission"])
    assert result.status is BedStatus.VACATING
    assert result.current_patient_id == case["patient"].id
    assert case["admission"].status is AdmissionStatus.DISCHARGING
    assert case["admission"].bed_id == case["bed"].id
    assert [event.event_type for event in _release_events(db_session, case["bed"].id)] == [
        "bed_release_started"
    ]


def test_start_release_writes_the_exact_internal_audit_payload(db_session, release_case):
    """Omitting actor or transition context from the audit event must fail."""
    case = release_case()

    BedReleaseService(db_session).start_release(case["bed"].id, case["doctor"])

    event = _release_events(db_session, case["bed"].id)[0]
    assert event.status == "pending"
    assert getattr(event, "trusted_provenance", None) is True
    assert set(event.payload) == {
        "bed_id",
        "patient_id",
        "admission_id",
        "report_id",
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
        "report_id": case["report"].id,
        "previous_status": "occupied",
        "new_status": "vacating",
        "timestamp": "ignored",
        "actor_user_id": case["doctor"].id,
        "actor_name": "Dr. Release",
        "actor_role": "doctor",
    }
    assert datetime.fromisoformat(event.payload["timestamp"]).tzinfo is not None


def test_start_release_rejects_an_unapproved_report(isolated_release_db_path):
    """Starting release from a generated clinical report must fail."""
    engine, SessionLocal, (bed_id, actor_id) = _committed_release_case(
        isolated_release_db_path, report_status=DischargeReportStatus.GENERATED,
    )
    session = SessionLocal()
    verifier = SessionLocal()
    try:
        with pytest.raises(HTTPException) as error:
            BedReleaseService(session).start_release(bed_id, session.get(User, actor_id))

        assert error.value.status_code == 409
        assert verifier.get(Bed, bed_id).status is BedStatus.OCCUPIED
        assert _release_events(verifier, bed_id) == []
    finally:
        session.close()
        verifier.close()
        engine.dispose()


def test_start_release_service_treats_a_missing_report_as_conflict(isolated_release_db_path):
    """Returning 404 for absent eligibility context must fail this contract."""
    engine, SessionLocal, (bed_id, actor_id) = _committed_release_case(
        isolated_release_db_path, report_exists=False,
    )
    session = SessionLocal()
    try:
        with pytest.raises(HTTPException) as error:
            BedReleaseService(session).start_release(bed_id, session.get(User, actor_id))

        assert error.value.status_code == 409
    finally:
        session.close()
        engine.dispose()


def test_start_release_endpoint_treats_a_missing_report_as_conflict(
    client, release_case,
):
    """The HTTP boundary must expose missing eligibility context as 409."""
    case = release_case(report_exists=False)

    response = client.post(
        f"/api/beds/{case['bed'].id}/start-release",
        headers={"X-User-Id": str(case["ward_admin"].id)},
    )

    assert response.status_code == 409


@pytest.mark.parametrize(
    "event_options",
    [
        {"approval_event": False},
        {"approval_trusted": False},
        {"approval_entity_type": "bed"},
        {"approval_entity_id": 999999},
    ],
)
def test_start_release_requires_the_matching_report_approval_event(
    db_session, release_case, event_options,
):
    """Missing or mismatched approval evidence must not authorize release."""
    case = release_case(**event_options)

    with pytest.raises(HTTPException) as error:
        BedReleaseService(db_session).start_release(case["bed"].id, case["ward_admin"])

    assert error.value.status_code == 409
    assert _release_events(db_session, case["bed"].id) == []


@pytest.mark.parametrize("bed_status", [BedStatus.AVAILABLE, BedStatus.CLEANING])
def test_start_release_rejects_beds_outside_the_occupied_state(db_session, release_case, bed_status):
    """Skipping normal turnover by starting from available or cleaning must fail."""
    case = release_case(bed_status=bed_status, current_patient=False)

    with pytest.raises(HTTPException) as error:
        BedReleaseService(db_session).start_release(case["bed"].id, case["ward_admin"])

    assert error.value.status_code == 409
    assert _release_events(db_session, case["bed"].id) == []


def test_start_release_rejects_an_occupied_bed_without_a_patient(db_session, release_case):
    """Transitioning an unassigned occupied bed must fail."""
    case = release_case(current_patient=False)

    with pytest.raises(HTTPException) as error:
        BedReleaseService(db_session).start_release(case["bed"].id, case["ward_admin"])

    assert error.value.status_code == 409


@pytest.mark.parametrize(
    ("payload_field", "wrong_value"),
    [
        ("patient_id", 999991),
        ("admission_id", 999992),
        ("report_id", 999993),
    ],
)
def test_vacating_idempotency_rejects_wrong_release_event_ownership(
    db_session, release_case, payload_field, wrong_value,
):
    """A release event for different context must not make a vacating bed idempotent."""
    case = release_case(bed_status=BedStatus.VACATING)
    _add_release_event(db_session, case, **{payload_field: wrong_value})

    with pytest.raises(HTTPException) as error:
        BedReleaseService(db_session).start_release(case["bed"].id, case["ward_admin"])

    assert error.value.status_code == 409


def test_vacating_idempotency_rejects_duplicate_matching_release_events(db_session, release_case):
    """Two matching start events are ambiguous and must not be treated as a clean repeat."""
    case = release_case(bed_status=BedStatus.VACATING)
    _add_release_event(db_session, case)
    _add_release_event(db_session, case)

    with pytest.raises(HTTPException) as error:
        BedReleaseService(db_session).start_release(case["bed"].id, case["ward_admin"])

    assert error.value.status_code == 409


def test_vacating_idempotency_rejects_an_exact_untrusted_release_clone(
    db_session, release_case,
):
    """An exact valid-shaped legacy clone must not establish release lineage."""
    case = release_case(bed_status=BedStatus.VACATING)
    _add_release_event(db_session, case, trusted_provenance=False)

    with pytest.raises(HTTPException) as error:
        BedReleaseService(db_session).start_release(case["bed"].id, case["ward_admin"])

    assert error.value.status_code == 409


def test_vacating_idempotency_ignores_an_exact_untrusted_clone_beside_trusted_lineage(
    db_session, release_case,
):
    """An exact legacy clone must not poison one valid trusted release event."""
    case = release_case(bed_status=BedStatus.VACATING)
    _add_release_event(db_session, case)
    _add_release_event(db_session, case, trusted_provenance=False)

    result = BedReleaseService(db_session).start_release(
        case["bed"].id, case["ward_admin"],
    )

    assert result.status == BedStatus.VACATING
    assert len(_release_events(db_session, case["bed"].id)) == 2


def test_vacating_idempotency_ignores_forged_conflicting_release_event(
    db_session, release_case,
):
    """A malformed legacy event must not poison a legitimate idempotent repeat."""
    case = release_case(bed_status=BedStatus.VACATING)
    _add_release_event(db_session, case)
    _add_release_event(db_session, case, patient_id=999994)

    result = BedReleaseService(db_session).start_release(
        case["bed"].id, case["ward_admin"],
    )

    assert result.status == BedStatus.VACATING
    assert len(_release_events(db_session, case["bed"].id)) == 2


def test_vacating_idempotency_ignores_a_prior_admission_release_event(
    isolated_release_db_path,
):
    """A reused bed's completed prior release must not make the current repeat ambiguous."""
    engine, SessionLocal, (bed_id, actor_id) = _committed_release_case(
        isolated_release_db_path,
        bed_status=BedStatus.VACATING,
        current_release_event=True,
        historical_release_event=True,
    )
    session = SessionLocal()
    verifier = SessionLocal()
    try:
        before_count = len(_release_events(session, bed_id))
        result = BedReleaseService(session).start_release(
            bed_id, session.get(User, actor_id),
        )

        assert result.status is BedStatus.VACATING
        assert len(_release_events(verifier, bed_id)) == before_count == 2
    finally:
        session.close()
        verifier.close()
        engine.dispose()


@pytest.mark.parametrize(
    "ownership_options",
    [{"admission_patient_matches": False}, {"admission_bed_matches": False}],
)
def test_start_release_rejects_mismatched_admission_ownership(
    db_session, release_case, ownership_options,
):
    """Using an admission owned by another patient or bed must fail."""
    case = release_case(**ownership_options)

    with pytest.raises(HTTPException) as error:
        BedReleaseService(db_session).start_release(case["bed"].id, case["ward_admin"])

    assert error.value.status_code == 409
    assert _release_events(db_session, case["bed"].id) == []


@pytest.mark.parametrize("actor_key", ["doctor", "ward_admin"])
def test_start_release_allows_doctors_and_ward_admins(db_session, release_case, actor_key):
    """Removing either permitted operational role must fail."""
    case = release_case()

    result = BedReleaseService(db_session).start_release(case["bed"].id, case[actor_key])

    assert result.status is BedStatus.VACATING


@pytest.mark.parametrize("actor_key", [None, "receiving_admin"])
def test_start_release_defensively_rejects_disallowed_service_actors(
    db_session, release_case, actor_key,
):
    """Calling the service directly must not bypass role checks."""
    case = release_case()
    actor = case[actor_key] if actor_key else None

    with pytest.raises(HTTPException) as error:
        BedReleaseService(db_session).start_release(case["bed"].id, actor)

    assert error.value.status_code == 403
    assert _release_events(db_session, case["bed"].id) == []


def test_start_release_endpoint_uses_server_actor_and_returns_refreshed_detail(
    client, db_session, release_case,
):
    """Accepting a client actor or returning a stale Bed model must fail."""
    case = release_case()

    response = client.post(
        f"/api/beds/{case['bed'].id}/start-release",
        json={"actor_user_id": case["receiving_admin"].id},
        headers={"X-User-Id": str(case["ward_admin"].id)},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "vacating"
    assert response.json()["current_patient_id"] == case["patient"].id
    assert response.json()["admission_status"] == "discharging"
    assert response.json()["release_eligible"] is False
    assert response.json()["transition_history"][0]["event_type"] == "bed_release_started"
    event = _release_events(db_session, case["bed"].id)[0]
    assert event.payload["actor_user_id"] == case["ward_admin"].id


def test_start_release_endpoint_requires_authentication(client, db_session, release_case):
    """Calling the route without a server-derived actor must return 401."""
    case = release_case()
    app.dependency_overrides[get_current_user_stub] = lambda: None
    try:
        response = client.post(f"/api/beds/{case['bed'].id}/start-release")
    finally:
        app.dependency_overrides.pop(get_current_user_stub, None)

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Authentication required"


def test_start_release_endpoint_rejects_a_disallowed_role(client, db_session, release_case):
    """A receiving administrator must not start local bed turnover."""
    case = release_case()

    response = client.post(
        f"/api/beds/{case['bed'].id}/start-release",
        headers={"X-User-Id": str(case["receiving_admin"].id)},
    )

    assert response.status_code == 403
    assert _release_events(db_session, case["bed"].id) == []


def test_start_release_is_idempotent_for_the_same_consistent_release(isolated_release_db_path):
    """Repeating a valid start must not create a second audit event."""
    engine, SessionLocal, (bed_id, actor_id) = _committed_release_case(isolated_release_db_path)
    session = SessionLocal()
    verifier = SessionLocal()
    try:
        service = BedReleaseService(session)
        actor = session.get(User, actor_id)

        first = service.start_release(bed_id, actor)
        second = service.start_release(bed_id, actor)

        assert first.status is BedStatus.VACATING
        assert second.status is BedStatus.VACATING
        assert session.in_transaction() is False
        assert [event.event_type for event in _release_events(verifier, bed_id)] == [
            "bed_release_started"
        ]
    finally:
        session.close()
        verifier.close()
        engine.dispose()


@pytest.fixture
def isolated_release_db_path():
    path = Path(__file__).parent / f".bed-release-{uuid4()}.db"
    yield path
    if path.exists():
        path.unlink()


def _committed_release_case(
    db_path,
    report_status=DischargeReportStatus.APPROVED,
    report_exists=True,
    bed_status=BedStatus.OCCUPIED,
    current_release_event=False,
    historical_release_event=False,
):
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    suffix = uuid4().hex
    actor = User(name="Ward Admin", email=f"stale-{suffix}@example.test", role=UserRole.WARD_ADMIN)
    patient = Patient(
        patient_code=f"STALE-{suffix}", first_name="Stale", last_name="Patient",
        date_of_birth=date(1985, 2, 3), gender="Female",
    )
    bed = Bed(ward="General Medicine", bed_number=f"STALE-{suffix}", status=bed_status)
    session.add_all([actor, patient, bed])
    session.flush()
    bed.current_patient_id = patient.id
    admission = Admission(
        patient_id=patient.id,
        primary_diagnosis="Pneumonia",
        attending_doctor_id=actor.id,
        status=AdmissionStatus.DISCHARGING,
        bed_id=bed.id,
    )
    session.add(admission)
    session.flush()
    if report_exists:
        report = DischargeReport(
            patient_id=patient.id,
            admission_id=admission.id,
            generated_content="Approved report",
            generation_provider="replicate",
            generation_model="openai/gpt-5.6-luna",
            status=report_status,
            approved_by=actor.id if report_status == DischargeReportStatus.APPROVED else None,
            approved_at=(
                datetime(2026, 8, 19, tzinfo=timezone.utc)
                if report_status == DischargeReportStatus.APPROVED else None
            ),
        )
        session.add(report)
        session.flush()
        if report_status == DischargeReportStatus.APPROVED:
            session.add(WorkflowEvent(
                event_type="report_approved",
                entity_type="discharge_report",
                entity_id=report.id,
                status="pending",
                trusted_provenance=True,
                payload={
                    "report_id": report.id,
                    "patient_id": report.patient_id,
                    "admission_id": report.admission_id,
                    "approved_by": report.approved_by,
                    "approved_at": report.approved_at.isoformat() if report.approved_at else None,
                },
                created_at=report.approved_at,
            ))
        if current_release_event:
            current_event_time = datetime(2026, 8, 19, 9, tzinfo=timezone.utc)
            session.add(WorkflowEvent(
                event_type="bed_release_started",
                entity_type="bed",
                entity_id=bed.id,
                status="pending",
                trusted_provenance=True,
                payload={
                    "bed_id": bed.id,
                    "patient_id": patient.id,
                    "admission_id": admission.id,
                    "report_id": report.id,
                    "previous_status": "occupied",
                    "new_status": "vacating",
                    "timestamp": current_event_time.isoformat(),
                    "actor_user_id": actor.id,
                    "actor_name": actor.name,
                    "actor_role": actor.role.value,
                },
                created_at=current_event_time,
            ))
    if historical_release_event:
        prior_patient = Patient(
            patient_code=f"PRIOR-{suffix}",
            first_name="Prior",
            last_name="Patient",
            date_of_birth=date(1975, 6, 7),
            gender="Female",
        )
        session.add(prior_patient)
        session.flush()
        prior_admission = Admission(
            patient_id=prior_patient.id,
            admission_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
            primary_diagnosis="Prior pneumonia",
            attending_doctor_id=actor.id,
            status=AdmissionStatus.DISCHARGED,
            bed_id=bed.id,
        )
        session.add(prior_admission)
        session.flush()
        prior_report = DischargeReport(
            patient_id=prior_patient.id,
            admission_id=prior_admission.id,
            generated_content="Prior approved report",
            generation_provider="replicate",
            generation_model="openai/gpt-5.6-luna",
            status=DischargeReportStatus.APPROVED,
            approved_by=actor.id,
            approved_at=datetime(2026, 7, 3, tzinfo=timezone.utc),
        )
        session.add(prior_report)
        session.flush()
        session.add(WorkflowEvent(
            event_type="bed_release_started",
            entity_type="bed",
            entity_id=bed.id,
            status="pending",
            trusted_provenance=True,
            payload={
                "bed_id": bed.id,
                "patient_id": prior_patient.id,
                "admission_id": prior_admission.id,
                "report_id": prior_report.id,
                "previous_status": "occupied",
                "new_status": "vacating",
                "timestamp": datetime(2026, 7, 3, 9, tzinfo=timezone.utc).isoformat(),
                "actor_user_id": actor.id,
                "actor_name": actor.name,
                "actor_role": actor.role.value,
            },
            created_at=datetime(2026, 7, 3, 9, tzinfo=timezone.utc),
        ))
    session.commit()
    ids = bed.id, actor.id
    session.close()
    return engine, SessionLocal, ids


def test_independent_stale_session_rechecks_and_does_not_duplicate_release(isolated_release_db_path):
    """A session that cached occupied state must not win a second transition."""
    engine, SessionLocal, (bed_id, actor_id) = _committed_release_case(isolated_release_db_path)
    first_session = SessionLocal()
    stale_session = SessionLocal()
    verifier = SessionLocal()
    try:
        assert stale_session.get(Bed, bed_id).status is BedStatus.OCCUPIED

        BedReleaseService(first_session).start_release(bed_id, first_session.get(User, actor_id))
        result = BedReleaseService(stale_session).start_release(bed_id, stale_session.get(User, actor_id))

        assert result.status is BedStatus.VACATING
        assert verifier.get(Bed, bed_id).status is BedStatus.VACATING
        assert len(_release_events(verifier, bed_id)) == 1
    finally:
        first_session.close()
        stale_session.close()
        verifier.close()
        engine.dispose()


def test_conditional_update_loser_returns_conflict_without_partial_state(
    isolated_release_db_path, monkeypatch,
):
    """A zero-row conditional update must not create a release event."""
    engine, SessionLocal, (bed_id, actor_id) = _committed_release_case(isolated_release_db_path)
    session = SessionLocal()
    original_execute = session.execute

    def lose_bed_update(statement, *args, **kwargs):
        if isinstance(statement, Update) and statement.table.name == "beds":
            return SimpleNamespace(rowcount=0)
        return original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(session, "execute", lose_bed_update)
    verifier = SessionLocal()
    try:
        with pytest.raises(HTTPException) as error:
            BedReleaseService(session).start_release(bed_id, session.get(User, actor_id))

        assert error.value.status_code == 409
        assert verifier.get(Bed, bed_id).status is BedStatus.OCCUPIED
        assert _release_events(verifier, bed_id) == []
    finally:
        session.close()
        verifier.close()
        engine.dispose()


def test_two_session_sqlite_race_has_one_winner_and_one_controlled_conflict(
    isolated_release_db_path,
):
    """Concurrent eligibility reads must still produce one durable transition."""
    engine, SessionLocal, (bed_id, actor_id) = _committed_release_case(isolated_release_db_path)
    update_barrier = Barrier(2)
    outcomes = Queue()

    def race_release():
        session = SessionLocal()
        original_execute = session.execute

        def synchronize_update(statement, *args, **kwargs):
            if isinstance(statement, Update) and statement.table.name == "beds":
                update_barrier.wait(timeout=5)
            return original_execute(statement, *args, **kwargs)

        session.execute = synchronize_update
        try:
            result = BedReleaseService(session).start_release(
                bed_id, session.get(User, actor_id),
            )
            outcomes.put(("ok", result.status.value))
        except HTTPException as error:
            outcomes.put(("http", error.status_code))
        except Exception as error:
            outcomes.put(("error", type(error).__name__))
        finally:
            session.close()

    threads = [Thread(target=race_release), Thread(target=race_release)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    verifier = SessionLocal()
    try:
        assert all(not thread.is_alive() for thread in threads)
        assert sorted([outcomes.get_nowait(), outcomes.get_nowait()]) == [
            ("http", 409),
            ("ok", "vacating"),
        ]
        assert verifier.get(Bed, bed_id).status is BedStatus.VACATING
        assert len(_release_events(verifier, bed_id)) == 1
    finally:
        verifier.close()
        engine.dispose()


def test_start_release_rolls_back_when_event_persistence_fails(
    isolated_release_db_path, monkeypatch,
):
    """An event write failure must not leave the bed vacating."""
    engine, SessionLocal, (bed_id, actor_id) = _committed_release_case(isolated_release_db_path)
    session = SessionLocal()
    original_flush = session.flush
    original_rollback = session.rollback
    rollback_called = False

    def fail_event_flush(*args, **kwargs):
        if any(
            isinstance(instance, WorkflowEvent) and instance.event_type == "bed_release_started"
            for instance in session.new
        ):
            raise SQLAlchemyError("bed release event flush failed")
        return original_flush(*args, **kwargs)

    def track_rollback():
        nonlocal rollback_called
        rollback_called = True
        return original_rollback()

    monkeypatch.setattr(session, "flush", fail_event_flush)
    monkeypatch.setattr(session, "rollback", track_rollback)

    verifier = SessionLocal()
    try:
        with pytest.raises(SQLAlchemyError, match="bed release event flush failed"):
            BedReleaseService(session).start_release(bed_id, session.get(User, actor_id))

        assert rollback_called is True
        assert verifier.get(Bed, bed_id).status is BedStatus.OCCUPIED
        assert _release_events(verifier, bed_id) == []
    finally:
        session.close()
        verifier.close()
        engine.dispose()


def test_start_release_rolls_back_when_commit_fails(isolated_release_db_path, monkeypatch):
    """A commit failure must roll back both the transition and audit event."""
    engine, SessionLocal, (bed_id, actor_id) = _committed_release_case(isolated_release_db_path)
    session = SessionLocal()
    original_rollback = session.rollback
    rollback_called = False
    commit_calls = 0

    def fail_commit():
        nonlocal commit_calls
        commit_calls += 1
        raise SQLAlchemyError("bed release commit failed")

    def track_rollback():
        nonlocal rollback_called
        rollback_called = True
        return original_rollback()

    monkeypatch.setattr(session, "commit", fail_commit)
    monkeypatch.setattr(session, "rollback", track_rollback)

    verifier = SessionLocal()
    try:
        with pytest.raises(SQLAlchemyError, match="bed release commit failed"):
            BedReleaseService(session).start_release(bed_id, session.get(User, actor_id))

        assert commit_calls == 1
        assert rollback_called is True
        assert verifier.get(Bed, bed_id).status is BedStatus.OCCUPIED
        assert _release_events(verifier, bed_id) == []
    finally:
        session.close()
        verifier.close()
        engine.dispose()


def test_start_release_rolls_back_when_precommit_refresh_fails(
    isolated_release_db_path, monkeypatch,
):
    """A refresh failure must occur before commit so state remains atomic."""
    engine, SessionLocal, (bed_id, actor_id) = _committed_release_case(isolated_release_db_path)
    session = SessionLocal()
    original_rollback = session.rollback
    rollback_called = False

    def fail_refresh(*args, **kwargs):
        raise SQLAlchemyError("bed refresh failed")

    def track_rollback():
        nonlocal rollback_called
        rollback_called = True
        return original_rollback()

    monkeypatch.setattr(session, "refresh", fail_refresh)
    monkeypatch.setattr(session, "rollback", track_rollback)

    verifier = SessionLocal()
    try:
        with pytest.raises(SQLAlchemyError, match="bed refresh failed"):
            BedReleaseService(session).start_release(bed_id, session.get(User, actor_id))

        assert rollback_called is True
        assert verifier.get(Bed, bed_id).status is BedStatus.OCCUPIED
        assert _release_events(verifier, bed_id) == []
    finally:
        session.close()
        verifier.close()
        engine.dispose()


def test_endpoint_detail_failure_occurs_before_commit_and_rolls_back(
    isolated_release_db_path, monkeypatch,
):
    """A failed response snapshot must not report failure after durable mutation."""
    engine, SessionLocal, (bed_id, actor_id) = _committed_release_case(isolated_release_db_path)
    request_session = SessionLocal()

    def override_get_db():
        yield request_session

    def fail_detail(*args, **kwargs):
        raise SQLAlchemyError("bed detail snapshot failed")

    monkeypatch.setattr(BedQueryService, "get_bed", fail_detail)
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as isolated_client:
            response = isolated_client.post(
                f"/api/beds/{bed_id}/start-release",
                headers={"X-User-Id": str(actor_id)},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    verifier = SessionLocal()
    try:
        assert response.status_code == 500
        assert response.json()["error"]["message"] == "Unable to start bed release"
        assert verifier.get(Bed, bed_id).status is BedStatus.OCCUPIED
        assert _release_events(verifier, bed_id) == []
    finally:
        request_session.close()
        verifier.close()
        engine.dispose()


def test_start_release_returns_not_found_for_a_missing_bed(db_session, release_case):
    """Turning a missing target into a generic conflict must fail."""
    case = release_case()

    with pytest.raises(HTTPException) as error:
        BedReleaseService(db_session).start_release(999999, case["ward_admin"])

    assert error.value.status_code == 404
