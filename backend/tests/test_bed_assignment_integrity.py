from datetime import date, datetime, timezone
from queue import Queue
from threading import Barrier, Event as ThreadEvent, Thread

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.dml import Update

from app.api.dependencies.database import get_db
from app.api.routes.admissions import create_admission
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
from app.schemas.admission import AdmissionCreate
from app.services.admission_assignment_service import AdmissionAssignmentService
from app.services.bed_release_service import BedReleaseService


ACTIVE_STATUSES = (
    AdmissionStatus.ADMITTED,
    AdmissionStatus.DISCHARGING,
    AdmissionStatus.TRANSFER_PENDING,
)


def _doctor(db, suffix="owner"):
    doctor = User(
        name=f"Dr {suffix}",
        email=f"{suffix}@assignment.test",
        role=UserRole.DOCTOR,
    )
    db.add(doctor)
    db.flush()
    return doctor


def _patient(db, suffix):
    patient = Patient(
        patient_code=f"ASSIGN-{suffix}",
        first_name="Assignment",
        last_name=suffix,
        date_of_birth=date(1988, 1, 1),
        gender="Other",
    )
    db.add(patient)
    db.flush()
    return patient


def _bed(db, status=BedStatus.AVAILABLE, patient_id=None):
    bed = Bed(
        ward="Assignment Ward",
        bed_number=f"A-{db.query(Bed).count() + 1}",
        status=status,
        current_patient_id=patient_id,
    )
    db.add(bed)
    db.flush()
    return bed


def _payload(patient, doctor, bed, status=AdmissionStatus.ADMITTED):
    return {
        "patient_id": patient.id,
        "admission_date": "2026-08-19T09:00:00Z",
        "primary_diagnosis": "Assignment integrity test",
        "attending_doctor_id": doctor.id,
        "status": status.value,
        "bed_id": bed.id,
    }


def _active_owners(db, bed_id):
    return db.query(Admission).filter(
        Admission.bed_id == bed_id,
        Admission.status.in_(ACTIVE_STATUSES),
    ).all()


def test_create_admission_atomically_claims_available_bed(client, db_session):
    doctor = _doctor(db_session, "claim")
    patient = _patient(db_session, "claim")
    bed = _bed(db_session)

    response = client.post("/api/admissions", json=_payload(patient, doctor, bed))

    assert response.status_code == 201
    db_session.refresh(bed)
    admission = db_session.get(Admission, response.json()["id"])
    assert admission.patient_id == patient.id
    assert admission.bed_id == bed.id
    assert bed.status == BedStatus.OCCUPIED
    assert bed.current_patient_id == patient.id
    assert [owner.id for owner in _active_owners(db_session, bed.id)] == [admission.id]


def test_create_admission_rejects_owned_bed_even_if_status_is_stale_available(client, db_session):
    doctor = _doctor(db_session, "stale")
    first_patient = _patient(db_session, "stale-first")
    second_patient = _patient(db_session, "stale-second")
    bed = _bed(db_session)
    existing = Admission(
        patient_id=first_patient.id,
        admission_date=datetime.now(timezone.utc),
        primary_diagnosis="Existing owner",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.ADMITTED,
        bed_id=bed.id,
    )
    db_session.add(existing)
    db_session.commit()

    response = client.post("/api/admissions", json=_payload(second_patient, doctor, bed))

    assert response.status_code == 409
    assert response.json()["error"]["message"] == "Bed is unavailable or already has an active admission"
    db_session.refresh(bed)
    assert bed.status == BedStatus.AVAILABLE
    assert bed.current_patient_id is None
    assert [owner.id for owner in _active_owners(db_session, bed.id)] == [existing.id]


def test_second_admission_loses_the_same_bed_claim_without_partial_row(client, db_session):
    doctor = _doctor(db_session, "double")
    first_patient = _patient(db_session, "double-first")
    second_patient = _patient(db_session, "double-second")
    bed = _bed(db_session)

    first = client.post("/api/admissions", json=_payload(first_patient, doctor, bed))
    second = client.post("/api/admissions", json=_payload(second_patient, doctor, bed))

    assert first.status_code == 201
    assert second.status_code == 409
    db_session.refresh(bed)
    owners = _active_owners(db_session, bed.id)
    assert [(owner.id, owner.patient_id) for owner in owners] == [
        (first.json()["id"], first_patient.id),
    ]
    assert bed.status == BedStatus.OCCUPIED
    assert bed.current_patient_id == first_patient.id


