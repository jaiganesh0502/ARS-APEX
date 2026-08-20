import pytest
from datetime import datetime
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.models.admission import Admission, AdmissionStatus
from app.models.bed import Bed, BedStatus
from app.models.billing_clearance import BillingClearance, BillingStatus
from app.models.discharge_package import DischargePackage, DischargePackageStatus
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.services.discharge_package_service import DischargePackageService
from app.services.bed_release_service import BedReleaseService


@pytest.fixture
def eligibility_env(db_session):
    doctor = User(name="Dr. Eligibility", email="elig.doc@hospital.org", role=UserRole.DOCTOR)
    db_session.add(doctor)
    db_session.flush()

    patient = Patient(
        patient_code="PT-ELIG-01",
        first_name="Anita",
        last_name="Desai",
        date_of_birth=datetime(1988, 5, 20).date(),
        gender="Female",
    )
    db_session.add(patient)
    db_session.flush()

    bed = Bed(bed_number="ELIG-101", ward="General", status=BedStatus.OCCUPIED, current_patient_id=patient.id)
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
        generated_content="Patient recovered completely. Prescription: Amoxicillin 500mg TDS for 5 days.",
        generation_provider="replicate",
        generation_model="openai/gpt-5.6-luna",
        status=DischargeReportStatus.GENERATED,
    )
    db_session.add(report)
    db_session.flush()

    billing = BillingClearance(
        patient_id=patient.id,
        admission_id=admission.id,
        discharge_report_id=report.id,
        status=BillingStatus.PENDING,
        total_amount=15000.0,
        amount_paid=0.0,
        outstanding_amount=15000.0,
        deferred=False,
    )
    db_session.add(billing)
    db_session.commit()

    return {
        "doctor": doctor,
        "patient": patient,
        "bed": bed,
        "admission": admission,
        "report": report,
        "billing": billing,
    }


def test_approved_report_with_billing_pending_is_rejected(db_session, eligibility_env):
    """
    Approved report + pending billing -> finalization MUST be rejected (HTTP 409).
    """
    admission = eligibility_env["admission"]
    report = eligibility_env["report"]
    doctor = eligibility_env["doctor"]

    # Approve report
    from app.services.discharge_service import DischargeService
    discharge_svc = DischargeService(db_session)
    discharge_svc.approve_report(report.id, doctor)

    # Attempt to finalize package while billing is pending
    service = DischargePackageService(db_session)
    with pytest.raises(HTTPException) as exc:
        service.finalize_discharge_package(admission.id, authorizing_user=doctor)

    assert exc.value.status_code == 409
    assert "cleared billing clearance" in exc.value.detail.lower()


def test_unapproved_report_with_billing_cleared_is_rejected(db_session, eligibility_env):
    """
    Unapproved report + cleared billing -> finalization MUST be rejected (HTTP 409).
    """
    admission = eligibility_env["admission"]
    billing = eligibility_env["billing"]
    doctor = eligibility_env["doctor"]

    # Clear billing while report is still GENERATED (not approved)
    billing.status = BillingStatus.CLEARED
    billing.clearance_reference = "TXN-CLEARED-01"
    db_session.commit()

    service = DischargePackageService(db_session)
    with pytest.raises(HTTPException) as exc:
        service.finalize_discharge_package(admission.id, authorizing_user=doctor)

    assert exc.value.status_code == 409
    assert "approved clinical discharge report" in exc.value.detail.lower()


def test_approved_report_with_cleared_billing_succeeds(db_session, eligibility_env):
    """
    Approved report + cleared billing -> finalization succeeds and creates DischargePackage.
    """
    admission = eligibility_env["admission"]
    report = eligibility_env["report"]
    billing = eligibility_env["billing"]
    doctor = eligibility_env["doctor"]

    # 1. Approve report
    from app.services.discharge_service import DischargeService
    discharge_svc = DischargeService(db_session)
    discharge_svc.approve_report(report.id, doctor)

    # 2. Clear billing
    billing.status = BillingStatus.CLEARED
    billing.clearance_reference = "TXN-AUTO-998"
    db_session.commit()

    # 3. Finalize package
    service = DischargePackageService(db_session)
    package = service.finalize_discharge_package(admission.id, authorizing_user=doctor)

    assert package is not None
    assert package.status in (DischargePackageStatus.AUTHORIZED, DischargePackageStatus.PDF_READY)
    assert package.patient_id == admission.patient_id
    assert package.clinical_snapshot["primary_diagnosis"] == "Acute Bronchitis"
    assert "why_you_were_admitted" in package.patient_summary


def test_bed_status_independence_rule(db_session, eligibility_env):
    """
    Verify bed turnover state (vacating -> cleaning -> available) is independent of billing gate.
    When bed is cleaning or available and billing clears, package authorization succeeds without errors.
    """
    admission = eligibility_env["admission"]
    report = eligibility_env["report"]
    billing = eligibility_env["billing"]
    bed = eligibility_env["bed"]
    doctor = eligibility_env["doctor"]

    # 1. Doctor approves report
    from app.services.discharge_service import DischargeService
    discharge_svc = DischargeService(db_session)
    discharge_svc.approve_report(report.id, doctor)

    # 2. Bed starts turnover
    bed_svc = BedReleaseService(db_session)
    vacating_bed = bed_svc.start_release(bed.id, doctor)
    assert vacating_bed.status == BedStatus.VACATING

    # 3. While billing is pending, package finalization MUST fail
    service = DischargePackageService(db_session)
    with pytest.raises(HTTPException):
        service.finalize_discharge_package(admission.id, authorizing_user=doctor)

    # 4. Bed completes departure and cleaning to AVAILABLE
    cleaning_bed = bed_svc.patient_departed(bed.id, doctor)
    assert cleaning_bed.status == BedStatus.CLEANING
    avail_bed = bed_svc.cleaning_complete(bed.id, doctor)
    assert avail_bed.status == BedStatus.AVAILABLE

    # 5. Billing clears later
    billing.status = BillingStatus.CLEARED
    billing.clearance_reference = "TXN-LATE-CLEARANCE"
    db_session.commit()

    # 6. Final package authorization now succeeds even though bed is already AVAILABLE
    package = service.finalize_discharge_package(admission.id, authorizing_user=doctor)
    assert package.id is not None
    assert package.clinical_snapshot["clearance_reference"] == "TXN-LATE-CLEARANCE"
