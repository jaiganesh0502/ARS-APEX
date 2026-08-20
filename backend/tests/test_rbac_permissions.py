from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.models.admission import Admission, AdmissionStatus
from app.models.bed import Bed, BedStatus
from app.models.billing_clearance import BillingClearance, BillingStatus
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.models.workflow_event import WorkflowEvent


@pytest.fixture
def rbac_env(db_session):
    doctor = User(
        name="Dr. RBAC Lead",
        email="doctor.rbac@hospital.org",
        role=UserRole.DOCTOR,
        password_hash=hash_password("DocPass!"),
        is_active=True,
    )
    superintendent = User(
        name="Superintendent Marcus",
        email="super.rbac@hospital.org",
        role=UserRole.MEDICAL_SUPERINTENDENT,
        password_hash=hash_password("SuperPass!"),
        is_active=True,
    )
    patient_user = User(
        name="Patient Alice",
        email="patient.rbac@hospital.org",
        role=UserRole.PATIENT,
        password_hash=hash_password("PatientPass!"),
        is_active=True,
    )
    patient = Patient(
        patient_code="PT-RBAC-01",
        first_name="Alice",
        last_name="Walker",
        date_of_birth=datetime(1982, 3, 15).date(),
        gender="Female",
    )
    db_session.add_all([doctor, superintendent, patient_user, patient])
    db_session.flush()

    patient_user.patient_id = patient.id

    bed = Bed(bed_number="RBAC-101", ward="ICU", status=BedStatus.OCCUPIED, current_patient_id=patient.id)
    db_session.add(bed)
    db_session.flush()

    admission = Admission(
        patient_id=patient.id,
        primary_diagnosis="Hypertensive Crisis",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.ADMITTED,
        bed_id=bed.id,
    )
    db_session.add(admission)
    db_session.flush()

    report = DischargeReport(
        patient_id=patient.id,
        admission_id=admission.id,
        generated_content="Blood pressure stabilized on IV labetalol. Switch to Amlodipine 5mg OD.",
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
        total_amount=25000.0,
        amount_paid=0.0,
        outstanding_amount=25000.0,
        deferred=False,
    )
    db_session.add(billing)

    event = WorkflowEvent(
        event_type="test_event",
        entity_type="test",
        entity_id=1,
        status="failed",
        delivery_status="failed",
        orchestration_status="failed",
        attempt_count=1,
        trusted_provenance=True,
        payload={},
    )
    db_session.add(event)
    db_session.commit()

    return {
        "doctor": doctor,
        "superintendent": superintendent,
        "patient_user": patient_user,
        "patient": patient,
        "admission": admission,
        "report": report,
        "billing": billing,
        "bed": bed,
        "event": event,
    }


def test_doctor_clinical_actions_permitted(client: TestClient, rbac_env):
    doctor = rbac_env["doctor"]
    admission = rbac_env["admission"]
    report = rbac_env["report"]
    token = create_access_token(subject=doctor.id, role="doctor")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Doctor creates clinical decision -> 201
    res_dec = client.post(
        f"/api/admissions/{admission.id}/clinical-decision",
        json={"decision_type": "discharge", "reason": "Patient is stable and criteria met."},
        headers=headers,
    )
    assert res_dec.status_code == 201
    decision_id = res_dec.json()["id"]
    assert res_dec.json()["decided_by"] == doctor.id

    # 1b. Doctor confirms clinical decision -> 200 (Admission moves to DISCHARGING)
    res_conf = client.post(
        f"/api/clinical-decisions/{decision_id}/confirm",
        headers=headers,
    )
    assert res_conf.status_code == 200

    # 2. Doctor approves discharge report -> 200
    res_app = client.post(
        f"/api/discharge/reports/{report.id}/approve",
        json={"acknowledged": True, "clinical_notes": "Reviewed and approved by attending doctor."},
        headers=headers,
    )
    assert res_app.status_code == 200
    assert res_app.json()["status"] == "approved"


def test_doctor_cannot_clear_billing(client: TestClient, rbac_env):
    doctor = rbac_env["doctor"]
    billing = rbac_env["billing"]
    token = create_access_token(subject=doctor.id, role="doctor")
    headers = {"Authorization": f"Bearer {token}"}

    # Doctor attempts to confirm billing clearance -> 403 Forbidden
    res = client.post(
        f"/api/billing-clearances/{billing.id}/clear",
        json={"clearance_reference": "TXN-DOC-ILLEGAL"},
        headers=headers,
    )
    assert res.status_code == 403
    err_msg = res.json().get("error", {}).get("message", "") or res.json().get("detail", "")
    assert "forbidden" in err_msg.lower()


def test_superintendent_billing_and_ops_permitted(client: TestClient, rbac_env):
    superintendent = rbac_env["superintendent"]
    billing = rbac_env["billing"]
    event = rbac_env["event"]
    token = create_access_token(subject=superintendent.id, role="medical_superintendent")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Superintendent clears billing -> 200
    res_clear = client.post(
        f"/api/billing-clearances/{billing.id}/clear",
        json={"clearance_reference": "TXN-SUPER-001"},
        headers=headers,
    )
    assert res_clear.status_code == 200
    assert res_clear.json()["status"] == "cleared"
    assert res_clear.json()["confirmed_by"] == superintendent.id

    # 2. Superintendent retries workflow event -> 200
    res_retry = client.post(
        f"/api/workflow-events/{event.id}/retry",
        headers=headers,
    )
    assert res_retry.status_code == 200


def test_superintendent_cannot_clinically_approve_report(client: TestClient, rbac_env):
    superintendent = rbac_env["superintendent"]
    report = rbac_env["report"]
    token = create_access_token(subject=superintendent.id, role="medical_superintendent")
    headers = {"Authorization": f"Bearer {token}"}

    # Superintendent attempts to approve clinical discharge report -> 403 Forbidden
    res = client.post(
        f"/api/discharge/reports/{report.id}/approve",
        json={"clinical_notes": "Approved by operational admin"},
        headers=headers,
    )
    assert res.status_code == 403


def test_patient_cannot_call_staff_endpoints(client: TestClient, rbac_env):
    patient_user = rbac_env["patient_user"]
    admission = rbac_env["admission"]
    report = rbac_env["report"]
    billing = rbac_env["billing"]
    token = create_access_token(subject=patient_user.id, role="patient")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Clinical decision -> 403
    res1 = client.post(
        f"/api/admissions/{admission.id}/clinical-decision",
        json={"decision_type": "discharge", "reason": "Patient self discharge"},
        headers=headers,
    )
    assert res1.status_code == 403

    # 2. Report approval -> 403
    res2 = client.post(
        f"/api/discharge/reports/{report.id}/approve",
        json={"acknowledged": True},
        headers=headers,
    )
    assert res2.status_code == 403

    # 3. Billing clear -> 403
    res3 = client.post(
        f"/api/billing-clearances/{billing.id}/clear",
        json={"clearance_reference": "PATIENT-CLR"},
        headers=headers,
    )
    assert res3.status_code == 403