def test_admission_commit_failure_rolls_back_bed_claim_and_returns_controlled_error(
    tmp_path, monkeypatch,
):
    database_path = tmp_path / "assignment-rollback.sqlite"
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)
    session = SessionLocal()
    doctor = _doctor(session, "rollback")
    patient = _patient(session, "rollback")
    bed = _bed(session)
    session.commit()
    bed_id = bed.id
    patient_id = patient.id

    real_commit = session.commit

    def fail_commit():
        raise SQLAlchemyError("forced admission commit failure")

    monkeypatch.setattr(session, "commit", fail_commit)

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.post("/api/admissions", json=_payload(patient, doctor, bed))
    finally:
        app.dependency_overrides.clear()
        monkeypatch.setattr(session, "commit", real_commit)

    assert response.status_code == 500
    assert response.json()["error"]["message"] == "Unable to create admission"
    session.expire_all()
    persisted_bed = session.get(Bed, bed_id)
    assert persisted_bed.status == BedStatus.AVAILABLE
    assert persisted_bed.current_patient_id is None
    assert session.query(Admission).filter(Admission.patient_id == patient_id).count() == 0
    session.close()
    engine.dispose()


def test_admission_response_serialization_performs_no_database_access_after_commit(
    tmp_path, monkeypatch,
):
    """Returning an expired ORM row must not trigger a post-commit response query."""
    database_path = tmp_path / "assignment-response-snapshot.sqlite"
    engine = create_engine(
        f"sqlite:///{database_path}", connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)
    session = SessionLocal()
    doctor = _doctor(session, "snapshot")
    patient = _patient(session, "snapshot")
    bed = _bed(session)
    session.commit()

    commit_returned = False
    post_commit_statements = []
    real_commit = session.commit

    def tracked_commit():
        nonlocal commit_returned
        real_commit()
        commit_returned = True

    def track_post_commit_sql(_connection, _cursor, statement, *_args):
        if commit_returned:
            post_commit_statements.append(statement)

    monkeypatch.setattr(session, "commit", tracked_commit)
    event.listen(engine, "before_cursor_execute", track_post_commit_sql)

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            response = test_client.post("/api/admissions", json=_payload(patient, doctor, bed))
    finally:
        app.dependency_overrides.clear()
        event.remove(engine, "before_cursor_execute", track_post_commit_sql)

    assert response.status_code == 201
    assert response.json()["patient_id"] == patient.id
    assert post_commit_statements == []
    session.close()
    engine.dispose()


def test_stale_independent_session_loses_conditional_assignment_claim(tmp_path):
    database_path = tmp_path / "assignment-race.sqlite"
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)
    setup = SessionLocal()
    try:
        doctor = _doctor(setup, "race")
        first_patient = _patient(setup, "race-first")
        second_patient = _patient(setup, "race-second")
        bed = _bed(setup)
        setup.commit()
        ids = doctor.id, first_patient.id, second_patient.id, bed.id
    finally:
        setup.close()

    first_session = SessionLocal()
    stale_session = SessionLocal()
    try:
        doctor_id, first_patient_id, second_patient_id, bed_id = ids
        first_session.get(Bed, bed_id)
        stale_session.get(Bed, bed_id)
        first_input = AdmissionCreate(
            patient_id=first_patient_id,
            admission_date=datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc),
            primary_diagnosis="First claim",
            attending_doctor_id=doctor_id,
            status=AdmissionStatus.ADMITTED,
            bed_id=bed_id,
        )
        second_input = first_input.model_copy(update={
            "patient_id": second_patient_id,
            "primary_diagnosis": "Losing claim",
        })

        winner = create_admission(first_input, db=first_session)
        with pytest.raises(HTTPException) as conflict:
            create_admission(second_input, db=stale_session)

        assert conflict.value.status_code == 409
        assert conflict.value.detail == "Bed is unavailable or already has an active admission"
        verifier = SessionLocal()
        try:
            persisted_bed = verifier.get(Bed, bed_id)
            owners = _active_owners(verifier, bed_id)
            assert [(owner.id, owner.patient_id) for owner in owners] == [
                (winner.id, first_patient_id),
            ]
            assert persisted_bed.status == BedStatus.OCCUPIED
            assert persisted_bed.current_patient_id == first_patient_id
        finally:
            verifier.close()
    finally:
        first_session.close()
        stale_session.close()
        engine.dispose()


