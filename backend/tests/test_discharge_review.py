from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
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
from app.services.discharge_service import DischargeService


@pytest.fixture
def isolated_review_db_path():
    path = Path(__file__).parent / f".discharge-review-{uuid4()}.db"
    yield path
    if path.exists():
        path.unlink()


def _committed_review_case(db_path):
    """Create a committed case for tests that need independent sessions."""
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    doctor = User(name="Dr. Independent", email="independent.doctor@example.test", role=UserRole.DOCTOR)
    patient = Patient(
        patient_code="RACE-1001", first_name="Race", last_name="Patient",
        date_of_birth=date(1985, 2, 3), gender="Female", blood_group="O+",
    )
    bed = Bed(ward="General Medicine", bed_number="G-14", status=BedStatus.OCCUPIED)
    session.add_all([doctor, patient, bed])
    session.flush()
    bed.current_patient_id = patient.id
    admission = Admission(
        patient_id=patient.id, admission_date=datetime(2026, 8, 10, tzinfo=timezone.utc),
        primary_diagnosis="Pneumonia", attending_doctor_id=doctor.id,
        status=AdmissionStatus.DISCHARGING, bed_id=bed.id,
    )
    session.add(admission)
    session.flush()
    report = DischargeReport(
        patient_id=patient.id, admission_id=admission.id, generated_content="AI draft content",
        generation_provider="replicate", generation_model="openai/gpt-5.6-luna",
        status=DischargeReportStatus.GENERATED,
    )
    session.add(report)
    session.commit()
    ids = report.id, admission.id, doctor.id
    session.close()
    return engine, SessionLocal, ids


@pytest.fixture
def generated_report(db_session):
    doctor = User(name="Dr. Review", email="review.doctor@example.test", role=UserRole.DOCTOR)
    ward_admin = User(name="Ward Admin", email="ward.admin@example.test", role=UserRole.WARD_ADMIN)
    patient = Patient(
        patient_code="REV-1001", first_name="Review", last_name="Patient",
        date_of_birth=date(1985, 2, 3), gender="Female", blood_group="O+",
    )
    bed = Bed(ward="General Medicine", bed_number="G-13", status=BedStatus.OCCUPIED)
    db_session.add_all([doctor, ward_admin, patient, bed])
    db_session.flush()
    bed.current_patient_id = patient.id
    admission = Admission(
        patient_id=patient.id, admission_date=datetime(2026, 8, 10, tzinfo=timezone.utc),
        primary_diagnosis="Pneumonia", attending_doctor_id=doctor.id,
        status=AdmissionStatus.DISCHARGING, bed_id=bed.id,
    )
    db_session.add(admission)
    db_session.flush()
    report = DischargeReport(
        patient_id=patient.id, admission_id=admission.id, generated_content="AI draft content",
        generation_provider="replicate", generation_model="openai/gpt-5.6-luna",
        status=DischargeReportStatus.GENERATED,
    )
    db_session.add(report)
    db_session.flush()
    return report


def test_edit_preserves_ai_output_and_sets_under_review(client, generated_report):
    response = client.put(
        f"/api/discharge/reports/{generated_report.id}/edit",
        json={"edited_content": "Doctor-reviewed discharge content"},
    )

    assert response.status_code == 200
    assert response.json()["generated_content"] == generated_report.generated_content
    assert response.json()["edited_content"] == "Doctor-reviewed discharge content"
    assert response.json()["status"] == "under_review"


def test_non_doctor_cannot_edit(client, generated_report):
    response = client.put(
        f"/api/discharge/reports/{generated_report.id}/edit",
        json={"edited_content": "Unauthorized change"}, headers={"X-User-Id": "2"},
    )

    assert response.status_code == 403


