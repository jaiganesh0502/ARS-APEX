import os
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.models.admission import Admission, AdmissionStatus
from app.models.bed import Bed, BedStatus
from app.models.billing_clearance import BillingClearance, BillingStatus
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.services.discharge_package_service import DischargePackageService
from app.services.discharge_service import DischargeService


@pytest.fixture
def pdf_test_env(db_session):
    doctor = User(name="Dr. Priya Sharma", email="priya.pdf@hospital.org", role=UserRole.DOCTOR)
    db_session.add(doctor)
    db_session.flush()

    patient = Patient(
        patient_code="PT-PDF-01",
        first_name="Vikram",
        last_name="Malhotra",
        date_of_birth=datetime(1975, 8, 12).date(),
        gender="Male",
    )
    db_session.add(patient)
    db_session.flush()

    bed = Bed(bed_number="PDF-201", ward="Cardiology", status=BedStatus.OCCUPIED, current_patient_id=patient.id)
    db_session.add(bed)
    db_session.flush()

    admission = Admission(
        patient_id=patient.id,
        primary_diagnosis="Coronary Artery Disease - Post PCI",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.DISCHARGING,
        bed_id=bed.id,
    )
    db_session.add(admission)
    db_session.flush()

    report = DischargeReport(
        patient_id=patient.id,
        admission_id=admission.id,
        generated_content="Patient successfully underwent PCI with drug-eluting stent. Stable hemodynamics.\nPrescriptions:\n- Aspirin 75mg OD\n- Clopidogrel 75mg OD\nDiet: Low sodium, cardiac healthy diet.\nActivity: Light walking, avoid lifting > 5kg.\nFollow up: Cardiology OPD in 7 days.",
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
        total_amount=32000.0,
        amount_paid=32000.0,
        outstanding_amount=0.0,
        deferred=False,
    )
    db_session.add(billing)
    db_session.commit()

    return {
        "doctor": doctor,
        "patient": patient,
        "admission": admission,
        "report": report,
        "billing": billing,
    }


def test_pdf_generated_and_file_exists(db_session, pdf_test_env):
    """
    Verify authorization produces a valid PDF file in storage directory without error.
    """
    admission = pdf_test_env["admission"]
    report = pdf_test_env["report"]
    billing = pdf_test_env["billing"]
    doctor = pdf_test_env["doctor"]

    # 1. Doctor approves report
    discharge_svc = DischargeService(db_session)
    discharge_svc.approve_report(report.id, doctor)

    # 2. Billing clears
    billing.status = BillingStatus.CLEARED
    billing.clearance_reference = "TXN-CARD-5544"
    db_session.commit()

    # 3. Finalize package
    package_svc = DischargePackageService(db_session)
    package = package_svc.finalize_discharge_package(admission.id, authorizing_user=doctor)

    assert package.pdf_path is not None
    assert os.path.exists(package.pdf_path)
    assert os.path.getsize(package.pdf_path) > 1000  # Valid non-empty PDF
    assert package.pdf_generated_at is not None


def test_pdf_download_endpoint(client: TestClient, db_session, pdf_test_env):
    """
    Verify GET /api/discharge-packages/{id}/pdf returns application/pdf stream.
    """
    admission = pdf_test_env["admission"]
    report = pdf_test_env["report"]
    billing = pdf_test_env["billing"]
    doctor = pdf_test_env["doctor"]

    discharge_svc = DischargeService(db_session)
    discharge_svc.approve_report(report.id, doctor)

    billing.status = BillingStatus.CLEARED
    billing.clearance_reference = "TXN-CARD-5544"
    db_session.commit()

    package_svc = DischargePackageService(db_session)
    package = package_svc.finalize_discharge_package(admission.id, authorizing_user=doctor)

    # Call download endpoint
    res = client.get(f"/api/discharge-packages/{package.id}/pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert len(res.content) > 1000


def test_invalid_package_id_returns_404(client: TestClient):
    """Verify downloading a non-existent package returns 404."""
    res = client.get("/api/discharge-packages/999999/pdf")
    assert res.status_code == 404


def test_duplicate_finalization_is_idempotent(db_session, pdf_test_env):
    """
    Verify calling finalize_discharge_package multiple times returns the exact same package
    without creating duplicate records or modifying clinical snapshots.
    """
    admission = pdf_test_env["admission"]
    report = pdf_test_env["report"]
    billing = pdf_test_env["billing"]
    doctor = pdf_test_env["doctor"]

    discharge_svc = DischargeService(db_session)
    discharge_svc.approve_report(report.id, doctor)

    billing.status = BillingStatus.CLEARED
    billing.clearance_reference = "TXN-CARD-5544"
    db_session.commit()

    package_svc = DischargePackageService(db_session)
    pkg1 = package_svc.finalize_discharge_package(admission.id, authorizing_user=doctor)
    initial_pdf = pkg1.pdf_path
    initial_auth_time = pkg1.authorized_at

    # Second call
    pkg2 = package_svc.finalize_discharge_package(admission.id, authorizing_user=doctor)
    assert pkg1.id == pkg2.id
    assert pkg1.pdf_path == pkg2.pdf_path
    assert pkg1.authorized_at == pkg2.authorized_at
