from datetime import date, datetime, timezone
import pytest
from app.models.admission import Admission, AdmissionStatus
from app.models.bed import Bed, BedStatus
from app.models.clinical_decision import (
    ClinicalDecision,
    ClinicalDecisionStatus,
    ClinicalDecisionType,
    TransferUrgency,
)
from app.models.hospital import Hospital
from app.models.hospital_capacity import HospitalCapacity
from app.models.patient import Patient
from app.models.transfer import Transfer, TransferStatus
from app.models.user import User, UserRole
from app.models.workflow_event import WorkflowEvent


@pytest.fixture
def transfer_scenario(db_session):
    db_session.query(HospitalCapacity).delete()
    db_session.query(Hospital).delete()
    db_session.flush()

    # Setup Doctor, Patient, Bed, Admission, Sending Hospital, Partner Hospitals
    doctor = User(name="Dr. Sarah Connor", email="sarah.connor@hospital.test", role=UserRole.DOCTOR)
    patient = Patient(
        patient_code="PT-TRF-001",
        first_name="Marcus",
        last_name="Sterling",
        date_of_birth=date(1978, 5, 12),
        gender="Male",
        phone="+1-555-0199",
    )
    bed = Bed(ward="Cardiology", bed_number="CARD-01", status=BedStatus.OCCUPIED)
    db_session.add_all([doctor, patient, bed])
    db_session.flush()

    bed.current_patient_id = patient.id

    admission = Admission(
        patient_id=patient.id,
        primary_diagnosis="Acute Coronary Syndrome",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.TRANSFER_PENDING,
        bed_id=bed.id,
    )
    db_session.add(admission)
    db_session.flush()

    sending_hospital = Hospital(
        name="Metro Multispeciality Medical Center",
        latitude=37.7749,
        longitude=-122.4194,
        specialties=["Cardiology", "Neurology", "Critical Care"],
        contact_number="+1-415-555-0100",
    )
    receiving_hospital = Hospital(
        name="City Heart & Neuro Institute",
        latitude=37.7550,
        longitude=-122.4300,
        specialties=["Cardiology", "Neurology", "Critical Care"],
        contact_number="+1-415-555-0302",
    )
    unmatched_hospital = Hospital(
        name="Green Valley Orthopedics",
        latitude=37.7885,
        longitude=-122.4075,
        specialties=["Orthopedics"],
        contact_number="+1-415-555-0201",
    )
    full_hospital = Hospital(
        name="Full Cardiac Clinic",
        latitude=37.7600,
        longitude=-122.4200,
        specialties=["Cardiology"],
        contact_number="+1-415-555-0999",
    )
    db_session.add_all([sending_hospital, receiving_hospital, unmatched_hospital, full_hospital])
    db_session.flush()

    cap_rec = HospitalCapacity(hospital_id=receiving_hospital.id, specialty="Cardiology", total_beds=12, available_beds=3)
    cap_unm = HospitalCapacity(hospital_id=unmatched_hospital.id, specialty="Orthopedics", total_beds=10, available_beds=4)
    cap_full = HospitalCapacity(hospital_id=full_hospital.id, specialty="Cardiology", total_beds=10, available_beds=0)
    db_session.add_all([cap_rec, cap_unm, cap_full])
    db_session.flush()

    decision = ClinicalDecision(
        patient_id=patient.id,
        admission_id=admission.id,
        decision_type=ClinicalDecisionType.TRANSFER,
        transfer_urgency=TransferUrgency.EMERGENCY,
        reason="Acute coronary syndrome requiring urgent catheterization.",
        required_specialty="Cardiology",
        decided_by=doctor.id,
        decided_at=datetime.now(timezone.utc),
        status=ClinicalDecisionStatus.CONFIRMED,
    )
    db_session.add(decision)
    db_session.commit()

    return {
        "doctor": doctor,
        "patient": patient,
        "admission": admission,
        "decision": decision,
        "sending_hospital": sending_hospital,
        "receiving_hospital": receiving_hospital,
        "unmatched_hospital": unmatched_hospital,
        "full_hospital": full_hospital,
        "capacity_receiving": cap_rec,
    }


def test_create_transfer_from_confirmed_decision(client, transfer_scenario, db_session):
    adm_id = transfer_scenario["admission"].id
    response = client.post(f"/api/admissions/{adm_id}/transfer")

    assert response.status_code == 201
    data = response.json()
    assert data["admission_id"] == adm_id
    assert data["patient_id"] == transfer_scenario["patient"].id
    assert data["required_specialty"] == "Cardiology"
    assert data["emergency"] is True
    assert data["status"] == "matching"
    assert data["receiving_hospital_id"] is None

    # Verify workflow event
    event = (
        db_session.query(WorkflowEvent)
        .filter(WorkflowEvent.entity_type == "transfer", WorkflowEvent.event_type == "transfer_matching_started")
        .first()
    )
    assert event is not None
    assert event.payload["transfer_id"] == data["id"]
    assert event.payload["required_specialty"] == "Cardiology"
    assert event.payload["emergency"] is True
    assert event.trusted_provenance is True


def test_duplicate_active_transfer_returns_existing(client, transfer_scenario):
    adm_id = transfer_scenario["admission"].id
    first = client.post(f"/api/admissions/{adm_id}/transfer")
    assert first.status_code == 201
    first_data = first.json()

    second = client.post(f"/api/admissions/{adm_id}/transfer")
    assert second.status_code == 201
    second_data = second.json()

    assert second_data["id"] == first_data["id"]