def test_approval_is_explicit_atomic_and_does_not_release_bed(client, db_session, generated_report):
    response = client.post(
        f"/api/discharge/reports/{generated_report.id}/approve", json={"acknowledged": True},
    )
    db_session.refresh(generated_report.admission)
    db_session.refresh(generated_report.admission.bed)

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["approved_at"] is not None
    assert generated_report.admission.status == AdmissionStatus.DISCHARGING
    assert generated_report.admission.bed.status == BedStatus.OCCUPIED
    event = db_session.query(WorkflowEvent).filter_by(
        entity_type="discharge_report", entity_id=generated_report.id,
    ).one()
    assert event.event_type == "report_approved"
    assert getattr(event, "trusted_provenance", None) is True


def test_approval_requires_explicit_acknowledgement(client, generated_report):
    response = client.post(f"/api/discharge/reports/{generated_report.id}/approve", json={})

    assert response.status_code == 422


def test_approval_uses_development_doctor_not_client_controlled_identity(client, generated_report):
    response = client.post(
        f"/api/discharge/reports/{generated_report.id}/approve",
        json={"acknowledged": True, "approved_by": 999999},
    )

    assert response.status_code == 422


def test_non_doctor_cannot_approve(client, generated_report):
    response = client.post(
        f"/api/discharge/reports/{generated_report.id}/approve",
        json={"acknowledged": True}, headers={"X-User-Id": "2"},
    )

    assert response.status_code == 403


def test_approved_report_cannot_be_edited(client, generated_report):
    approved = client.post(
        f"/api/discharge/reports/{generated_report.id}/approve", json={"acknowledged": True},
    )
    response = client.put(
        f"/api/discharge/reports/{generated_report.id}/edit", json={"edited_content": "Changed after approval"},
    )

    assert approved.status_code == 200
    assert response.status_code == 409


def test_repeated_approval_returns_conflict(client, generated_report):
    first = client.post(f"/api/discharge/reports/{generated_report.id}/approve", json={"acknowledged": True})
    second = client.post(f"/api/discharge/reports/{generated_report.id}/approve", json={"acknowledged": True})

    assert first.status_code == 200
    assert second.status_code == 409


def test_whitespace_only_edit_is_rejected_at_the_server_boundary(client, generated_report):
    response = client.put(
        f"/api/discharge/reports/{generated_report.id}/edit",
        json={"edited_content": " \n\t "},
    )

    assert response.status_code == 422


def test_approval_rejects_a_whitespace_only_effective_report(client, db_session, generated_report):
    generated_report.edited_content = " \n\t "
    db_session.flush()

    response = client.post(
        f"/api/discharge/reports/{generated_report.id}/approve", json={"acknowledged": True},
    )

    assert response.status_code == 409
    db_session.refresh(generated_report)
    assert generated_report.status == DischargeReportStatus.GENERATED
    assert db_session.query(WorkflowEvent).filter_by(entity_id=generated_report.id).count() == 0


def test_concurrent_stale_approvals_create_one_event_and_one_conflict(isolated_review_db_path, monkeypatch):
    engine, SessionLocal, (report_id, _, doctor_id) = _committed_review_case(isolated_review_db_path)
    first_session = SessionLocal()
    second_session = SessionLocal()
    verifier = SessionLocal()
    try:
        stale_report = second_session.get(DischargeReport, report_id)
        second_service = DischargeService(second_session)
        monkeypatch.setattr(second_service.repo, "get", lambda _: stale_report)

        DischargeService(first_session).approve_report(report_id, first_session.get(User, doctor_id))
        with pytest.raises(HTTPException) as error:
            second_service.approve_report(report_id, second_session.get(User, doctor_id))

        assert error.value.status_code == 409
        assert verifier.get(DischargeReport, report_id).status == DischargeReportStatus.APPROVED
        assert verifier.query(WorkflowEvent).filter_by(entity_id=report_id).count() == 1
    finally:
        first_session.close()
        second_session.close()
        verifier.close()
        engine.dispose()


