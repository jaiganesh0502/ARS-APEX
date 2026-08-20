import pytest
from datetime import datetime, timezone
from fastapi import HTTPException

from app.models.admission import Admission, AdmissionStatus
from app.models.bed import Bed, BedStatus
from app.models.billing_clearance import BillingClearance, BillingStatus
from app.models.clinical_decision import ClinicalDecision, ClinicalDecisionType
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.patient import Patient
from app.models.transfer import Transfer, TransferStatus
from app.models.user import User, UserRole
from app.models.workflow_event import WorkflowEvent
from app.services.billing_clearance_service import BillingClearanceService
from app.services.discharge_service import DischargeService
from app.services.bed_release_service import BedReleaseService


@pytest.fixture
def billing_test_data(db_session):
    doctor = User(name="Dr. Sunita Rao", email="sunita.billing@hospital.org", role=UserRole.DOCTOR)
    db_session.add(doctor)
    db_session.flush()

    patient = Patient(
        patient_code="PT-BILL-01",
        first_name="Ananya",
        last_name="Sharma",
        date_of_birth=datetime(1990, 5, 20).date(),
        gender="Female",
        blood_group="O+",
    )
    db_session.add(patient)
    db_session.flush()

    bed = Bed(bed_number="BIL-101", ward="General Medicine", status=BedStatus.OCCUPIED, current_patient_id=patient.id)
    db_session.add(bed)
    db_session.flush()

    admission = Admission(
        patient_id=patient.id,
        primary_diagnosis="Acute Bronchitis",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.DISCHARGING,
        bed_id=bed.id,
    )
    db_session.add(admission)
    db_session.flush()

    report = DischargeReport(
        patient_id=patient.id,
        admission_id=admission.id,
        generated_content="Patient recovered. Medications prescribed.",
        generation_provider="replicate",
        generation_model="openai/gpt-5.6-luna",
        status=DischargeReportStatus.GENERATED,
    )
    db_session.add(report)
    db_session.commit()

    return {"doctor": doctor, "patient": patient, "bed": bed, "admission": admission, "report": report}


def test_requires_billing_clearance_rule():
    """Verify centralized domain rule for billing requirement."""
    assert BillingClearanceService.requires_billing_clearance("discharge", emergency=False) is True
    assert BillingClearanceService.requires_billing_clearance("transfer", emergency=False) is True
    assert BillingClearanceService.requires_billing_clearance("transfer", emergency=True) is False


def test_report_approval_parallel_billing_and_bed_release(db_session, billing_test_data):
    """
    Verify report approval creates pending billing clearance in parallel without blocking bed turnover to vacating.
    """
    doctor = billing_test_data["doctor"]
    report = billing_test_data["report"]
    bed = billing_test_data["bed"]

    discharge_svc = DischargeService(db_session)
    approved_report = discharge_svc.approve_report(report.id, doctor=doctor)
    assert approved_report.status == DischargeReportStatus.APPROVED

    # Check billing clearance was created as PENDING in parallel
    billing_svc = BillingClearanceService(db_session)
    clearance = billing_svc.get_by_admission_id(report.admission_id)
    assert clearance is not None
    assert clearance.status == BillingStatus.PENDING
    assert clearance.deferred is False
    assert clearance.outstanding_amount == 18500.00

    # CRITICAL INVARIANT: Bed turnover to VACATING must proceed immediately while billing is PENDING
    bed_svc = BedReleaseService(db_session)
    vacating_bed = bed_svc.start_release(bed.id, doctor)
    assert vacating_bed.status == BedStatus.VACATING


def test_billing_clearance_and_final_authorization(db_session, billing_test_data):
    """
    Verify billing clearance transitions to CLEARED, is idempotent, and enables final discharge authorization.
    """
    doctor = billing_test_data["doctor"]
    report = billing_test_data["report"]
    admission = billing_test_data["admission"]

    discharge_svc = DischargeService(db_session)
    discharge_svc.approve_report(report.id, doctor=doctor)

    billing_svc = BillingClearanceService(db_session)
    clearance = billing_svc.get_by_admission_id(admission.id)

    # Attempt final authorization while billing is PENDING -> MUST FAIL
    with pytest.raises(HTTPException) as exc:
        billing_svc.finalize_discharge_authorization(admission.id)
    assert exc.value.status_code == 409
    assert "Billing clearance is pending" in exc.value.detail

    # Clear billing
    cleared = billing_svc.clear_billing(
        billing_id=clearance.id,
        clearance_reference="DEMO-REF-1004",
        notes="All pharmacy and ward dues cleared.",
        confirmed_by_user=doctor,
    )
    assert cleared.status == BillingStatus.CLEARED
    assert cleared.outstanding_amount == 0.00
    assert cleared.clearance_reference == "DEMO-REF-1004"

    # Idempotent double clear
    cleared_again = billing_svc.clear_billing(
        billing_id=clearance.id,
        clearance_reference="DEMO-REF-1004",
    )
    assert cleared_again.status == BillingStatus.CLEARED

    # Final discharge authorization now SUCCEEDS
    auth = billing_svc.finalize_discharge_authorization(admission.id)
    assert auth["success"] is True
    assert auth["billing_status"] == "cleared"


def test_emergency_transfer_billing_deferral(db_session, billing_test_data):
    """
    Verify emergency transfers skip billing clearance, set deferred=True, and never enter a wait state.
    """
    admission = billing_test_data["admission"]
    billing_svc = BillingClearanceService(db_session)

    clearance = billing_svc.defer_billing_for_emergency(admission.id, transfer_id=99)
    assert clearance.status == BillingStatus.DEFERRED
    assert clearance.deferred is True
    assert clearance.total_amount == 0.00

    events = db_session.query(WorkflowEvent).filter(WorkflowEvent.event_type == "billing_deferred").all()
    assert len(events) > 0