def _err(res):
    body = res.json()
    return (body.get("detail") or body.get("error", {}).get("message") or "").lower()


def test_discharge_patient_cannot_create_transfer(client, transfer_scenario, db_session):
    # Change decision to discharge
    decision = transfer_scenario["decision"]
    decision.decision_type = ClinicalDecisionType.DISCHARGE
    transfer_scenario["admission"].status = AdmissionStatus.DISCHARGING
    db_session.commit()

    adm_id = transfer_scenario["admission"].id
    response = client.post(f"/api/admissions/{adm_id}/transfer")

    assert response.status_code in (400, 409)
    assert "discharge" in _err(response)


def test_transfer_creation_fails_without_confirmed_decision(client, db_session):
    patient = Patient(patient_code="PT-NO-DEC", first_name="No", last_name="Decision", date_of_birth=date(1990, 1, 1), gender="Male")
    user = User(name="Dr. Test", email="dr.test@hospital.test", role=UserRole.DOCTOR)
    db_session.add_all([patient, user])
    db_session.flush()

    admission = Admission(patient_id=patient.id, primary_diagnosis="Test", attending_doctor_id=user.id, status=AdmissionStatus.TRANSFER_PENDING)
    db_session.add(admission)
    db_session.commit()

    response = client.post(f"/api/admissions/{admission.id}/transfer")
    assert response.status_code == 409
    assert "confirmed clinical transfer decision" in _err(response)


def test_get_hospital_matches_for_transfer(client, transfer_scenario):
    adm_id = transfer_scenario["admission"].id
    create_res = client.post(f"/api/admissions/{adm_id}/transfer")
    transfer_id = create_res.json()["id"]

    matches_res = client.get(f"/api/transfers/{transfer_id}/matches")
    assert matches_res.status_code == 200
    matches = matches_res.json()

    # Only City Heart & Neuro Institute matches (Green Valley has no Cardiology, Full Clinic has 0 beds)
    assert len(matches) == 1
    assert matches[0]["hospital_id"] == transfer_scenario["receiving_hospital"].id
    assert matches[0]["available_beds"] == 3
    assert matches[0]["is_recommended"] is True
    assert matches[0]["match_score"] > 0
    assert len(matches[0]["match_reasons"]) >= 2


def test_doctor_can_select_valid_hospital(client, transfer_scenario, db_session):
    adm_id = transfer_scenario["admission"].id
    create_res = client.post(f"/api/admissions/{adm_id}/transfer")
    transfer_id = create_res.json()["id"]
    rec_hosp_id = transfer_scenario["receiving_hospital"].id

    initial_beds = transfer_scenario["capacity_receiving"].available_beds

    select_res = client.post(
        f"/api/transfers/{transfer_id}/select-hospital",
        json={"hospital_id": rec_hosp_id},
    )
    assert select_res.status_code == 200
    data = select_res.json()
    assert data["receiving_hospital_id"] == rec_hosp_id
    assert data["status"] == "awaiting_acceptance"
    assert data["selected_hospital_at"] is not None

    # Capacity must NOT be decremented yet in Feature 5
    db_session.expire_all()
    updated_cap = db_session.get(HospitalCapacity, transfer_scenario["capacity_receiving"].id)
    assert updated_cap.available_beds == initial_beds

    # Verify workflow event receiving_hospital_selected
    event = (
        db_session.query(WorkflowEvent)
        .filter(WorkflowEvent.entity_type == "transfer", WorkflowEvent.event_type == "receiving_hospital_selected")
        .first()
    )
    assert event is not None
    assert event.payload["transfer_id"] == transfer_id
    assert event.payload["hospital_id"] == rec_hosp_id
    assert event.payload["status"] == "awaiting_acceptance"
    assert event.trusted_provenance is True


def test_cannot_select_hospital_without_required_specialty(client, transfer_scenario):
    adm_id = transfer_scenario["admission"].id
    create_res = client.post(f"/api/admissions/{adm_id}/transfer")
    transfer_id = create_res.json()["id"]
    unmatched_id = transfer_scenario["unmatched_hospital"].id

    res = client.post(
        f"/api/transfers/{transfer_id}/select-hospital",
        json={"hospital_id": unmatched_id},
    )
    assert res.status_code == 400
    assert "does not support the required specialty" in _err(res)


def test_cannot_select_hospital_with_zero_availability(client, transfer_scenario):
    adm_id = transfer_scenario["admission"].id
    create_res = client.post(f"/api/admissions/{adm_id}/transfer")
    transfer_id = create_res.json()["id"]
    full_id = transfer_scenario["full_hospital"].id

    res = client.post(
        f"/api/transfers/{transfer_id}/select-hospital",
        json={"hospital_id": full_id},
    )
    assert res.status_code in (400, 409)
    assert "0 available beds" in _err(res)


def test_transfer_list_and_detail_endpoints(client, transfer_scenario):
    adm_id = transfer_scenario["admission"].id
    create_res = client.post(f"/api/admissions/{adm_id}/transfer")
    transfer_id = create_res.json()["id"]

    # List
    list_res = client.get("/api/transfers?emergency=true")
    assert list_res.status_code == 200
    items = list_res.json()
    assert any(item["id"] == transfer_id for item in items)

    # Detail
    detail_res = client.get(f"/api/transfers/{transfer_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == transfer_id
    assert detail["patient_name"] == "Marcus Sterling"
    assert detail["required_specialty"] == "Cardiology"
    assert detail["primary_diagnosis"] == "Acute Coronary Syndrome"
    assert detail["emergency"] is True
