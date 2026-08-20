from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.models import (
    Admission,
    AdmissionStatus,
    Bed,
    BedStatus,
    DischargeReport,
    DischargeReportStatus,
    Invoice,
    PaymentStatus,
    Patient,
    User,
    UserRole,
)
from app.services.billing_service import BillingService


def test_four_tier_rbac_matrix(db_session, client):
    # Setup test patients and roles
    patient_entity = Patient(first_name="Rani", last_name="Mukherjee", patient_code="PT-RBAC-1", date_of_birth=date(1984, 3, 21), gender="Female")
    db_session.add(patient_entity)
    db_session.flush()

    doctor = User(name="Dr. Alpha", email="doc_rbac@test.org", role=UserRole.DOCTOR, is_active=True)
    superintendent = User(name="Dr. Super", email="super_rbac@test.org", role=UserRole.MEDICAL_SUPERINTENDENT, is_active=True)
    receptionist = User(name="Priya Reception", email="rec_rbac@test.org", role=UserRole.RECEPTIONIST, is_active=True)
    patient_user = User(name="Rani User", email="pat_rbac@test.org", role=UserRole.PATIENT, is_active=True, patient_id=patient_entity.id)
    db_session.add_all([doctor, superintendent, receptionist, patient_user])
    db_session.flush()

    bed = Bed(bed_number="WARD-A-01", ward="General Ward", status=BedStatus.OCCUPIED, current_patient_id=patient_entity.id)
    db_session.add(bed)
    db_session.flush()

    admission = Admission(
        patient_id=patient_entity.id,
        attending_doctor_id=doctor.id,
        bed_id=bed.id,
        primary_diagnosis="Dengue Fever",
        status=AdmissionStatus.DISCHARGING,
    )
    db_session.add(admission)
    db_session.flush()

    report = DischargeReport(
        admission_id=admission.id,
        patient_id=patient_entity.id,
        generated_content="DRAFT discharge summary",
        generation_provider="clinical_document_pipeline",
        generation_model="ocr_extractor_v1",
        status=DischargeReportStatus.GENERATED,
    )
    db_session.add(report)
    db_session.commit()

    invoice = BillingService(db_session).generate_or_get_invoice(admission.id)

    # Helper headers
    doc_h = {"Authorization": f"Bearer {create_access_token(subject=doctor.id, role=doctor.role.value)}"}
    super_h = {"Authorization": f"Bearer {create_access_token(subject=superintendent.id, role=superintendent.role.value)}"}
    rec_h = {"Authorization": f"Bearer {create_access_token(subject=receptionist.id, role=receptionist.role.value)}"}
    pat_h = {"Authorization": f"Bearer {create_access_token(subject=patient_user.id, role=patient_user.role.value)}"}

    # 1. DOCTOR RBAC CHECKS
    # Approve report -> ALLOWED (200)
    r_app = client.post(
        f"/api/discharge/reports/{report.id}/approve",
        headers=doc_h,
        json={"acknowledged": True, "clinical_notes": "Reviewed and verified."},
    )
    assert r_app.status_code == 200

    # Record manual payment -> FORBIDDEN (403)
    r_doc_pay = client.post(
        f"/api/invoices/{invoice.id}/payments/manual",
        headers=doc_h,
        json={"amount": 500.00, "payment_method": "cash", "reference": "REC-01"},
    )
    assert r_doc_pay.status_code == 403

    # Bed turnover mutation -> FORBIDDEN (403)
    r_doc_bed = client.post(f"/api/beds/{bed.id}/patient-departed", headers=doc_h)
    assert r_doc_bed.status_code == 403

    # 2. RECEPTIONIST RBAC CHECKS
    # Register patient -> ALLOWED (201)
    r_rec_pat = client.post(
        "/api/patients",
        headers=rec_h,
        json={"first_name": "New", "last_name": "Patient", "patient_code": "PT-NEW-99", "date_of_birth": "1995-01-01", "gender": "Female"},
    )
    assert r_rec_pat.status_code == 201

    # Record manual payment -> ALLOWED (200)
    r_rec_pay = client.post(
        f"/api/invoices/{invoice.id}/payments/manual",
        headers=rec_h,
        json={"amount": float(invoice.total_amount), "payment_method": "cash", "reference": "REC-CASH-009"},
    )
    assert r_rec_pay.status_code == 200

    # Approve discharge report -> FORBIDDEN (403)
    r_rec_app = client.post(
        f"/api/discharge/reports/{report.id}/approve",
        headers=rec_h,
        json={"acknowledged": True},
    )
    assert r_rec_app.status_code == 403

    # 3. MEDICAL SUPERINTENDENT RBAC CHECKS
    # Approve discharge report -> FORBIDDEN (403)
    r_sup_app = client.post(
        f"/api/discharge/reports/{report.id}/approve",
        headers=super_h,
        json={"acknowledged": True},
    )
    assert r_sup_app.status_code == 403

    # 4. PATIENT RBAC CHECKS
    # Access own patient portal profile -> ALLOWED (200)
    r_pat_prof = client.get("/api/patient-portal/profile", headers=pat_h)
    assert r_pat_prof.status_code == 200
    assert r_pat_prof.json()["patient"]["patient_code"] == "PT-RBAC-1"
    assert r_pat_prof.json()["invoice"]["invoice_number"] == invoice.invoice_number

    # Access doctor / staff routes -> FORBIDDEN (403)
    r_pat_inv = client.get("/api/invoices", headers=pat_h)
    assert r_pat_inv.status_code == 403
