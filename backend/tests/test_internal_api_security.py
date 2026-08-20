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
from app.models.clinical_decision import ClinicalDecision, ClinicalDecisionType
from app.models.user import User, UserRole
from app.core.config import settings


@pytest.fixture
def internal_test_env(db_session):
    doctor = User(name="Dr. Internal Auth", email="internal.test@hospital.org", role=UserRole.DOCTOR)
    db_session.add(doctor)
    db_session.flush()

    patient = Patient(
        patient_code="PT-INT-01",
        first_name="Meera",
        last_name="Nair",
        date_of_birth=datetime(1985, 3, 15).date(),
        gender="Female",
        blood_group="B+",
    )
    db_session.add(patient)
    db_session.flush()

    bed = Bed(bed_number="INT-501", ward="ICU", status=BedStatus.OCCUPIED, current_patient_id=patient.id)
    db_session.add(bed)
    db_session.flush()

    admission = Admission(
        patient_id=patient.id,
        primary_diagnosis="Severe Asthma",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.DISCHARGING,
        bed_id=bed.id,
    )
    db_session.add(admission)
    db_session.flush()

    hosp = Hospital(
        name="St. Jude General",
        latitude=13.0827,
        longitude=80.2707,
        specialties=["Pulmonology", "Emergency Medicine"],
        contact_number="+91-44-23456789",
    )
    db_session.add(hosp)
    db_session.flush()

    cap = HospitalCapacity(
        hospital_id=hosp.id,
        specialty="Pulmonology",
        total_beds=10,
        available_beds=5,
    )
    db_session.add(cap)

    decision = ClinicalDecision(
        patient_id=patient.id,
        admission_id=admission.id,
        decision_type=ClinicalDecisionType.TRANSFER,
        transfer_urgency="non_emergency",
        reason="Needs specialized Pulmonology ICU care.",
        required_specialty="Pulmonology",
        decided_by=doctor.id,
        status="confirmed",
    )
    db_session.add(decision)

    report = DischargeReport(
        patient_id=patient.id,
        admission_id=admission.id,
        generated_content="Patient fully recovered.",
        generation_provider="replicate",
        generation_model="openai/gpt-5.6-luna",
        status=DischargeReportStatus.GENERATED,
    )
    db_session.add(report)
    db_session.commit()

    from app.services.discharge_service import DischargeService
    discharge_svc = DischargeService(db_session)
    discharge_svc.approve_report(report.id, doctor)

    # Transfer patient setup
    patient_trf = Patient(
        patient_code="PT-INT-TRF",
        first_name="Raj",
        last_name="Kapoor",
        date_of_birth=datetime(1980, 1, 1).date(),
        gender="Male",
    )
    db_session.add(patient_trf)
    db_session.flush()

    bed_trf = Bed(bed_number="INT-502", ward="ICU", status=BedStatus.OCCUPIED, current_patient_id=patient_trf.id)
    db_session.add(bed_trf)
    db_session.flush()

    admission_trf = Admission(
        patient_id=patient_trf.id,
        primary_diagnosis="Acute Respiratory Failure",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.TRANSFER_PENDING,
        bed_id=bed_trf.id,
    )
    db_session.add(admission_trf)
    db_session.flush()

    decision = ClinicalDecision(
        patient_id=patient_trf.id,
        admission_id=admission_trf.id,
        decision_type=ClinicalDecisionType.TRANSFER,
        transfer_urgency="non_emergency",
        reason="Needs specialized Pulmonology ICU care.",
        required_specialty="Pulmonology",
        decided_by=doctor.id,
        status="confirmed",
    )
    db_session.add(decision)
    db_session.flush()

    transfer = Transfer(
        patient_id=patient_trf.id,
        admission_id=admission_trf.id,
        clinical_decision_id=decision.id,
        sending_hospital_id=hosp.id,
        receiving_hospital_id=hosp.id,
        required_specialty="Pulmonology",
        emergency=False,
        status=TransferStatus.ACCEPTED,
    )
    db_session.add(transfer)
    db_session.commit()

    return {
        "doctor": doctor,
        "patient": patient,
        "bed": bed,
        "admission": admission,
        "admission_trf": admission_trf,
        "hospital": hosp,
        "transfer": transfer,
        "report": report,
    }


def test_internal_api_key_security(client: TestClient, internal_test_env):
    """Verify missing or invalid X-Internal-API-Key returns HTTP 403 Forbidden."""
    bed_id = internal_test_env["bed"].id

    # 1. No key
    res = client.post(f"/api/internal/beds/{bed_id}/start-release")
    assert res.status_code == 403 or res.status_code == 422

    # 2. Invalid key
    res = client.post(
        f"/api/internal/beds/{bed_id}/start-release",
        headers={"X-Internal-API-Key": "wrong-secret-key"},
    )
    assert res.status_code == 403

    # 3. Valid key
    res = client.post(
        f"/api/internal/beds/{bed_id}/start-release",
        headers={"X-Internal-API-Key": settings.INTERNAL_API_KEY},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] == "vacating"


def test_internal_actions_idempotency(client: TestClient, internal_test_env):
    """Verify internal endpoints handle duplicate calls gracefully."""
    headers = {"X-Internal-API-Key": settings.INTERNAL_API_KEY}
    admission_trf_id = internal_test_env["admission_trf"].id
    admission_id = internal_test_env["admission"].id
    transfer_id = internal_test_env["transfer"].id

    # 1. Start transfer matching
    res1 = client.post(f"/api/internal/admissions/{admission_trf_id}/start-transfer-matching", headers=headers)
    assert res1.status_code == 200
    res2 = client.post(f"/api/internal/admissions/{admission_trf_id}/start-transfer-matching", headers=headers)
    assert res2.status_code == 200

    # 2. Billing clearance creation
    res_b1 = client.post(f"/api/internal/admissions/{admission_id}/billing-clearance", headers=headers)
    assert res_b1.status_code == 200
    res_b2 = client.post(f"/api/internal/admissions/{admission_id}/billing-clearance", headers=headers)
    assert res_b2.status_code == 200
    assert res_b1.json()["billing_id"] == res_b2.json()["billing_id"]

    # 3. Ambulance dispatch
    res_a1 = client.post(f"/api/internal/transfers/{transfer_id}/dispatch-ambulance", headers=headers)
    assert res_a1.status_code == 200
    res_a2 = client.post(f"/api/internal/transfers/{transfer_id}/dispatch-ambulance", headers=headers)
    assert res_a2.status_code == 200
    assert res_a1.json()["dispatch_id"] == res_a2.json()["dispatch_id"]
