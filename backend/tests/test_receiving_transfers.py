from datetime import datetime, timezone
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.admission import Admission, AdmissionStatus
from app.models.clinical_decision import ClinicalDecision, ClinicalDecisionStatus, ClinicalDecisionType, TransferUrgency
from app.models.hospital import Hospital
from app.models.hospital_capacity import HospitalCapacity
from app.models.patient import Patient
from app.models.transfer import Transfer, TransferStatus
from app.models.transfer_decision import TransferDecision, TransferDecisionType
from app.models.user import User
from app.models.workflow_event import WorkflowEvent


@pytest.fixture
def receiving_setup(db_session: Session):
    """Setup for testing receiving hospital operations and capacity reservations."""
    patient1 = Patient(
        first_name="Meera",
        last_name="Nair",
        patient_code="PT-1004",
        date_of_birth=datetime(1982, 3, 15, tzinfo=timezone.utc),
        gender="Female",
    )
    patient2 = Patient(
        first_name="Vikram",
        last_name="Singh",
        patient_code="PT-1007",
        date_of_birth=datetime(1968, 8, 20, tzinfo=timezone.utc),
        gender="Male",
    )
    db_session.add_all([patient1, patient2])
    db_session.flush()

    sending_hosp = Hospital(
        name="Metro Multispeciality Medical Center",
        latitude=37.7749,
        longitude=-122.4194,
        contact_number="+1-415-555-0100",
        specialties=["Cardiology", "Neurology"],
    )
    receiving_hosp = Hospital(
        name="City Heart & Neuro Institute",
        latitude=37.7550,
        longitude=-122.4300,
        contact_number="+1-415-555-0200",
        specialties=["Cardiology", "Neurology"],
    )
    db_session.add_all([sending_hosp, receiving_hosp])
    db_session.flush()

    # Configured capacity with exactly 1 available bed
    cap = HospitalCapacity(
        hospital_id=receiving_hosp.id,
        specialty="Cardiology",
        total_beds=10,
        available_beds=1,
    )
    db_session.add(cap)

    doctor = User(
        name="Dr. Asha Rao",
        email="asha.rao@metrohospital.org",
    )
    db_session.add(doctor)
    db_session.flush()

    # Admission 1
    adm1 = Admission(
        patient_id=patient1.id,
        attending_doctor_id=doctor.id,
        admission_date=datetime.now(timezone.utc),
        status=AdmissionStatus.TRANSFER_PENDING,
        primary_diagnosis="Acute Coronary Syndrome",
    )
    # Admission 2
    adm2 = Admission(
        patient_id=patient2.id,
        attending_doctor_id=doctor.id,
        admission_date=datetime.now(timezone.utc),
        status=AdmissionStatus.TRANSFER_PENDING,
        primary_diagnosis="Severe Angina",
    )
    db_session.add_all([adm1, adm2])
    db_session.flush()

    trf1 = Transfer(
        patient_id=patient1.id,
        admission_id=adm1.id,
        sending_hospital_id=sending_hosp.id,
        receiving_hospital_id=receiving_hosp.id,
        required_specialty="Cardiology",
        emergency=True,
        status=TransferStatus.AWAITING_ACCEPTANCE,
        requested_at=datetime.now(timezone.utc),
        selected_hospital_at=datetime.now(timezone.utc),
    )
    trf2 = Transfer(
        patient_id=patient2.id,
        admission_id=adm2.id,
        sending_hospital_id=sending_hosp.id,
        receiving_hospital_id=receiving_hosp.id,
        required_specialty="Cardiology",
        emergency=False,
        status=TransferStatus.AWAITING_ACCEPTANCE,
        requested_at=datetime.now(timezone.utc),
        selected_hospital_at=datetime.now(timezone.utc),
    )
    db_session.add_all([trf1, trf2])
    db_session.commit()

    return {
        "receiving_hospital": receiving_hosp,
        "capacity": cap,
        "transfer1": trf1,
        "transfer2": trf2,
    }


def test_incoming_transfers_queue_and_filter(client: TestClient, receiving_setup: dict):
    rec_hosp = receiving_setup["receiving_hospital"]

    # 1. Query queue for receiving hospital
    res = client.get(f"/api/receiving/transfers?hospital_id={rec_hosp.id}")
    assert res.status_code == status.HTTP_200_OK
    items = res.json()
    assert len(items) == 2

    # 2. Filter by emergency
    res_emerg = client.get(f"/api/receiving/transfers?hospital_id={rec_hosp.id}&emergency=true")
    assert res_emerg.status_code == status.HTTP_200_OK
    items_emerg = res_emerg.json()
    assert len(items_emerg) == 1
    assert items_emerg[0]["emergency"] is True


