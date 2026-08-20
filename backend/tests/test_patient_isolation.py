from datetime import datetime
import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.models.admission import Admission, AdmissionStatus
from app.models.billing_clearance import BillingClearance, BillingStatus
from app.models.discharge_package import DischargePackage, DischargePackageStatus
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.services.discharge_package_service import DischargePackageService
from app.services.discharge_service import DischargeService


@pytest.fixture
def isolation_env(db_session):
    doctor = User(
        name="Dr. Attending Doctor",
        email="doctor.iso@hospital.org",
        role=UserRole.DOCTOR,
        password_hash=hash_password("DocPass!"),
    )
    # Patient A
    patient_a = Patient(
        patient_code="PT-ISO-A",
        first_name="Alice",
        last_name="Johnson",
        date_of_birth=datetime(1990, 1, 1).date(),
        gender="Female",
    )
    # Patient B
    patient_b = Patient(
        patient_code="PT-ISO-B",
        first_name="Bob",
        last_name="Smith",
        date_of_birth=datetime(1985, 6, 15).date(),
        gender="Male",
    )
    db_session.add_all([doctor, patient_a, patient_b])
    db_session.flush()

    user_a = User(
        name="Alice Johnson",
        email="alice@demo.local",
        role=UserRole.PATIENT,
        password_hash=hash_password("Alice123!"),
        patient_id=patient_a.id,
    )
    user_b = User(
        name="Bob Smith",
        email="bob@demo.local",
        role=UserRole.PATIENT,
        password_hash=hash_password("Bob123!"),
        patient_id=patient_b.id,
    )
    db_session.add_all([user_a, user_b])
    db_session.flush()

    # Create admission and package for Patient A
    adm_a = Admission(
        patient_id=patient_a.id,
        primary_diagnosis="Type 2 Diabetes - Hyperglycemia",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.DISCHARGING,
    )
    db_session.add(adm_a)
    db_session.flush()

    report_a = DischargeReport(
        patient_id=patient_a.id,
        admission_id=adm_a.id,
        generated_content="Blood sugar stabilized. Prescriptions:\n- Metformin 500mg BD\nDiet: Low glycemic index diet.\nFollow up: Endocrine clinic in 10 days.",
        generation_provider="replicate",
        generation_model="openai/gpt-5.6-luna",
        status=DischargeReportStatus.GENERATED,
    )
    db_session.add(report_a)
    db_session.flush()

    billing_a = BillingClearance(
        patient_id=patient_a.id,
        admission_id=adm_a.id,
        discharge_report_id=report_a.id,
        status=BillingStatus.CLEARED,
        total_amount=5000.0,
        amount_paid=5000.0,
        outstanding_amount=0.0,
        clearance_reference="TXN-ISO-A-100",
    )
    db_session.add(billing_a)
    db_session.commit()

    # Approve and finalize for Patient A
    discharge_svc = DischargeService(db_session)
    discharge_svc.approve_report(report_a.id, doctor)

    pkg_svc = DischargePackageService(db_session)
    pkg_a = pkg_svc.finalize_discharge_package(adm_a.id, authorizing_user=doctor)

    return {
        "doctor": doctor,
        "patient_a": patient_a,
        "patient_b": patient_b,
        "user_a": user_a,
        "user_b": user_b,
        "pkg_a": pkg_a,
    }


def test_patient_a_sees_only_own_data(client: TestClient, isolation_env):
    user_a = isolation_env["user_a"]
    token_a = create_access_token(subject=user_a.id, role="patient")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    res = client.get("/api/patient-portal/profile", headers=headers_a)
    assert res.status_code == 200
    data = res.json()
    assert data["patient"]["patient_code"] == "PT-ISO-A"
    assert data["patient"]["first_name"] == "Alice"
    assert data["discharge_package"] is not None
    assert data["discharge_package"]["has_pdf"] is True


def test_patient_b_sees_only_own_data(client: TestClient, isolation_env):
    user_b = isolation_env["user_b"]
    token_b = create_access_token(subject=user_b.id, role="patient")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    res = client.get("/api/patient-portal/profile", headers=headers_b)
    assert res.status_code == 200
    data = res.json()
    assert data["patient"]["patient_code"] == "PT-ISO-B"
    assert data["patient"]["first_name"] == "Bob"
    # Patient B does not have a package yet
    assert data["discharge_package"] is None


def test_patient_a_can_download_own_pdf(client: TestClient, isolation_env):
    user_a = isolation_env["user_a"]
    token_a = create_access_token(subject=user_a.id, role="patient")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    res = client.get("/api/patient-portal/pdf", headers=headers_a)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert len(res.content) > 1000


def test_doctor_cannot_access_patient_portal_endpoints(client: TestClient, isolation_env):
    doctor = isolation_env["doctor"]
    token_doc = create_access_token(subject=doctor.id, role="doctor")
    headers_doc = {"Authorization": f"Bearer {token_doc}"}

    res = client.get("/api/patient-portal/profile", headers=headers_doc)
    assert res.status_code == 403
