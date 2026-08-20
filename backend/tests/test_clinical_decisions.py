from datetime import date, datetime, timezone

import pytest

from app.models import Admission, AdmissionStatus, Bed, BedStatus, Patient, User, UserRole, WorkflowEvent


@pytest.fixture
def admitted_case(db_session):
    doctor = User(name="Dr. Decision Demo", email="decision.doctor@example.test", role=UserRole.DOCTOR)
    patient = Patient(
        patient_code="DEC-1001", first_name="Ira", last_name="Synthetic",
        date_of_birth=date(1980, 1, 1), gender="Female",
    )
    bed = Bed(ward="General Medicine", bed_number="DEC-01", status=BedStatus.OCCUPIED)
    db_session.add_all([doctor, patient, bed])
    db_session.flush()
    admission = Admission(
        patient_id=patient.id,
        admission_date=datetime(2026, 8, 19, tzinfo=timezone.utc),
        primary_diagnosis="Synthetic clinical decision case",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.ADMITTED,
        bed_id=bed.id,
    )
    db_session.add(admission)
    db_session.flush()
    bed.current_patient_id = patient.id
    db_session.commit()
    return {"doctor": doctor, "patient": patient, "bed": bed, "admission": admission}


def _create(client, admission_id, payload):
    return client.post(f"/api/admissions/{admission_id}/clinical-decision", json=payload)


def test_create_discharge_decision(client, admitted_case):
    response = _create(client, admitted_case["admission"].id, {
        "decision_type": "discharge",
        "reason": " Patient clinically stable for discharge. ",
        "notes": "Continue oral medication at home.",
    })

    assert response.status_code == 201
    payload = response.json()
    assert payload["decision_type"] == "discharge"
    assert payload["status"] == "draft"
    assert payload["reason"] == "Patient clinically stable for discharge."
    assert payload["transfer_urgency"] is None
    assert payload["required_specialty"] is None
    assert payload["decided_by_name"] == "Dr. Decision Demo"


@pytest.mark.parametrize("urgency", ["emergency", "non_emergency"])
def test_create_transfer_decision(client, admitted_case, urgency):
    response = _create(client, admitted_case["admission"].id, {
        "decision_type": "transfer",
        "transfer_urgency": urgency,
        "required_specialty": "Cardiology",
        "reason": "Requires PCI-capable cardiac center",
    })

    assert response.status_code == 201
    assert response.json()["transfer_urgency"] == urgency
    assert response.json()["required_specialty"] == "Cardiology"


@pytest.mark.parametrize("missing_field", ["transfer_urgency", "required_specialty"])
def test_transfer_requires_urgency_and_specialty(client, admitted_case, missing_field):
    payload = {
        "decision_type": "transfer",
        "transfer_urgency": "emergency",
        "required_specialty": "Cardiology",
        "reason": "Requires specialist care",
    }
    payload.pop(missing_field)

    response = _create(client, admitted_case["admission"].id, payload)
    assert response.status_code == 422


def test_discharge_rejects_transfer_fields(client, admitted_case):
    response = _create(client, admitted_case["admission"].id, {
        "decision_type": "discharge",
        "transfer_urgency": "emergency",
        "reason": "Stable",
    })
    assert response.status_code == 422


def test_unknown_admission_returns_404(client, admitted_case):
    response = _create(client, 999999, {"decision_type": "discharge", "reason": "Stable"})
    assert response.status_code == 404


def test_get_and_update_draft(client, admitted_case):
    created = _create(client, admitted_case["admission"].id, {
        "decision_type": "discharge", "reason": "Initial reason"
    }).json()

    fetched = client.get(f"/api/admissions/{admitted_case['admission'].id}/clinical-decision")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]

    updated = client.put(f"/api/clinical-decisions/{created['id']}", json={
        "decision_type": "discharge", "reason": "Updated clinical reason", "notes": "Reviewed"
    })
    assert updated.status_code == 200
    assert updated.json()["reason"] == "Updated clinical reason"


def test_get_missing_decision_returns_404(client, admitted_case):
    response = client.get(f"/api/admissions/{admitted_case['admission'].id}/clinical-decision")
    assert response.status_code == 404


def test_duplicate_active_decision_is_rejected(client, admitted_case):
    admission_id = admitted_case["admission"].id
    first = _create(client, admission_id, {"decision_type": "discharge", "reason": "Stable"})
    second = _create(client, admission_id, {"decision_type": "discharge", "reason": "Again"})
    assert first.status_code == 201
    assert second.status_code == 409


def test_confirm_discharge_transitions_admission_and_audits(client, db_session, admitted_case):
    case = admitted_case
    created = _create(client, case["admission"].id, {
        "decision_type": "discharge", "reason": "Stable for discharge"
    }).json()

    response = client.post(f"/api/clinical-decisions/{created['id']}/confirm")
    db_session.refresh(case["admission"])
    db_session.refresh(case["bed"])

    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"
    assert response.json()["decided_at"] is not None
    assert case["admission"].status == AdmissionStatus.DISCHARGING
    assert case["bed"].status == BedStatus.OCCUPIED
    event = db_session.query(WorkflowEvent).filter_by(entity_id=created["id"]).one()
    assert event.event_type == "clinical_discharge_decision_confirmed"
    assert event.payload["decision_type"] == "discharge"
    assert getattr(event, "trusted_provenance", None) is True


def test_confirm_transfer_transitions_admission_and_audits(client, db_session, admitted_case):
    case = admitted_case
    created = _create(client, case["admission"].id, {
        "decision_type": "transfer", "transfer_urgency": "emergency",
        "required_specialty": "Cardiology", "reason": "Requires PCI"
    }).json()

    response = client.post(f"/api/clinical-decisions/{created['id']}/confirm")
    db_session.refresh(case["admission"])
    db_session.refresh(case["bed"])

    assert response.status_code == 200
    assert case["admission"].status == AdmissionStatus.TRANSFER_PENDING
    assert case["bed"].status == BedStatus.OCCUPIED
    event = db_session.query(WorkflowEvent).filter_by(entity_id=created["id"]).one()
    assert event.event_type == "clinical_transfer_decision_confirmed"
    assert event.payload["transfer_urgency"] == "emergency"
    assert getattr(event, "trusted_provenance", None) is True


def test_confirmed_decision_cannot_be_updated_or_confirmed_twice(client, admitted_case):
    created = _create(client, admitted_case["admission"].id, {
        "decision_type": "discharge", "reason": "Stable"
    }).json()
    assert client.post(f"/api/clinical-decisions/{created['id']}/confirm").status_code == 200
    assert client.put(f"/api/clinical-decisions/{created['id']}", json={
        "decision_type": "discharge", "reason": "Changed"
    }).status_code == 409
    assert client.post(f"/api/clinical-decisions/{created['id']}/confirm").status_code == 409