def test_stale_edit_cannot_revert_an_approved_report_or_its_single_event(isolated_review_db_path, monkeypatch):
    engine, SessionLocal, (report_id, _, doctor_id) = _committed_review_case(isolated_review_db_path)
    approving_session = SessionLocal()
    stale_edit_session = SessionLocal()
    verifier = SessionLocal()
    try:
        stale_report = stale_edit_session.get(DischargeReport, report_id)
        stale_edit_service = DischargeService(stale_edit_session)
        monkeypatch.setattr(stale_edit_service.repo, "get", lambda _: stale_report)
        DischargeService(approving_session).approve_report(report_id, approving_session.get(User, doctor_id))

        with pytest.raises(HTTPException) as error:
            stale_edit_service.edit_report(
                report_id,
                "Stale edit that must not replace approved content",
                stale_edit_session.get(User, doctor_id),
            )

        assert error.value.status_code == 409
        approved_report = verifier.get(DischargeReport, report_id)
        assert approved_report.status == DischargeReportStatus.APPROVED
        assert approved_report.edited_content is None
        assert verifier.query(WorkflowEvent).filter_by(entity_id=report_id).count() == 1
    finally:
        approving_session.close()
        stale_edit_session.close()
        verifier.close()
        engine.dispose()


def test_approval_rechecks_admission_status_after_stale_session_load(isolated_review_db_path):
    engine, SessionLocal, (report_id, admission_id, doctor_id) = _committed_review_case(isolated_review_db_path)
    stale_session = SessionLocal()
    changing_session = SessionLocal()
    verifier = SessionLocal()
    try:
        stale_report = stale_session.get(DischargeReport, report_id)
        assert stale_report.admission.status == AdmissionStatus.DISCHARGING

        changing_session.get(Admission, admission_id).status = AdmissionStatus.ADMITTED
        changing_session.commit()

        with pytest.raises(HTTPException) as error:
            DischargeService(stale_session).approve_report(report_id, stale_session.get(User, doctor_id))

        assert error.value.status_code == 409
        assert verifier.get(DischargeReport, report_id).status == DischargeReportStatus.GENERATED
        assert verifier.query(WorkflowEvent).filter_by(entity_id=report_id).count() == 0
    finally:
        stale_session.close()
        changing_session.close()
        verifier.close()
        engine.dispose()


def test_approval_rolls_back_report_when_event_flush_fails(isolated_review_db_path, monkeypatch):
    engine, SessionLocal, (report_id, _, doctor_id) = _committed_review_case(isolated_review_db_path)
    session = SessionLocal()
    service = DischargeService(session)
    doctor = session.get(User, doctor_id)
    original_flush = session.flush
    original_commit = session.commit
    original_rollback = session.rollback
    commit_calls = 0
    rollback_called = False

    def fail_when_event_is_pending(*args, **kwargs):
        if any(isinstance(instance, WorkflowEvent) for instance in session.new):
            raise SQLAlchemyError("workflow event flush failed")
        return original_flush(*args, **kwargs)

    def track_commit():
        nonlocal commit_calls
        commit_calls += 1
        return original_commit()

    def track_rollback():
        nonlocal rollback_called
        rollback_called = True
        return original_rollback()

    monkeypatch.setattr(session, "flush", fail_when_event_is_pending)
    monkeypatch.setattr(session, "commit", track_commit)
    monkeypatch.setattr(session, "rollback", track_rollback)

    verifier = SessionLocal()
    try:
        with pytest.raises(SQLAlchemyError, match="workflow event flush failed"):
            service.approve_report(report_id, doctor)

        assert commit_calls == 1
        assert rollback_called is True
        session.close()
        assert verifier.get(DischargeReport, report_id).status == DischargeReportStatus.GENERATED
        assert verifier.query(WorkflowEvent).filter_by(entity_id=report_id).count() == 0
    finally:
        session.close()
        verifier.close()
        engine.dispose()
