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
from app.models.transfer_packet import TransferPacket, TransferPacketStatus
from app.models.user import User
from app.models.workflow_event import WorkflowEvent
from app.models.medication import Medication
from app.models.vital import Vital
from app.services.transfer_packet_service import TransferPacketService


@pytest.fixture
def transfer_setup(db_session: Session):
    """Fixture creating patient, admission, hospitals, capacities, confirmed transfer decision, and transfer case."""
    patient = Patient(
        first_name="Ramesh",
        last_name="Kumar",
        patient_code="PT-2001",
        date_of_birth=datetime(1975, 4, 12, tzinfo=timezone.utc),
        gender="Male",
        blood_group="O+",
        phone="+91-9876543210",
        emergency_contact="+91-9876543211",
    )
    db_session.add(patient)
    db_session.flush()

    sending_hospital = Hospital(
        name="Metro Multispeciality Medical Center",
        latitude=37.7749,
        longitude=-122.4194,
        contact_number="+1-415-555-0100",
        specialties=["Cardiology", "Neurology"],
    )
    receiving_hospital = Hospital(
        name="City Heart & Neuro Institute",
        latitude=37.7550,
        longitude=-122.4300,
        contact_number="+1-415-555-0200",
        specialties=["Cardiology", "Neurology"],
    )
    db_session.add_all([sending_hospital, receiving_hospital])
    db_session.flush()

    # Add capacity
    cap = HospitalCapacity(
        hospital_id=receiving_hospital.id,
        specialty="Cardiology",
        total_beds=10,
        available_beds=2,
    )
    db_session.add(cap)

    doctor = User(
        name="Dr. Asha Rao",
        email="asha.rao@metrohospital.org",
    )
    db_session.add(doctor)
    db_session.flush()

    admission = Admission(
        patient_id=patient.id,
        attending_doctor_id=doctor.id,
        admission_date=datetime.now(timezone.utc),
        status=AdmissionStatus.TRANSFER_PENDING,
        primary_diagnosis="Acute Coronary Syndrome",
    )
    db_session.add(admission)
    db_session.flush()

    med = Medication(
        patient_id=patient.id,
        admission_id=admission.id,
        medication_name="Aspirin",
        dosage="75mg",
        frequency="Once daily",
        route="Oral",
        start_date=datetime.now(timezone.utc),
    )
    vital = Vital(
        patient_id=patient.id,
        admission_id=admission.id,
        temperature=36.8,
        heart_rate=78,
        blood_pressure_systolic=120,
        blood_pressure_diastolic=80,
        oxygen_saturation=98,
        recorded_at=datetime.now(timezone.utc),
    )
    db_session.add_all([med, vital])

    decision = ClinicalDecision(
        patient_id=patient.id,
        admission_id=admission.id,
        decision_type=ClinicalDecisionType.TRANSFER,
        status=ClinicalDecisionStatus.CONFIRMED,
        reason="Needs urgent cardiac catheterization unavailable locally.",
        required_specialty="Cardiology",
        transfer_urgency=TransferUrgency.EMERGENCY,
        decided_by=doctor.id,
        decided_at=datetime.now(timezone.utc),
    )
    db_session.add(decision)
    db_session.flush()

    transfer = Transfer(
        patient_id=patient.id,
        admission_id=admission.id,
        clinical_decision_id=decision.id,
        sending_hospital_id=sending_hospital.id,
        receiving_hospital_id=receiving_hospital.id,
        required_specialty="Cardiology",
        emergency=True,
        status=TransferStatus.AWAITING_ACCEPTANCE,
        requested_at=datetime.now(timezone.utc),
        selected_hospital_at=datetime.now(timezone.utc),
    )
    db_session.add(transfer)
    db_session.commit()

    return {
        "patient": patient,
        "admission": admission,
        "sending_hospital": sending_hospital,
        "receiving_hospital": receiving_hospital,
        "transfer": transfer,
    }


def test_prepare_transfer_packet_success(client: TestClient, db_session: Session, transfer_setup: dict):
    transfer = transfer_setup["transfer"]

    response = client.post(f"/api/transfers/{transfer.id}/packet")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["transfer_id"] == transfer.id
    assert data["status"] == "prepared"
    assert data["packet_content"]["primary_diagnosis"] == "Acute Coronary Syndrome"
    assert data["packet_content"]["required_specialty"] == "Cardiology"
    assert data["packet_content"]["urgency"] == "emergency"
    assert data["packet_content"]["patient_summary"]["patient_code"] == "PT-2001"
    assert len(data["packet_content"]["current_medications"]) == 1
    assert data["packet_content"]["current_medications"][0]["medication_name"] == "Aspirin"
    assert len(data["packet_content"]["recent_vitals"]) == 1


def test_prepare_packet_fails_without_receiving_hospital(client: TestClient, db_session: Session, transfer_setup: dict):
    transfer = transfer_setup["transfer"]
    transfer.receiving_hospital_id = None
    transfer.status = TransferStatus.MATCHING
    db_session.commit()

    response = client.post(f"/api/transfers/{transfer.id}/packet")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "receiving hospital" in response.json()["error"]["message"].lower()


def test_prepare_packet_idempotency(client: TestClient, db_session: Session, transfer_setup: dict):
    transfer = transfer_setup["transfer"]

    res1 = client.post(f"/api/transfers/{transfer.id}/packet")
    assert res1.status_code == status.HTTP_200_OK
    packet1_id = res1.json()["id"]

    res2 = client.post(f"/api/transfers/{transfer.id}/packet")
    assert res2.status_code == status.HTTP_200_OK
    packet2_id = res2.json()["id"]

    assert packet1_id == packet2_id
    assert db_session.query(TransferPacket).filter(TransferPacket.transfer_id == transfer.id).count() == 1


def test_send_and_view_transfer_packet(client: TestClient, db_session: Session, transfer_setup: dict):
    transfer = transfer_setup["transfer"]

    # 1. Send packet
    send_res = client.post(f"/api/transfers/{transfer.id}/packet/send")
    assert send_res.status_code == status.HTTP_200_OK
    send_data = send_res.json()
    assert send_data["status"] == "sent"
    assert send_data["sent_at"] is not None

    # Check workflow event
    event = (
        db_session.query(WorkflowEvent)
        .filter(
            WorkflowEvent.event_type == "transfer_packet_sent",
            WorkflowEvent.entity_id == transfer.id,
        )
        .first()
    )
    assert event is not None
    assert event.payload["transfer_id"] == transfer.id

    # 2. View packet (mark_viewed=True)
    get_res = client.get(f"/api/transfers/{transfer.id}/packet?mark_viewed=true")
    assert get_res.status_code == status.HTTP_200_OK
    get_data = get_res.json()
    assert get_data["status"] == "viewed"
    assert get_data["viewed_at"] is not None

    # Check workflow event
    view_event = (
        db_session.query(WorkflowEvent)
        .filter(
            WorkflowEvent.event_type == "transfer_packet_viewed",
            WorkflowEvent.entity_id == transfer.id,
        )
        .first()
    )
    assert view_event is not None
