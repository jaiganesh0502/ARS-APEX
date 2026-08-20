import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.models.admission import Admission, AdmissionStatus
from app.models.bed import Bed, BedStatus
from app.models.billing_clearance import BillingClearance, BillingStatus
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.hospital import Hospital
from app.models.hospital_capacity import HospitalCapacity
from app.models.patient import Patient
from app.models.transfer import Transfer, TransferStatus
from app.models.user import User, UserRole
from app.models.workflow_event import WorkflowEvent
from app.core.config import settings


@pytest.fixture
def e2e_hospitals(db_session):
    h1 = Hospital(name="Origin Apex Hospital", latitude=13.0827, longitude=80.2707, specialties=["Cardiology", "Trauma Care"], contact_number="+91-44-11111111")
    h2 = Hospital(name="Destination Mercy Hospital", latitude=13.0900, longitude=80.2800, specialties=["Cardiology", "Trauma Care"], contact_number="+91-44-22222222")
    db_session.add_all([h1, h2])
    db_session.flush()

    c1 = HospitalCapacity(hospital_id=h2.id, specialty="Cardiology", total_beds=20, available_beds=5)
    c2 = HospitalCapacity(hospital_id=h2.id, specialty="Trauma Care", total_beds=10, available_beds=3)
    db_session.add_all([c1, c2])
    db_session.commit()
    return {"origin": h1, "destination": h2}


def test_e2e_normal_discharge_with_parallel_billing_gate(client: TestClient, db_session, e2e_hospitals):
    """
    E2E Test: Normal Discharge Workflow
    1. Doctor approves discharge report -> report_approved emitted.
    2. Parallel Branch A: Bed transitions to vacating (NON-BLOCKING).
    3. Parallel Branch B: Billing clearance is created as pending.
    4. Attempting final discharge authorization while billing pending fails.
    5. Finance confirms billing clearance -> billing_cleared emitted.
    6. Final discharge authorization succeeds -> final_discharge_authorized emitted.
    7. Bed turnover proceeds: vacating -> cleaning -> available.
    """
    headers = {"X-Internal-API-Key": settings.INTERNAL_API_KEY}

    doctor = User(name="Dr. Priya", email="priya.e2e@hospital.org", role=UserRole.DOCTOR)
    patient = Patient(patient_code="PT-E2E-01", first_name="Kavita", last_name="Krishnan", date_of_birth=datetime(1982, 7, 10).date(), gender="Female")
    db_session.add_all([doctor, patient])
    db_session.flush()

    bed = Bed(bed_number="E2E-101", ward="Cardiology", status=BedStatus.OCCUPIED, current_patient_id=patient.id)
    db_session.add(bed)
    db_session.flush()

    admission = Admission(
        patient_id=patient.id,
        primary_diagnosis="Unstable Angina",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.DISCHARGING,
        bed_id=bed.id,
    )
    db_session.add(admission)
    db_session.flush()

    report = DischargeReport(
        patient_id=patient.id,
        admission_id=admission.id,
        generated_content="Patient clinically stable after angioplasty.",
        generation_provider="replicate",
        generation_model="openai/gpt-5.6-luna",
        status=DischargeReportStatus.GENERATED,
    )
    db_session.add(report)
    db_session.commit()

    # Step 1: Doctor Approves Report
    from app.services.discharge_service import DischargeService
    discharge_svc = DischargeService(db_session)
    discharge_svc.approve_report(report.id, doctor=doctor)

    # Step 2: Internal Automated Bed Release (Branch A)
    res_bed = client.post(f"/api/internal/beds/{bed.id}/start-release", headers=headers)
    assert res_bed.status_code == 200
    assert res_bed.json()["status"] == "vacating"

    # Step 3: Verify Billing Clearance (Branch B)
    res_bill_get = client.get(f"/api/admissions/{admission.id}/billing-clearance")
    assert res_bill_get.status_code == 200
    billing_data = res_bill_get.json()
    assert billing_data["status"] == "pending"
    billing_id = billing_data["id"]

    # Step 4: Final authorization while pending MUST fail
    res_fin_fail = client.post(f"/api/internal/billing-clearances/{billing_id}/finalize-handoff", headers=headers)
    assert res_fin_fail.status_code == 409

    # Step 5: Finance confirms billing clearance
    res_clear = client.post(
        f"/api/billing-clearances/{billing_id}/clear",
        json={"clearance_reference": "TXN-E2E-9988", "notes": "Settled via insurance cashless"},
    )
    assert res_clear.status_code == 200
    assert res_clear.json()["status"] == "cleared"

    # Step 6: Final authorization now succeeds
    res_fin_ok = client.post(f"/api/internal/billing-clearances/{billing_id}/finalize-handoff", headers=headers)
    assert res_fin_ok.status_code == 200
    assert res_fin_ok.json()["success"] is True

    # Step 7: Complete Bed Turnover to available
    from app.services.bed_release_service import BedReleaseService
    bed_svc = BedReleaseService(db_session)
    cleaning_bed = bed_svc.patient_departed(bed.id, doctor)
    assert cleaning_bed.status == BedStatus.CLEANING
    avail_bed = bed_svc.cleaning_complete(bed.id, doctor)
    assert avail_bed.status == BedStatus.AVAILABLE


