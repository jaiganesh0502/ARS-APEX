from copy import deepcopy
from datetime import datetime, timezone

import pytest

from app.db.seed import seed_database
from app.models import (
    Admission,
    AdmissionStatus,
    Bed,
    BedStatus,
    DischargeReport,
    DischargeReportStatus,
    MedicalRecord,
    Medication,
    Patient,
    Vital,
    WorkflowEvent,
)


TURNOVER_EVENT_TYPES = (
    "bed_release_started",
    "patient_departed_bed",
    "bed_cleaning_started",
    "bed_available",
)


def _turnover_event(
    event_type, bed, admission, patient, report, previous_status, new_status,
    *, trusted_provenance=True,
):
    event_time = datetime(2026, 8, 19, 10, tzinfo=timezone.utc)
    payload = {
        "bed_id": bed.id,
        "patient_id": patient.id,
        "admission_id": admission.id,
        "previous_status": previous_status.value,
        "new_status": new_status.value,
        "timestamp": event_time.isoformat(),
        "actor_user_id": admission.attending_doctor_id,
        "actor_name": "Dr. Asha Rao",
        "actor_role": "doctor",
    }
    if event_type == "bed_release_started":
        payload["report_id"] = report.id
    return WorkflowEvent(
        event_type=event_type,
        entity_type="bed",
        entity_id=bed.id,
        status="pending",
        trusted_provenance=trusted_provenance,
        payload=payload,
        created_at=event_time,
    )


def _seeded_release_case(db_session):
    seed_database(db_session)
    patient = db_session.query(Patient).filter(Patient.patient_code == "PT-1006").one()
    admission = db_session.query(Admission).filter(Admission.patient_id == patient.id).one()
    bed = db_session.get(Bed, admission.bed_id)
    report = db_session.query(DischargeReport).filter_by(admission_id=admission.id).first()
    if report is None:
        approved_at = datetime(2026, 8, 19, 9, tzinfo=timezone.utc)
        report = DischargeReport(
            patient_id=patient.id,
            admission_id=admission.id,
            generated_content="Seed lineage report",
            generation_provider="test",
            generation_model="test-model",
            status=DischargeReportStatus.APPROVED,
            approved_by=admission.attending_doctor_id,
            approved_at=approved_at,
        )
        db_session.add(report)
        db_session.flush()
    return patient, admission, bed, report


def _counts(db_session):
    return tuple(
        db_session.query(model).count()
        for model in (Patient, Admission, Bed, MedicalRecord, Medication, Vital, WorkflowEvent)
    )


def _snapshot(db_session, bed, admission):
    events = (
        db_session.query(WorkflowEvent)
        .filter(WorkflowEvent.entity_type == "bed", WorkflowEvent.entity_id == bed.id)
        .order_by(WorkflowEvent.id)
        .all()
    )
    return {
        "bed": (bed.status, bed.current_patient_id),
        "admission": (admission.status, admission.bed_id),
        "events": [
            (
                event.id,
                event.event_type,
                event.status,
                event.trusted_provenance,
                deepcopy(event.payload),
                event.created_at,
            )
            for event in events
        ],
        "counts": _counts(db_session),
    }


def test_seed_is_idempotent_and_complete(db_session):
    seed_database(db_session)
    first_counts = (
        db_session.query(Patient).filter(Patient.patient_code.like("PT-100%")).count(),
        db_session.query(Admission).count(),
        db_session.query(MedicalRecord).count(),
        db_session.query(Medication).count(),
        db_session.query(Vital).count(),
    )

    seed_database(db_session)
    second_counts = (
        db_session.query(Patient).filter(Patient.patient_code.like("PT-100%")).count(),
        db_session.query(Admission).count(),
        db_session.query(MedicalRecord).count(),
        db_session.query(Medication).count(),
        db_session.query(Vital).count(),
    )

    assert first_counts[0] == 8
    assert first_counts[1] == 8
    assert first_counts[2] == 8
    assert first_counts[4] >= 16
    assert second_counts == first_counts


@pytest.mark.parametrize("turnover_state", ["occupied", "vacating", "cleaning", "available"])
def test_reseed_preserves_every_existing_turnover_state_and_events(db_session, turnover_state):
    patient, admission, bed, report = _seeded_release_case(db_session)

    # A newly seeded discharging admission has not started operational release yet.
    assert admission.status == AdmissionStatus.DISCHARGING
    assert bed.status == BedStatus.OCCUPIED
    assert bed.current_patient_id == patient.id

    if turnover_state in {"vacating", "cleaning", "available"}:
        bed.status = BedStatus.VACATING
        db_session.add(_turnover_event(
            "bed_release_started", bed, admission, patient, report,
            BedStatus.OCCUPIED, BedStatus.VACATING,
        ))
    if turnover_state in {"cleaning", "available"}:
        bed.status = BedStatus.CLEANING
        bed.current_patient_id = None
        admission.status = AdmissionStatus.DISCHARGED
        db_session.add_all([
            _turnover_event(
                "patient_departed_bed", bed, admission, patient, report,
                BedStatus.VACATING, BedStatus.CLEANING,
            ),
            _turnover_event(
                "bed_cleaning_started", bed, admission, patient, report,
                BedStatus.VACATING, BedStatus.CLEANING,
            ),
        ])
    if turnover_state == "available":
        bed.status = BedStatus.AVAILABLE
        db_session.add(_turnover_event(
            "bed_available", bed, admission, patient, report,
            BedStatus.CLEANING, BedStatus.AVAILABLE,
        ))

    db_session.flush()
    before = _snapshot(db_session, bed, admission)

    seed_database(db_session)
    db_session.refresh(bed)
    db_session.refresh(admission)

    assert _snapshot(db_session, bed, admission) == before


def test_reseed_rejects_vacating_seeded_bed_without_valid_release_lineage(db_session):
    patient, admission, bed, _report = _seeded_release_case(db_session)
    bed.status = BedStatus.VACATING
    db_session.add(WorkflowEvent(
        event_type="bed_release_started",
        entity_type="bed",
        entity_id=bed.id,
        status="pending",
        payload={
            "bed_id": bed.id,
            "patient_id": patient.id,
            "admission_id": admission.id + 999,
            "previous_status": BedStatus.OCCUPIED.value,
            "new_status": BedStatus.VACATING.value,
        },
    ))
    db_session.commit()
    before = _snapshot(db_session, bed, admission)

    with pytest.raises(RuntimeError, match="valid bed_release_started lineage"):
        seed_database(db_session)

    db_session.refresh(bed)
    db_session.refresh(admission)
    assert _snapshot(db_session, bed, admission) == before


def test_reseed_rejects_exact_untrusted_release_lineage(db_session):
    """A perfect valid-shaped legacy event must not establish seed lineage."""
    patient, admission, bed, report = _seeded_release_case(db_session)
    bed.status = BedStatus.VACATING
    db_session.add(_turnover_event(
        "bed_release_started",
        bed,
        admission,
        patient,
        report,
        BedStatus.OCCUPIED,
        BedStatus.VACATING,
        trusted_provenance=False,
    ))
    db_session.commit()
    before = _snapshot(db_session, bed, admission)

    with pytest.raises(RuntimeError, match="valid bed_release_started lineage"):
        seed_database(db_session)

    db_session.refresh(bed)
    db_session.refresh(admission)
    assert _snapshot(db_session, bed, admission) == before
