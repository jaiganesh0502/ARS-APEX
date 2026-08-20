import pytest
from datetime import datetime, timezone
from fastapi import HTTPException

from app.models.admission import Admission, AdmissionStatus
from app.models.ambulance_dispatch import AmbulanceDispatch, AmbulanceStatus
from app.models.bed import Bed, BedStatus
from app.models.hospital import Hospital
from app.models.hospital_capacity import HospitalCapacity
from app.models.patient import Patient
from app.models.transfer import Transfer, TransferStatus
from app.models.user import User, UserRole
from app.models.workflow_event import WorkflowEvent
from app.services.ambulance_dispatch_service import AmbulanceDispatchService
from app.services.receiving_transfer_service import ReceivingTransferService


@pytest.fixture
def test_data(db_session):
    """
    Set up sending hospital, receiving hospital with capacity, patient, admission, bed, and transfer.
    """
    user = User(
        name="Dr. Asha Rao",
        email="asha.dispatch@test.com",
        role=UserRole.DOCTOR,
    )
    db_session.add(user)
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

    # Receiving capacity: 2 beds
    cap = HospitalCapacity(
        hospital_id=receiving_hosp.id,
        specialty="Neurology",
        total_beds=10,
        available_beds=2,
    )
    db_session.add(cap)

    patient = Patient(
        patient_code="PT-AMB-01",
        first_name="Kavitha",
        last_name="Rajan",
        date_of_birth=datetime(1985, 4, 12).date(),
        gender="Female",
        blood_group="O+",
    )
    db_session.add(patient)
    db_session.flush()

    bed = Bed(
        bed_number="NEU-AMB-01",
        ward="Neurology Ward",
        status=BedStatus.OCCUPIED,
        current_patient_id=patient.id,
    )
    db_session.add(bed)
    db_session.flush()

    admission = Admission(
        patient_id=patient.id,
        primary_diagnosis="Acute Ischemic Stroke",
        attending_doctor_id=user.id,
        status=AdmissionStatus.TRANSFER_PENDING,
        bed_id=bed.id,
    )
    db_session.add(admission)
    db_session.flush()

    transfer = Transfer(
        patient_id=patient.id,
        admission_id=admission.id,
        sending_hospital_id=sending_hosp.id,
        receiving_hospital_id=receiving_hosp.id,
        required_specialty="Neurology",
        emergency=True,
        status=TransferStatus.MATCHING,
    )
    db_session.add(transfer)
    db_session.commit()

    return {
        "user": user,
        "sending_hosp": sending_hosp,
        "receiving_hosp": receiving_hosp,
        "patient": patient,
        "bed": bed,
        "admission": admission,
        "transfer": transfer,
    }


def test_dispatch_eligibility_and_idempotency(db_session, test_data):
    """
    Verify ambulance dispatch eligibility rules, distance calculation, ETA, and idempotency.
    """
    svc = AmbulanceDispatchService(db_session)
    rec_svc = ReceivingTransferService(db_session)
    transfer = test_data["transfer"]

    # 1. Matching transfer cannot dispatch
    with pytest.raises(HTTPException) as exc:
        svc.dispatch_ambulance(transfer.id)
    assert exc.value.status_code == 400
    assert "accepted" in exc.value.detail

    # 2. Accept transfer (Feature 6 flow)
    transfer.status = TransferStatus.AWAITING_ACCEPTANCE
    db_session.commit()
    rec_svc.accept_transfer(transfer.id, notes="Ready in Neuro ICU")
    assert transfer.status == TransferStatus.ACCEPTED

    # 3. Dispatch ambulance
    dispatch = svc.dispatch_ambulance(transfer.id, test_data["user"])
    assert dispatch is not None
    assert dispatch.status == AmbulanceStatus.REQUESTED
    assert dispatch.dispatch_reference.startswith("AMB-")
    assert dispatch.pickup_name == test_data["sending_hosp"].name
    assert dispatch.destination_name == test_data["receiving_hosp"].name
    assert dispatch.distance_km > 0
    assert dispatch.estimated_duration_minutes > 0
    assert dispatch.current_eta_minutes > 0
    assert dispatch.vehicle_number is not None
    assert dispatch.driver_name is not None
    assert transfer.status == TransferStatus.AMBULANCE_REQUESTED

    # 4. Idempotency: second dispatch returns existing dispatch
    dispatch_again = svc.dispatch_ambulance(transfer.id, test_data["user"])
    assert dispatch_again.id == dispatch.id
    assert dispatch_again.dispatch_reference == dispatch.dispatch_reference