def _durable_assignment_case(tmp_path, name, bed_status):
    database_path = tmp_path / f"{name}.sqlite"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False, "timeout": 1},
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        connection.execute(sa.text(
            "CREATE UNIQUE INDEX uq_admissions_active_bed "
            "ON admissions (bed_id) WHERE bed_id IS NOT NULL AND status IN ("
            "'ADMITTED', 'DISCHARGING', 'TRANSFER_PENDING', "
            "'admitted', 'discharging', 'transfer_pending')"
        ))
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with SessionLocal() as setup:
        doctor = _doctor(setup, name)
        first_patient = _patient(setup, f"{name}-first")
        second_patient = _patient(setup, f"{name}-second")
        bed = _bed(setup, status=bed_status)
        setup.commit()
        ids = doctor.id, first_patient.id, second_patient.id, bed.id
    return engine, SessionLocal, ids


def _admission_input(doctor_id, patient_id, bed_id, diagnosis):
    return AdmissionCreate(
        patient_id=patient_id,
        admission_date=datetime(2026, 8, 20, 9, tzinfo=timezone.utc),
        primary_diagnosis=diagnosis,
        attending_doctor_id=doctor_id,
        status=AdmissionStatus.ADMITTED,
        bed_id=bed_id,
    )


def test_two_simultaneous_admissions_have_one_durable_winner_and_controlled_conflict(
    tmp_path,
):
    """Removing either CAS/constraint protection may allow two owners or leak a DB error."""
    engine, SessionLocal, ids = _durable_assignment_case(
        tmp_path, "simultaneous-admissions", BedStatus.AVAILABLE,
    )
    doctor_id, first_patient_id, second_patient_id, bed_id = ids
    update_barrier = Barrier(2)
    outcomes = Queue()

    def claim(patient_id):
        session = SessionLocal()
        original_execute = session.execute

        def synchronize_bed_update(statement, *args, **kwargs):
            if isinstance(statement, Update) and statement.table.name == "beds":
                update_barrier.wait(timeout=5)
            return original_execute(statement, *args, **kwargs)

        session.execute = synchronize_bed_update
        try:
            response = AdmissionAssignmentService(session).create(
                _admission_input(
                    doctor_id, patient_id, bed_id, f"Concurrent claim {patient_id}",
                )
            )
            outcomes.put(("ok", response.patient_id))
        except HTTPException as error:
            outcomes.put(("http", error.status_code))
        except Exception as error:
            outcomes.put(("error", type(error).__name__))
        finally:
            session.close()

    threads = [
        Thread(target=claim, args=(first_patient_id,)),
        Thread(target=claim, args=(second_patient_id,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    with SessionLocal() as verifier:
        try:
            assert all(not thread.is_alive() for thread in threads)
            results = [outcomes.get_nowait(), outcomes.get_nowait()]
            assert sum(kind == "ok" for kind, _value in results) == 1
            assert sum(item == ("http", 409) for item in results) == 1
            winner_patient_id = next(value for kind, value in results if kind == "ok")
            persisted_bed = verifier.get(Bed, bed_id)
            owners = _active_owners(verifier, bed_id)
            assert [(owner.patient_id, owner.status) for owner in owners] == [
                (winner_patient_id, AdmissionStatus.ADMITTED),
            ]
            assert persisted_bed.status == BedStatus.OCCUPIED
            assert persisted_bed.current_patient_id == winner_patient_id
            assert verifier.query(WorkflowEvent).count() == 0
        finally:
            engine.dispose()


def test_admission_loses_cleaning_race_while_cleaner_is_paused_before_update(tmp_path):
    """An admission reading CLEANING mid-flight must conflict without creating an owner."""
    engine, SessionLocal, ids = _durable_assignment_case(
        tmp_path, "claim-during-cleaning", BedStatus.CLEANING,
    )
    doctor_id, first_patient_id, _second_patient_id, bed_id = ids
    start_barrier = Barrier(2)
    cleaner_at_update = ThreadEvent()
    admission_finished = ThreadEvent()
    outcomes = Queue()

    def finish_cleaning():
        session = SessionLocal()
        original_execute = session.execute

        def pause_bed_update(statement, *args, **kwargs):
            if isinstance(statement, Update) and statement.table.name == "beds":
                cleaner_at_update.set()
                if not admission_finished.wait(timeout=5):
                    raise TimeoutError("admission did not reach the cleaning interleaving")
            return original_execute(statement, *args, **kwargs)

        session.execute = pause_bed_update
        try:
            start_barrier.wait(timeout=5)
            result = BedReleaseService(session).cleaning_complete(
                bed_id, session.get(User, doctor_id),
            )
            outcomes.put(("cleaning", "ok", result.status.value))
        except Exception as error:
            outcomes.put(("cleaning", "error", type(error).__name__))
        finally:
            session.close()

    def claim_during_cleaning():
        session = SessionLocal()
        try:
            start_barrier.wait(timeout=5)
            if not cleaner_at_update.wait(timeout=5):
                raise TimeoutError("cleaner did not reach its bed update")
            AdmissionAssignmentService(session).create(
                _admission_input(
                    doctor_id, first_patient_id, bed_id, "Claim during cleaning",
                )
            )
            outcomes.put(("admission", "ok", first_patient_id))
        except HTTPException as error:
            outcomes.put(("admission", "http", error.status_code))
        except Exception as error:
            outcomes.put(("admission", "error", type(error).__name__))
        finally:
            session.close()
            admission_finished.set()

    threads = [Thread(target=finish_cleaning), Thread(target=claim_during_cleaning)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    with SessionLocal() as verifier:
        try:
            assert all(not thread.is_alive() for thread in threads)
            assert sorted([outcomes.get_nowait(), outcomes.get_nowait()]) == [
                ("admission", "http", 409),
                ("cleaning", "ok", "available"),
            ]
            persisted_bed = verifier.get(Bed, bed_id)
            assert persisted_bed.status == BedStatus.AVAILABLE
            assert persisted_bed.current_patient_id is None
            assert _active_owners(verifier, bed_id) == []
            assert [event.event_type for event in verifier.query(WorkflowEvent).all()] == [
                "bed_available",
            ]
        finally:
            engine.dispose()


def test_admission_wins_cleaning_race_after_cleaner_commits(tmp_path):
    """A post-cleaning claim may succeed only as one consistent occupied assignment."""
    engine, SessionLocal, ids = _durable_assignment_case(
        tmp_path, "claim-after-cleaning", BedStatus.CLEANING,
    )
    doctor_id, first_patient_id, _second_patient_id, bed_id = ids
    start_barrier = Barrier(2)
    cleaning_committed = ThreadEvent()
    outcomes = Queue()

    def finish_cleaning():
        with SessionLocal() as session:
            try:
                start_barrier.wait(timeout=5)
                result = BedReleaseService(session).cleaning_complete(
                    bed_id, session.get(User, doctor_id),
                )
                outcomes.put(("cleaning", "ok", result.status.value))
            except Exception as error:
                outcomes.put(("cleaning", "error", type(error).__name__))
            finally:
                cleaning_committed.set()

    def claim_after_cleaning():
        with SessionLocal() as session:
            try:
                start_barrier.wait(timeout=5)
                if not cleaning_committed.wait(timeout=5):
                    raise TimeoutError("cleaner did not commit")
                result = AdmissionAssignmentService(session).create(
                    _admission_input(
                        doctor_id, first_patient_id, bed_id, "Claim after cleaning",
                    )
                )
                outcomes.put(("admission", "ok", result.patient_id))
            except HTTPException as error:
                outcomes.put(("admission", "http", error.status_code))
            except Exception as error:
                outcomes.put(("admission", "error", type(error).__name__))

    threads = [Thread(target=finish_cleaning), Thread(target=claim_after_cleaning)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    with SessionLocal() as verifier:
        try:
            assert all(not thread.is_alive() for thread in threads)
            assert sorted([outcomes.get_nowait(), outcomes.get_nowait()]) == [
                ("admission", "ok", first_patient_id),
                ("cleaning", "ok", "available"),
            ]
            persisted_bed = verifier.get(Bed, bed_id)
            owners = _active_owners(verifier, bed_id)
            assert [(owner.patient_id, owner.status) for owner in owners] == [
                (first_patient_id, AdmissionStatus.ADMITTED),
            ]
            assert persisted_bed.status == BedStatus.OCCUPIED
            assert persisted_bed.current_patient_id == first_patient_id
            assert [event.event_type for event in verifier.query(WorkflowEvent).all()] == [
                "bed_available",
            ]
        finally:
            engine.dispose()


def _release_context(db, status):
    doctor = _doctor(db, f"release-{status.value}")
    patient = _patient(db, f"release-{status.value}")
    competitor = _patient(db, f"competitor-{status.value}")
    bed = _bed(db, status=status, patient_id=patient.id)
    owner = Admission(
        patient_id=patient.id,
        admission_date=datetime.now(timezone.utc),
        primary_diagnosis="Matching owner",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.DISCHARGING,
        bed_id=bed.id,
    )
    competing_owner = Admission(
        patient_id=competitor.id,
        admission_date=datetime.now(timezone.utc),
        primary_diagnosis="Competing owner",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.ADMITTED,
        bed_id=bed.id,
    )
    db.add_all([owner, competing_owner])
    db.flush()
    return doctor, patient, bed, owner


def test_start_release_rejects_any_competing_active_bed_owner(db_session):
    doctor, patient, bed, owner = _release_context(db_session, BedStatus.OCCUPIED)
    from app.models import DischargeReport, DischargeReportStatus

    report = DischargeReport(
        patient_id=patient.id,
        admission_id=owner.id,
        generated_content="Approved report",
        generation_provider="test",
        generation_model="test-model",
        status=DischargeReportStatus.APPROVED,
        approved_by=doctor.id,
        approved_at=datetime.now(timezone.utc),
    )
    db_session.add(report)
    db_session.flush()
    db_session.add(WorkflowEvent(
        event_type="report_approved",
        entity_type="discharge_report",
        entity_id=report.id,
        status="pending",
        payload={"patient_id": patient.id, "admission_id": owner.id},
    ))
    db_session.flush()

    with pytest.raises(HTTPException) as conflict:
        BedReleaseService(db_session).start_release(bed.id, doctor)

    assert conflict.value.status_code == 409
    assert conflict.value.detail == "Bed must have exactly one matching active admission owner"
    db_session.refresh(bed)
    assert bed.status == BedStatus.OCCUPIED


def test_patient_departure_rejects_any_competing_active_bed_owner(db_session):
    doctor, _patient_record, bed, _owner = _release_context(db_session, BedStatus.VACATING)

    with pytest.raises(HTTPException) as conflict:
        BedReleaseService(db_session).patient_departed(bed.id, doctor)

    assert conflict.value.status_code == 409
    assert conflict.value.detail == "Bed must have exactly one matching active admission owner"
    db_session.refresh(bed)
    assert bed.status == BedStatus.VACATING


def test_cleaning_cannot_finish_while_any_active_admission_references_bed(db_session):
    doctor = _doctor(db_session, "cleaning-owner")
    patient = _patient(db_session, "cleaning-owner")
    bed = _bed(db_session, status=BedStatus.CLEANING)
    admission = Admission(
        patient_id=patient.id,
        admission_date=datetime.now(timezone.utc),
        primary_diagnosis="Unexpected active owner",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.ADMITTED,
        bed_id=bed.id,
    )
    db_session.add(admission)
    db_session.flush()

    with pytest.raises(HTTPException) as conflict:
        BedReleaseService(db_session).cleaning_complete(bed.id, doctor)

    assert conflict.value.status_code == 409
    assert conflict.value.detail == "Bed cannot become available while an active admission references it"
    db_session.refresh(bed)
    assert bed.status == BedStatus.CLEANING
    assert db_session.query(WorkflowEvent).filter(
        WorkflowEvent.entity_type == "bed",
        WorkflowEvent.entity_id == bed.id,
    ).count() == 0