def test_incoming_transfer_detail_marks_packet_viewed(client: TestClient, receiving_setup: dict):
    trf1 = receiving_setup["transfer1"]

    # First prepare & send packet
    client.post(f"/api/transfers/{trf1.id}/packet")
    client.post(f"/api/transfers/{trf1.id}/packet/send")

    # Receiving staff opens detail
    res = client.get(f"/api/receiving/transfers/{trf1.id}")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["id"] == trf1.id
    assert data["packet_status"] == "viewed"


def test_accept_transfer_transactional_capacity_and_double_acceptance(client: TestClient, db_session: Session, receiving_setup: dict):
    trf1 = receiving_setup["transfer1"]
    cap = receiving_setup["capacity"]
    assert cap.available_beds == 1

    # 1. Accept transfer 1
    accept_payload = {"notes": "Cath lab prepared. Patient accepted."}
    res = client.post(f"/api/transfers/{trf1.id}/accept", json=accept_payload)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["status"] == "accepted"
    assert data["accepted_at"] is not None

    # Verify capacity decremented from 1 -> 0
    db_session.refresh(cap)
    assert cap.available_beds == 0

    # Verify TransferDecision record created
    decision = db_session.query(TransferDecision).filter(TransferDecision.transfer_id == trf1.id).first()
    assert decision is not None
    assert decision.decision == TransferDecisionType.ACCEPTED
    assert decision.reason == "Cath lab prepared. Patient accepted."

    # Verify receiving_hospital_accepted event emitted
    event = db_session.query(WorkflowEvent).filter(
        WorkflowEvent.event_type == "receiving_hospital_accepted",
        WorkflowEvent.entity_id == trf1.id,
    ).first()
    assert event is not None
    assert event.payload["remaining_available_beds"] == 0

    # 2. DOUBLE ACCEPTANCE TEST: repeating accept on already-accepted transfer must NOT decrement capacity again!
    res_double = client.post(f"/api/transfers/{trf1.id}/accept", json=accept_payload)
    assert res_double.status_code == status.HTTP_200_OK
    db_session.refresh(cap)
    assert cap.available_beds == 0  # Still 0, not -1!


def test_capacity_conflict_rejection(client: TestClient, db_session: Session, receiving_setup: dict):
    trf1 = receiving_setup["transfer1"]
    trf2 = receiving_setup["transfer2"]
    cap = receiving_setup["capacity"]
    assert cap.available_beds == 1

    # Accept transfer 1 -> uses remaining bed
    res1 = client.post(f"/api/transfers/{trf1.id}/accept")
    assert res1.status_code == status.HTTP_200_OK
    db_session.refresh(cap)
    assert cap.available_beds == 0

    # Transfer 2 attempts to accept but capacity is 0 -> 409 Conflict
    res2 = client.post(f"/api/transfers/{trf2.id}/accept")
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert "No capacity remains" in res2.json()["error"]["message"]

    db_session.refresh(cap)
    assert cap.available_beds == 0


def test_reject_transfer_and_rematch_flow(client: TestClient, db_session: Session, receiving_setup: dict):
    trf2 = receiving_setup["transfer2"]
    cap = receiving_setup["capacity"]
    initial_beds = cap.available_beds

    # 1. Reject without reason -> 422 validation error
    res_no_reason = client.post(f"/api/transfers/{trf2.id}/reject", json={"reason": ""})
    assert res_no_reason.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 2. Reject with valid reason
    reject_payload = {"reason": "No ICU beds available due to incoming emergency surgery."}
    res_reject = client.post(f"/api/transfers/{trf2.id}/reject", json=reject_payload)
    assert res_reject.status_code == status.HTTP_200_OK
    data = res_reject.json()
    assert data["status"] == "rejected"
    assert data["rejected_at"] is not None

    # Verify capacity NOT changed
    db_session.refresh(cap)
    assert cap.available_beds == initial_beds

    # Verify TransferDecision stored
    decision = db_session.query(TransferDecision).filter(
        TransferDecision.transfer_id == trf2.id,
        TransferDecision.decision == TransferDecisionType.REJECTED,
    ).first()
    assert decision is not None
    assert decision.reason == "No ICU beds available due to incoming emergency surgery."

    # Verify receiving_hospital_rejected event
    event = db_session.query(WorkflowEvent).filter(
        WorkflowEvent.event_type == "receiving_hospital_rejected",
        WorkflowEvent.entity_id == trf2.id,
    ).first()
    assert event is not None

    # 3. Sending Doctor triggers REMATCH
    res_rematch = client.post(f"/api/transfers/{trf2.id}/rematch")
    assert res_rematch.status_code == status.HTTP_200_OK
    rematch_data = res_rematch.json()
    assert rematch_data["status"] == "matching"
    assert rematch_data["receiving_hospital_id"] is None

    # Verify historical decision is preserved
    decisions_count = db_session.query(TransferDecision).filter(TransferDecision.transfer_id == trf2.id).count()
    assert decisions_count == 1
