import pytest
from fastapi.testclient import TestClient
from datetime import datetime, date

from app.main import app
from app.api.dependencies.auth import get_current_user_stub, get_current_user
from app.api.dependencies.database import get_db
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.admission import Admission, AdmissionStatus
from app.models.bed import Bed, BedStatus
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.discharge_package import DischargePackage, DischargePackageStatus


@pytest.fixture
def rbac_env(db_session):
    # Create doctor
    doc = User(name="Dr. Smith", email="dr.smith@test.org", role=UserRole.DOCTOR, is_active=True)
    # Create superintendent
    supt = User(name="Super Admin", email="super@test.org", role=UserRole.MEDICAL_SUPERINTENDENT, is_active=True)
    # Create patient entity & user
    pt_entity = Patient(
        first_name="John",
        last_name="Doe",
        patient_code="PT-RBAC-001",
        date_of_birth=date(1985, 1, 1),
        gender="Male",
        phone="555-0101",
    )
    db_session.add_all([doc, supt, pt_entity])
    db_session.commit()

    pt_user = User(
        name="John Doe",
        email="john.doe@test.org",
        role=UserRole.PATIENT,
        patient_id=pt_entity.id,
        is_active=True,
    )
    # Create Bed
    bed = Bed(bed_number="BED-RBAC-01", ward="ICU", status=BedStatus.CLEANING)
    db_session.add_all([pt_user, bed])
    db_session.commit()

    admission = Admission(
        patient_id=pt_entity.id,
        attending_doctor_id=doc.id,
        bed_id=bed.id,
        primary_diagnosis="Acute Coronary Syndrome",
        status=AdmissionStatus.ADMITTED,
    )
    db_session.add(admission)
    db_session.commit()

    # Discharge report for discharge packages tests
    report = DischargeReport(
        patient_id=pt_entity.id,
        admission_id=admission.id,
        generated_content="Patient clinically stable",
        generation_provider="replicate",
        generation_model="deepseek-r1",
        approved_by=doc.id,
        status=DischargeReportStatus.APPROVED,
    )
    db_session.add(report)
    db_session.commit()

    return {
        "doctor": doc,
        "superintendent": supt,
        "patient_user": pt_user,
        "patient_entity": pt_entity,
        "bed": bed,
        "admission": admission,
        "report": report,
    }


def test_doctor_cannot_complete_bed_cleaning(db_session, rbac_env):
    """Doctor role must get 403 Forbidden when attempting bed operational mutations."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user_stub] = lambda: rbac_env["doctor"]
    app.dependency_overrides[get_current_user] = lambda: rbac_env["doctor"]

    with TestClient(app) as client:
        res = client.post(f"/api/beds/{rbac_env['bed'].id}/cleaning-complete")
        assert res.status_code == 403
    app.dependency_overrides.clear()


def test_superintendent_can_complete_bed_cleaning(db_session, rbac_env):
    """Medical Superintendent can complete bed cleaning."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user_stub] = lambda: rbac_env["superintendent"]
    app.dependency_overrides[get_current_user] = lambda: rbac_env["superintendent"]

    # Mark admission discharged so bed can complete cleaning
    rbac_env["admission"].status = AdmissionStatus.DISCHARGED
    rbac_env["bed"].status = BedStatus.CLEANING
    rbac_env["bed"].current_patient_id = None
    db_session.commit()

    with TestClient(app) as client:
        res = client.post(f"/api/beds/{rbac_env['bed'].id}/cleaning-complete")
        assert res.status_code == 200
        assert res.json()["status"] == "available"
    app.dependency_overrides.clear()


def test_superintendent_cannot_create_clinical_decision(db_session, rbac_env):
    """Medical Superintendent must get 403 Forbidden when attempting clinical decision mutations."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user_stub] = lambda: rbac_env["superintendent"]
    app.dependency_overrides[get_current_user] = lambda: rbac_env["superintendent"]

    payload = {
        "decision_type": "discharge",
        "reason": "Patient is stable",
    }

    with TestClient(app) as client:
        res = client.post(f"/api/admissions/{rbac_env['admission'].id}/clinical-decision", json=payload)
        assert res.status_code == 403
    app.dependency_overrides.clear()


def test_doctor_can_create_clinical_decision(db_session, rbac_env):
    """Doctor can create clinical decisions."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user_stub] = lambda: rbac_env["doctor"]
    app.dependency_overrides[get_current_user] = lambda: rbac_env["doctor"]

    payload = {
        "decision_type": "discharge",
        "reason": "Patient is clinically stable for discharge",
    }

    with TestClient(app) as client:
        res = client.post(f"/api/admissions/{rbac_env['admission'].id}/clinical-decision", json=payload)
        assert res.status_code == 201
        assert res.json()["decision_type"] == "discharge"
    app.dependency_overrides.clear()


def test_patient_cannot_access_staff_patients_list(db_session, rbac_env):
    """Patient role must get 403 Forbidden when trying to list hospital patients."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user_stub] = lambda: rbac_env["patient_user"]
    app.dependency_overrides[get_current_user] = lambda: rbac_env["patient_user"]

    with TestClient(app) as client:
        res = client.get("/api/patients")
        assert res.status_code == 403
    app.dependency_overrides.clear()


def test_patient_can_access_own_portal_profile(db_session, rbac_env):
    """Patient role can access their own portal profile."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user_stub] = lambda: rbac_env["patient_user"]
    app.dependency_overrides[get_current_user] = lambda: rbac_env["patient_user"]

    with TestClient(app) as client:
        res = client.get("/api/patient-portal/profile")
        assert res.status_code == 200
        data = res.json()
        assert data["patient"]["patient_code"] == "PT-RBAC-001"
    app.dependency_overrides.clear()


def test_patient_cannot_download_other_patient_pdf(db_session, rbac_env):
    """Patient cannot access or download another patient's discharge package PDF."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user_stub] = lambda: rbac_env["patient_user"]
    app.dependency_overrides[get_current_user] = lambda: rbac_env["patient_user"]

    # Package belonging to a DIFFERENT patient (patient_id=9999)
    other_pkg = DischargePackage(
        patient_id=9999,
        admission_id=rbac_env["admission"].id,
        discharge_report_id=rbac_env["report"].id,
        status=DischargePackageStatus.AUTHORIZED,
        clinical_snapshot={"patient_code": "PT-9999"},
        patient_summary={},
    )
    db_session.add(other_pkg)
    db_session.commit()

    with TestClient(app) as client:
        res = client.get(f"/api/discharge-packages/{other_pkg.id}")
        assert res.status_code == 403
    app.dependency_overrides.clear()