def test_e2e_emergency_transfer_billing_bypass(client: TestClient, db_session, e2e_hospitals):
    """
    E2E Test: Emergency Transfer Workflow
    1. Transfer created with emergency = True.
    2. Receiving hospital accepts -> billing clearance is DEFERRED (status=deferred).
    3. Ambulance dispatch proceeds IMMEDIATELY without waiting for billing.
    4. Bed turnover proceeds normally on transit departure.
    """
    headers = {"X-Internal-API-Key": settings.INTERNAL_API_KEY}
    origin_hosp = e2e_hospitals["origin"]
    dest_hosp = e2e_hospitals["destination"]

    doctor = User(name="Dr. Emergency", email="emg.e2e@hospital.org", role=UserRole.DOCTOR)
    patient = Patient(patient_code="PT-E2E-EMG", first_name="Rohan", last_name="Verma", date_of_birth=datetime(1995, 1, 1).date(), gender="Male")
    db_session.add_all([doctor, patient])
    db_session.flush()

    bed = Bed(bed_number="EMG-ICU-1", ward="ICU", status=BedStatus.OCCUPIED, current_patient_id=patient.id)
    db_session.add(bed)
    db_session.flush()

    admission = Admission(
        patient_id=patient.id,
        primary_diagnosis="Polytrauma Head Injury",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.TRANSFER_PENDING,
        bed_id=bed.id,
    )
    db_session.add(admission)
    db_session.flush()

    from app.models.clinical_decision import ClinicalDecision, ClinicalDecisionType
    decision = ClinicalDecision(
        patient_id=patient.id,
        admission_id=admission.id,
        decision_type=ClinicalDecisionType.TRANSFER,
        transfer_urgency="emergency",
        reason="Immediate trauma surgery required.",
        required_specialty="Trauma Care",
        decided_by=doctor.id,
        status="confirmed",
    )
    db_session.add(decision)
    db_session.commit()

    # Step 1: Create Emergency Transfer
    from app.services.transfer_service import TransferService
    trf_svc = TransferService(db_session)
    transfer = trf_svc.create_or_get_transfer_for_admission(admission.id, requesting_user=doctor)
    transfer.emergency = True
    transfer.sending_hospital_id = origin_hosp.id
    transfer.receiving_hospital_id = dest_hosp.id
    transfer.required_specialty = "Trauma Care"
    transfer.status = TransferStatus.HOSPITAL_SELECTED
    db_session.commit()

    # Step 2: Receiving Hospital Accepts
    from app.services.receiving_transfer_service import ReceivingTransferService
    recv_svc = ReceivingTransferService(db_session)
    recv_svc.accept_transfer(transfer.id, notes="Trauma OR prepped", decided_by_user=doctor)

    # Step 3: Check billing status is DEFERRED
    billing_clearance = db_session.query(BillingClearance).filter(BillingClearance.admission_id == admission.id).first()
    assert billing_clearance is not None
    assert billing_clearance.status == BillingStatus.DEFERRED
    assert billing_clearance.deferred is True

    # Step 4: Dispatch Ambulance Immediately
    res_dispatch = client.post(f"/api/internal/transfers/{transfer.id}/dispatch-ambulance", headers=headers)
    assert res_dispatch.status_code == 200
    dispatch_data = res_dispatch.json()
    assert dispatch_data["success"] is True
    assert dispatch_data["status"] == "requested"

    # Step 5: Verify Operations Events recorded
    res_counts = client.get("/api/workflow-events/counts")
    assert res_counts.status_code == 200
    counts = res_counts.json()
    assert counts["total_events"] > 0
