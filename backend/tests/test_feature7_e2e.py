import pytest
from datetime import datetime, timezone
from fastapi import HTTPException

from app.models.admission import Admission, AdmissionStatus
from app.models.ambulance_dispatch import AmbulanceDispatch, AmbulanceStatus
from app.models.bed import Bed, BedStatus
from app.models.clinical_decision import ClinicalDecision, ClinicalDecisionType, ClinicalDecisionStatus
from app.models.hospital import Hospital
from app.models.hospital_capacity import HospitalCapacity
from app.models.patient import Patient
from app.models.transfer import Transfer, TransferStatus
from app.models.user import User, UserRole
from app.models.workflow_event import WorkflowEvent
from app.services.ambulance_dispatch_service import AmbulanceDispatchService
from app.services.clinical_decision_service import ClinicalDecisionService
from app.services.receiving_transfer_service import ReceivingTransferService
from app.services.transfer_packet_service import TransferPacketService
from app.services.transfer_service import TransferService


def test_feature7_full_end_to_end_lifecycle(db_session):
    """
    Test full end-to-end clinical transfer handoff, hospital matching, packet delivery,
    receiving acceptance, bed reservation, ambulance dispatch, simulated ETA tracking,
    sending-bed turnover on patient departure, and transfer completion.
    """
    # 1. Setup attending physician and hospitals
    doctor = User(
        name="Dr. Asha Rao",
        email="asha.e2e@metrohospital.org",
        role=UserRole.DOCTOR,
    )
    db_session.add(doctor)
    db_session.flush()

    sending_hosp = Hospital(
        name="Metro Multispeciality Medical Center",
        latitude=13.0827,
        longitude=80.2707,
        specialties=["Neurology", "Cardiology"],
        contact_number="+91-44-1234-5678",
    )
    receiving_hosp = Hospital(
        name="City Heart & Neuro Institute",
        latitude=13.0400,
        longitude=80.2500,
        specialties=["Neurology"],
        contact_number="+91-44-9876-5432",
    )
    db_session.add_all([sending_hosp, receiving_hosp])
    db_session.flush()

    # Receiving hospital has 2 available beds for Neurology
    db_session.add(HospitalCapacity(
        hospital_id=receiving_hosp.id,
        specialty="Neurology",
        total_beds=10,
        available_beds=2,
    ))

    # 2. Patient Profile & Admission with occupied bed
    patient = Patient(
        patient_code="PT-E2E-001",
        first_name="Meera",
        last_name="Nair",
        date_of_birth=datetime(1982, 3, 15).date(),
        gender="Female",
        blood_group="B+",
    )
    db_session.add(patient)
    db_session.flush()

    bed = Bed(
        bed_number="NEU-E2E-01",
        ward="Neurology Intensive Care",
        status=BedStatus.OCCUPIED,
        current_patient_id=patient.id,
    )
    db_session.add(bed)
    db_session.flush()

    admission = Admission(
        patient_id=patient.id,
        primary_diagnosis="Acute Ischemic Stroke",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.ADMITTED,
        bed_id=bed.id,
    )
    db_session.add(admission)
    db_session.flush()

    # 3. Doctor Confirms Clinical Decision: Transfer (Emergency, Neurology)
    from app.schemas.clinical_decision import ClinicalDecisionPayload
    decision_svc = ClinicalDecisionService(db_session)
    payload = ClinicalDecisionPayload(
        decision_type=ClinicalDecisionType.TRANSFER,
        transfer_urgency="emergency",
        required_specialty="Neurology",
        reason="Requires comprehensive stroke center for endovascular thrombectomy.",
    )
    decision = decision_svc.create_draft(
        admission_id=admission.id,
        payload=payload,
        doctor=doctor,
    )
    decision = decision_svc.confirm(decision.id)
    db_session.refresh(admission)
    assert admission.status == AdmissionStatus.TRANSFER_PENDING

    # 4. Transfer Case Created & Hospital Matching
    trf_svc = TransferService(db_session)
    transfer = trf_svc.create_or_get_transfer_for_admission(admission.id, requesting_user=doctor)
    assert transfer.status == TransferStatus.MATCHING
    assert transfer.emergency is True

    matches = trf_svc.get_matches_for_transfer(transfer.id)
    assert len(matches) > 0
    assert matches[0].hospital_id == receiving_hosp.id

    # 5. Doctor Selects Receiving Hospital
    transfer = trf_svc.select_receiving_hospital(transfer.id, receiving_hosp.id, selecting_user=doctor)
    assert transfer.status == TransferStatus.AWAITING_ACCEPTANCE
    assert transfer.receiving_hospital_id == receiving_hosp.id

    # 6. Transfer Packet Prepared & Sent
    pkt_svc = TransferPacketService(db_session)
    packet = pkt_svc.prepare_packet(transfer.id)
    assert packet.status.value in ("prepared", "sent")
    if packet.status.value != "sent":
        packet = pkt_svc.send_packet(transfer.id, sender_user=doctor)
    assert packet.status.value == "sent"

    # 7. Receiving Hospital Reviews & Accepts
    rec_svc = ReceivingTransferService(db_session)
    detail = rec_svc.get_incoming_transfer_detail(transfer.id, mark_viewed=True)
    assert detail.packet_status == "viewed"

    transfer = rec_svc.accept_transfer(transfer.id, notes="Neuro ICU Bed 3 Held", decided_by_user=doctor)
    assert transfer.status in (TransferStatus.ACCEPTED, TransferStatus.AMBULANCE_REQUESTED)

    # Verify 1 bed slot decremented (2 -> 1)
    cap = db_session.query(HospitalCapacity).filter(
        HospitalCapacity.hospital_id == receiving_hosp.id,
        HospitalCapacity.specialty == "Neurology"
    ).first()
    assert cap.available_beds == 1

    # 8. Ambulance Dispatch Requested
    amb_svc = AmbulanceDispatchService(db_session)
    dispatch = amb_svc.dispatch_ambulance(transfer.id, requesting_user=doctor)
    assert dispatch.status == AmbulanceStatus.REQUESTED
    assert dispatch.dispatch_reference.startswith("AMB-")
    assert dispatch.distance_km > 0
    assert dispatch.estimated_duration_minutes > 0
    assert dispatch.current_eta_minutes > 0
    assert dispatch.vehicle_number is not None

    db_session.refresh(transfer)
    assert transfer.status == TransferStatus.AMBULANCE_REQUESTED

    # Bed is still OCCUPIED by the patient while ambulance is requested
    db_session.refresh(bed)
    assert bed.status == BedStatus.OCCUPIED
    assert bed.current_patient_id == patient.id

    # 9. Ambulance Status Progression: Requested -> En Route -> Arrived Pickup -> Patient Onboard
    dispatch = amb_svc.update_dispatch_status(dispatch.id, AmbulanceStatus.EN_ROUTE)
    assert dispatch.status == AmbulanceStatus.EN_ROUTE

    dispatch = amb_svc.update_dispatch_status(dispatch.id, AmbulanceStatus.ARRIVED_PICKUP)
    assert dispatch.status == AmbulanceStatus.ARRIVED_PICKUP

    dispatch = amb_svc.update_dispatch_status(dispatch.id, AmbulanceStatus.PATIENT_ONBOARD)
    assert dispatch.status == AmbulanceStatus.PATIENT_ONBOARD
    db_session.refresh(transfer)
    assert transfer.status == TransferStatus.IN_TRANSIT

    # 10. Patient Departs Origin Facility: in_transit -> Triggers Sending Bed Turnover!
    dispatch = amb_svc.update_dispatch_status(dispatch.id, AmbulanceStatus.IN_TRANSIT)
    assert dispatch.status == AmbulanceStatus.IN_TRANSIT

    db_session.refresh(bed)
    assert bed.status == BedStatus.CLEANING
    assert bed.current_patient_id is None

    # 11. Ambulance Arrives at Receiving Hospital & Completes Transfer
    dispatch = amb_svc.update_dispatch_status(dispatch.id, AmbulanceStatus.ARRIVED_DESTINATION)
    assert dispatch.status == AmbulanceStatus.ARRIVED_DESTINATION
    assert dispatch.current_eta_minutes == 0

    dispatch = amb_svc.update_dispatch_status(dispatch.id, AmbulanceStatus.COMPLETED)
    assert dispatch.status == AmbulanceStatus.COMPLETED

    db_session.refresh(transfer)
    db_session.refresh(admission)
    assert transfer.status == TransferStatus.COMPLETED
    assert transfer.completed_at is not None
    assert admission.status == AdmissionStatus.TRANSFERRED

    # 12. Receiving Capacity Verification: remained at 1 (not double decremented)
    db_session.refresh(cap)
    assert cap.available_beds == 1

    # 13. Audit Workflow Events Verification
    events = (
        db_session.query(WorkflowEvent)
        .filter(WorkflowEvent.trusted_provenance.is_(True))
        .all()
    )
    event_types = {e.event_type for e in events}
    assert "clinical_transfer_decision_confirmed" in event_types
    assert "receiving_hospital_selected" in event_types
    assert "transfer_packet_sent" in event_types
    assert "transfer_packet_viewed" in event_types
    assert "receiving_hospital_accepted" in event_types
    assert "ambulance_dispatch_requested" in event_types
    assert "ambulance_en_route" in event_types
    assert "ambulance_arrived_pickup" in event_types
    assert "patient_onboarded" in event_types
    assert "patient_transfer_started"
    assert "patient_departed_bed" in event_types
    assert "bed_cleaning_started" in event_types
    assert "ambulance_arrived_destination" in event_types
    assert "transfer_completed" in event_types