def test_emergency_vs_standard_eta(db_session, test_data):
    """
    Verify emergency transfer receives prioritized dispatch buffer in simulated ETA.
    """
    svc = AmbulanceDispatchService(db_session)
    eta_emergency = svc.eta_service.calculate_initial_eta(distance_km=10.0, emergency=True)
    eta_standard = svc.eta_service.calculate_initial_eta(distance_km=10.0, emergency=False)

    assert eta_emergency["dispatch_buffer_minutes"] == 4
    assert eta_standard["dispatch_buffer_minutes"] == 8
    assert eta_emergency["estimated_duration_minutes"] < eta_standard["estimated_duration_minutes"]


def test_status_state_machine_and_bed_release(db_session, test_data):
    """
    Verify complete validated status transitions from requested to completed,
    and verify sending bed stays occupied until physical patient departure (in_transit).
    """
    svc = AmbulanceDispatchService(db_session)
    rec_svc = ReceivingTransferService(db_session)
    transfer = test_data["transfer"]
    bed = test_data["bed"]
    admission = test_data["admission"]

    # Setup accepted transfer and dispatch
    transfer.status = TransferStatus.AWAITING_ACCEPTANCE
    db_session.commit()
    rec_svc.accept_transfer(transfer.id)
    dispatch = svc.dispatch_ambulance(transfer.id)

    # Initial state: bed remains OCCUPIED by patient
    db_session.refresh(bed)
    assert bed.status == BedStatus.OCCUPIED
    assert bed.current_patient_id == test_data["patient"].id

    # Step 1: Requested -> En Route
    dispatch = svc.update_dispatch_status(dispatch.id, AmbulanceStatus.EN_ROUTE)
    assert dispatch.status == AmbulanceStatus.EN_ROUTE
    assert dispatch.en_route_at is not None
    db_session.refresh(bed)
    assert bed.status == BedStatus.OCCUPIED

    # Invalid jump: en_route -> completed (Must be rejected)
    with pytest.raises(HTTPException) as exc:
        svc.update_dispatch_status(dispatch.id, AmbulanceStatus.COMPLETED)
    assert exc.value.status_code == 409

    # Step 2: En Route -> Arrived Pickup
    dispatch = svc.update_dispatch_status(dispatch.id, AmbulanceStatus.ARRIVED_PICKUP)
    assert dispatch.status == AmbulanceStatus.ARRIVED_PICKUP
    assert dispatch.arrived_pickup_at is not None
    db_session.refresh(bed)
    assert bed.status == BedStatus.OCCUPIED

    # Step 3: Arrived Pickup -> Patient Onboard
    dispatch = svc.update_dispatch_status(dispatch.id, AmbulanceStatus.PATIENT_ONBOARD)
    assert dispatch.status == AmbulanceStatus.PATIENT_ONBOARD
    assert dispatch.patient_onboard_at is not None
    db_session.refresh(transfer)
    assert transfer.status == TransferStatus.IN_TRANSIT

    # Step 4: Patient Onboard -> In Transit (Patient leaves sending facility!)
    dispatch = svc.update_dispatch_status(dispatch.id, AmbulanceStatus.IN_TRANSIT)
    assert dispatch.status == AmbulanceStatus.IN_TRANSIT
    assert dispatch.departed_pickup_at is not None

    # BED TURNOVER TRIGGERED ON DEPARTURE: Sending bed enters CLEANING and patient is cleared
    db_session.refresh(bed)
    assert bed.status == BedStatus.CLEANING
    assert bed.current_patient_id is None

    # Step 5: In Transit -> Arrived Destination
    dispatch = svc.update_dispatch_status(dispatch.id, AmbulanceStatus.ARRIVED_DESTINATION)
    assert dispatch.status == AmbulanceStatus.ARRIVED_DESTINATION
    assert dispatch.arrived_destination_at is not None
    assert dispatch.current_eta_minutes == 0

    # Step 6: Arrived Destination -> Completed
    dispatch = svc.update_dispatch_status(dispatch.id, AmbulanceStatus.COMPLETED)
    assert dispatch.status == AmbulanceStatus.COMPLETED
    assert dispatch.completed_at is not None

    # Verify Transfer and Admission completion states
    db_session.refresh(transfer)
    db_session.refresh(admission)
    assert transfer.status == TransferStatus.COMPLETED
    assert transfer.completed_at is not None
    assert admission.status == AdmissionStatus.TRANSFERRED

    # Idempotent double completion
    dispatch_again = svc.update_dispatch_status(dispatch.id, AmbulanceStatus.COMPLETED)
    assert dispatch_again.status == AmbulanceStatus.COMPLETED


def test_capacity_remains_intact_during_dispatch(db_session, test_data):
    """
    Verify ambulance transitions do not alter receiving hospital capacity
    (capacity was already decremented by Feature 6 acceptance).
    """
    svc = AmbulanceDispatchService(db_session)
    rec_svc = ReceivingTransferService(db_session)
    transfer = test_data["transfer"]
    receiving_hosp = test_data["receiving_hosp"]

    # Initial capacity is 2
    transfer.status = TransferStatus.AWAITING_ACCEPTANCE
    db_session.commit()
    rec_svc.accept_transfer(transfer.id)

    cap_after_accept = (
        db_session.query(HospitalCapacity)
        .filter(HospitalCapacity.hospital_id == receiving_hosp.id, HospitalCapacity.specialty == "Neurology")
        .first()
        .available_beds
    )
    assert cap_after_accept == 1  # 2 - 1 = 1

    # Run entire ambulance lifecycle
    dispatch = svc.dispatch_ambulance(transfer.id)
    svc.update_dispatch_status(dispatch.id, AmbulanceStatus.EN_ROUTE)
    svc.update_dispatch_status(dispatch.id, AmbulanceStatus.ARRIVED_PICKUP)
    svc.update_dispatch_status(dispatch.id, AmbulanceStatus.PATIENT_ONBOARD)
    svc.update_dispatch_status(dispatch.id, AmbulanceStatus.IN_TRANSIT)
    svc.update_dispatch_status(dispatch.id, AmbulanceStatus.ARRIVED_DESTINATION)
    svc.update_dispatch_status(dispatch.id, AmbulanceStatus.COMPLETED)

    # Capacity must still be exactly 1 (not double decremented)
    cap_final = (
        db_session.query(HospitalCapacity)
        .filter(HospitalCapacity.hospital_id == receiving_hosp.id, HospitalCapacity.specialty == "Neurology")
        .first()
        .available_beds
    )
    assert cap_final == 1


def test_cancellation_workflow(db_session, test_data):
    """
    Verify ambulance cancellation before patient onboarding reverts transfer to accepted,
    and cancellation after patient onboarding is rejected.
    """
    svc = AmbulanceDispatchService(db_session)
    rec_svc = ReceivingTransferService(db_session)
    transfer = test_data["transfer"]

    transfer.status = TransferStatus.AWAITING_ACCEPTANCE
    db_session.commit()
    rec_svc.accept_transfer(transfer.id)
    dispatch = svc.dispatch_ambulance(transfer.id)
    assert transfer.status == TransferStatus.AMBULANCE_REQUESTED

    # Cancel dispatch while in REQUESTED state
    cancelled = svc.cancel_dispatch(dispatch.id, reason="Sending physician ordered clinical delay.")
    assert cancelled.status == AmbulanceStatus.CANCELLED
    assert cancelled.cancellation_reason == "Sending physician ordered clinical delay."

    db_session.refresh(transfer)
    assert transfer.status == TransferStatus.ACCEPTED

    # Re-dispatch and advance to PATIENT_ONBOARD
    dispatch2 = svc.dispatch_ambulance(transfer.id)
    svc.update_dispatch_status(dispatch2.id, AmbulanceStatus.EN_ROUTE)
    svc.update_dispatch_status(dispatch2.id, AmbulanceStatus.ARRIVED_PICKUP)
    svc.update_dispatch_status(dispatch2.id, AmbulanceStatus.PATIENT_ONBOARD)

    # Attempting to cancel after patient is onboard must be rejected
    with pytest.raises(HTTPException) as exc:
        svc.cancel_dispatch(dispatch2.id, reason="Cannot cancel midway")
    assert exc.value.status_code == 409
    assert "already in progress" in exc.value.detail
