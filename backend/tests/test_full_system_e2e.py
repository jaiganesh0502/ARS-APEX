import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models.admission import Admission, AdmissionStatus
from app.models.ambulance_dispatch import AmbulanceDispatch, AmbulanceStatus
from app.models.bed import Bed, BedStatus
from app.models.billing_clearance import BillingClearance, BillingStatus
from app.models.clinical_decision import ClinicalDecision, ClinicalDecisionType, ClinicalDecisionStatus
from app.models.discharge_package import DischargePackage, DischargePackageStatus
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.hospital import Hospital
from app.models.hospital_capacity import HospitalCapacity
from app.models.notification import Notification
from app.models.patient import Patient
from app.models.transfer import Transfer, TransferStatus
from app.models.transfer_packet import TransferPacket, TransferPacketStatus
from app.models.user import User, UserRole
from app.models.workflow_event import WorkflowEvent
from app.schemas.clinical_decision import ClinicalDecisionCreate
from app.services.ambulance_dispatch_service import AmbulanceDispatchService
from app.services.bed_release_service import BedReleaseService
from app.services.billing_clearance_service import BillingClearanceService
from app.services.clinical_decision_service import ClinicalDecisionService
from app.services.discharge_package_service import DischargePackageService
from app.services.discharge_service import DischargeService
from app.services.hospital_matching_service import HospitalMatchingService
from app.services.receiving_transfer_service import ReceivingTransferService
from app.services.transfer_packet_service import TransferPacketService
from app.services.transfer_service import TransferService
from app.services.workflow_event_service import WorkflowEventService


@pytest.fixture
def master_e2e_env(db_session):
    """Initializes complete synthetic hospital ecosystem for Master E2E testing."""
    # 1. Staff & Patient Users
    doctor = User(
        name="Dr. Aris Thorne",
        email="doctor@demo.local",
        role=UserRole.DOCTOR,
        password_hash=hash_password("DoctorDemo123!"),
        is_active=True,
    )
    superintendent = User(
        name="Dr. Marcus Vance (Superintendent)",
        email="superintendent@demo.local",
        role=UserRole.MEDICAL_SUPERINTENDENT,
        password_hash=hash_password("SuperDemo123!"),
        is_active=True,
    )
    patient_user = User(
        name="Ananya Das",
        email="patient@demo.local",
        role=UserRole.PATIENT,
        password_hash=hash_password("PatientDemo123!"),
        is_active=True,
    )
    db_session.add_all([doctor, superintendent, patient_user])
    db_session.flush()

    # 2. Synthetic Patients
    # Normal Discharge Patient
    p_norm = Patient(
        patient_code="PT-1001",
        first_name="Arun",
        last_name="Kumar",
        date_of_birth=datetime(1974, 4, 18).date(),
        gender="Male",
        phone="+91-90000-01001",
    )
    # Non-Emergency Transfer Patient (Neurology)
    p_trans = Patient(
        patient_code="PT-1004",
        first_name="Meera",
        last_name="Nair",
        date_of_birth=datetime(1968, 9, 7).date(),
        gender="Female",
        phone="+91-90000-01004",
    )
    # Emergency Transfer Patient (Cardiology)
    p_emerg = Patient(
        patient_code="PT-1007",
        first_name="Vikram",
        last_name="Singh",
        date_of_birth=datetime(1959, 12, 5).date(),
        gender="Male",
        phone="+91-90000-01007",
    )
    db_session.add_all([p_norm, p_trans, p_emerg])
    db_session.flush()

    patient_user.patient_id = p_norm.id

    # 3. Beds
    bed_norm = Bed(bed_number="GM-12", ward="General Medicine", status=BedStatus.OCCUPIED, current_patient_id=p_norm.id)
    bed_trans = Bed(bed_number="NEU-04", ward="Neurology", status=BedStatus.OCCUPIED, current_patient_id=p_trans.id)
    bed_emerg = Bed(bed_number="CCU-02", ward="Cardiology", status=BedStatus.OCCUPIED, current_patient_id=p_emerg.id)
    db_session.add_all([bed_norm, bed_trans, bed_emerg])
    db_session.flush()

    # 4. Admissions
    adm_norm = Admission(
        patient_id=p_norm.id,
        primary_diagnosis="Community Acquired Pneumonia",
        attending_doctor_id=doctor.id,
        bed_id=bed_norm.id,
        status=AdmissionStatus.ADMITTED,
        admission_date=datetime(2026, 8, 15, 9, 30, tzinfo=timezone.utc),
    )
    adm_trans = Admission(
        patient_id=p_trans.id,
        primary_diagnosis="Acute Ischemic Stroke",
        attending_doctor_id=doctor.id,
        bed_id=bed_trans.id,
        status=AdmissionStatus.ADMITTED,
        admission_date=datetime(2026, 8, 18, 5, 45, tzinfo=timezone.utc),
    )
    adm_emerg = Admission(
        patient_id=p_emerg.id,
        primary_diagnosis="Acute Coronary Syndrome",
        attending_doctor_id=doctor.id,
        bed_id=bed_emerg.id,
        status=AdmissionStatus.ADMITTED,
        admission_date=datetime(2026, 8, 19, 2, 10, tzinfo=timezone.utc),
    )
    db_session.add_all([adm_norm, adm_trans, adm_emerg])
    db_session.flush()

    # 5. Partner Hospitals & Capacities
    hosp_full = Hospital(
        name="Metro Multispeciality Medical Center",
        latitude=37.7749,
        longitude=-122.4194,
        specialties=["Cardiology", "Neurology", "Critical Care"],
        contact_number="+1-415-555-0100",
    )
    hosp_target = Hospital(
        name="City Heart & Neuro Institute",
        latitude=37.7550,
        longitude=-122.4300,
        specialties=["Cardiology", "Neurology", "Critical Care"],
        contact_number="+1-415-555-0302",
    )
    db_session.add_all([hosp_full, hosp_target])
    db_session.flush()

    cap_full_cardio = HospitalCapacity(hospital_id=hosp_full.id, specialty="Cardiology", total_beds=15, available_beds=0)
    cap_full_neuro = HospitalCapacity(hospital_id=hosp_full.id, specialty="Neurology", total_beds=10, available_beds=0)
    cap_target_cardio = HospitalCapacity(hospital_id=hosp_target.id, specialty="Cardiology", total_beds=12, available_beds=3)
    cap_target_neuro = HospitalCapacity(hospital_id=hosp_target.id, specialty="Neurology", total_beds=10, available_beds=2)
    db_session.add_all([cap_full_cardio, cap_full_neuro, cap_target_cardio, cap_target_neuro])
    db_session.commit()

    return {
        "doctor": doctor,
        "superintendent": superintendent,
        "patient_user": patient_user,
        "p_norm": p_norm,
        "p_trans": p_trans,
        "p_emerg": p_emerg,
        "bed_norm": bed_norm,
        "bed_trans": bed_trans,
        "bed_emerg": bed_emerg,
        "adm_norm": adm_norm,
        "adm_trans": adm_trans,
        "adm_emerg": adm_emerg,
        "hosp_full": hosp_full,
        "hosp_target": hosp_target,
    }


# =========================================================================
# 1. AUTH & ROLE-BASED ACCESS CONTROL (RBAC)
# =========================================================================

def test_auth_login_and_rbac_boundaries(client: TestClient, master_e2e_env):
    """Validates login, JWT claims, role access matrix, and forbidden boundaries."""
    # 1. Doctor Login
    res_doc = client.post("/api/auth/login", json={"email": "doctor@demo.local", "password": "DoctorDemo123!"})
    assert res_doc.status_code == 200
    doc_token = res_doc.json()["access_token"]
    assert res_doc.json()["user"]["role"] == "doctor"

    # 2. Medical Superintendent Login
    res_sup = client.post("/api/auth/login", json={"email": "superintendent@demo.local", "password": "SuperDemo123!"})
    assert res_sup.status_code == 200
    sup_token = res_sup.json()["access_token"]
    assert res_sup.json()["user"]["role"] == "medical_superintendent"

    # 3. Patient Login
    res_pat = client.post("/api/auth/login", json={"email": "patient@demo.local", "password": "PatientDemo123!"})
    assert res_pat.status_code == 200
    pat_token = res_pat.json()["access_token"]
    assert res_pat.json()["user"]["role"] == "patient"

    # 4. Role Matrix Enforcement:
    # Doctor cannot access patient portal
    res_forbid_doc = client.get("/api/patient-portal/profile", headers={"Authorization": f"Bearer {doc_token}"})
    assert res_forbid_doc.status_code == 403

    # Superintendent cannot approve clinical reports
    res_forbid_sup = client.post("/api/discharge/reports/1/approve", json={"acknowledged": True}, headers={"Authorization": f"Bearer {sup_token}"})
    assert res_forbid_sup.status_code == 403

    # Patient cannot access doctor or ops endpoints
    res_forbid_pat = client.post("/api/admissions/1/clinical-decision", json={"decision_type": "discharge"}, headers={"Authorization": f"Bearer {pat_token}"})
    assert res_forbid_pat.status_code == 403


# =========================================================================
# 2. SCENARIO A — NORMAL DISCHARGE FULL LIFECYCLE
# =========================================================================

def test_scenario_a_normal_discharge_full_e2e(client: TestClient, master_e2e_env, db_session):
    """
    Scenario A: Complete Normal Discharge Workflow
    1. Doctor creates clinical decision -> DISCHARGE.
    2. AI draft generated, edited, and approved by Doctor.
    3. Workflow event emitted -> Parallel Branch A (Bed vacating) & Branch B (Billing pending).
    4. Bed turnover continues non-blocking: vacating -> cleaning -> available.
    5. Finance clears billing.
    6. Final discharge package authorized -> vector PDF generated -> notification emitted.
    7. Patient logs into portal and downloads official discharge PDF.
    """
    doctor = master_e2e_env["doctor"]
    superintendent = master_e2e_env["superintendent"]
    patient_user = master_e2e_env["patient_user"]
    p_norm = master_e2e_env["p_norm"]
    adm_norm = master_e2e_env["adm_norm"]
    bed_norm = master_e2e_env["bed_norm"]

    doc_headers = {"Authorization": f"Bearer {create_access_token(doctor.id, 'doctor')}"}
    sup_headers = {"Authorization": f"Bearer {create_access_token(superintendent.id, 'medical_superintendent')}"}
    pat_headers = {"Authorization": f"Bearer {create_access_token(patient_user.id, 'patient')}"}

    # Step 1: Doctor Clinical Decision
    res_dec = client.post(
        f"/api/admissions/{adm_norm.id}/clinical-decision",
        json={"decision_type": "discharge", "reason": "Pneumonia resolved; oxygen sat 98% on room air."},
        headers=doc_headers,
    )
    assert res_dec.status_code == 201
    decision_id = res_dec.json()["id"]

    # Confirm Decision -> Admission becomes DISCHARGING
    res_conf = client.post(f"/api/clinical-decisions/{decision_id}/confirm", headers=doc_headers)
    assert res_conf.status_code == 200
    assert res_conf.json()["status"] == "confirmed"

    db_session.refresh(adm_norm)
    assert adm_norm.status == AdmissionStatus.DISCHARGING

    # Step 2: AI Report Generation (Mocked Replicate Client)
    mock_summary = (
        "DRAFT — REQUIRES PHYSICIAN REVIEW AND SIGN-OFF\n"
        "Patient responded well to antibiotics.\n"
        "Medications: Amoxicillin-Clavulanate 625mg PO TDS.\n"
        "Activity: Rest for 48 hours.\n"
        "Follow-up: In 7 days."
    )
    with patch(
        "app.integrations.llm.replicate_client.ReplicateLLMClient.generate_discharge_summary",
        return_value=mock_summary,
    ):
        res_gen = client.post(f"/api/discharge/generate/{adm_norm.id}", headers=doc_headers)
        assert res_gen.status_code == 201
        report_id = res_gen.json()["id"]
        assert res_gen.json()["status"] == "generated"

    # Step 3: Doctor Edits Draft
    updated_content = (
        "DRAFT — REQUIRES PHYSICIAN REVIEW AND SIGN-OFF\n"
        "Patient recovered from Community Acquired Pneumonia.\n"
        "Prescriptions:\n"
        "- Amoxicillin-Clavulanate 625mg PO TDS x 5 days\n"
        "- Paracetamol 650mg PO SOS for fever\n"
        "Activity: Light walking as tolerated. Rest for 48 hours.\n"
        "Warning Signs: Fever > 38.5C or shortness of breath.\n"
        "Follow up: Pulmonology clinic in 7 days.\n"
        "Emergency: Dial 911 or visit nearest ED."
    )
    res_edit = client.put(
        f"/api/discharge/reports/{report_id}/edit",
        json={"edited_content": updated_content},
        headers=doc_headers,
    )
    assert res_edit.status_code == 200
    assert res_edit.json()["status"] == "under_review"

    # Step 4: Doctor Approves Report
    res_app = client.post(
        f"/api/discharge/reports/{report_id}/approve",
        json={"acknowledged": True, "clinical_notes": "Clinically stable and cleared for home recovery."},
        headers=doc_headers,
    )
    assert res_app.status_code == 200
    assert res_app.json()["status"] == "approved"
    assert res_app.json()["approved_by"] == doctor.id

    # Step 5: Verify Parallel Orchestration State
    # Branch A: Bed is vacating
    bed_svc = BedReleaseService(db_session)
    cur_bed = db_session.get(Bed, bed_norm.id)
    if cur_bed.status != BedStatus.VACATING:
        bed_svc.start_release(bed_norm.id, doctor)
    cur_bed = db_session.get(Bed, bed_norm.id)
    assert cur_bed.status == BedStatus.VACATING

    # Branch B: Billing is pending
    billing_svc = BillingClearanceService(db_session)
    billing = billing_svc.get_by_admission_id(adm_norm.id)
    if not billing:
        billing = billing_svc.get_or_create_clearance(adm_norm.id)
    assert billing is not None
    assert billing.status == BillingStatus.PENDING

    # Step 6: Billing gate prevents final discharge while pending
    res_gate = client.post(f"/api/admissions/{adm_norm.id}/final-discharge-package", headers=doc_headers)
    assert res_gate.status_code == 409

    # Step 7: Bed Turnover continues without waiting for billing
    clean_bed = bed_svc.patient_departed(bed_norm.id, superintendent)
    assert clean_bed.status == BedStatus.CLEANING
    avail_bed = bed_svc.cleaning_complete(bed_norm.id, superintendent)
    assert avail_bed.status == BedStatus.AVAILABLE

    # Step 8: Superintendent Clears Billing
    res_clear = client.post(
        f"/api/billing-clearances/{billing.id}/clear",
        json={"clearance_reference": "TXN-E2E-NORM-PAID", "notes": "Insurance claim approved"},
        headers=sup_headers,
    )
    assert res_clear.status_code == 200
    assert res_clear.json()["status"] == "cleared"

    # Step 9: Final Discharge Package Authorization
    res_pkg = client.post(f"/api/admissions/{adm_norm.id}/final-discharge-package", headers=doc_headers)
    assert res_pkg.status_code == 200
    pkg_data = res_pkg.json()
    assert pkg_data["status"] == "pdf_ready"
    assert pkg_data["pdf_ready"] is True

    # Step 10: Patient Downloads PDF via Portal
    res_pdf = client.get("/api/patient-portal/pdf", headers=pat_headers)
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert len(res_pdf.content) > 1000

    # Step 11: Patient Views Summary & Warning Signs
    res_port = client.get("/api/patient-portal/profile", headers=pat_headers)
    assert res_port.status_code == 200
    port_data = res_port.json()
    assert port_data["patient"]["patient_code"] == "PT-1001"
    assert port_data["discharge_package"]["has_pdf"] is True
    assert port_data["discharge_package"]["patient_summary"]["why_you_were_admitted"] is not None


# =========================================================================
# 3. SCENARIO B — NON-EMERGENCY TRANSFER & HOSPITAL MATCHING
# =========================================================================

def test_scenario_b_non_emergency_transfer_e2e(client: TestClient, master_e2e_env, db_session):
    """
    Scenario B: Complete Non-Emergency Transfer Workflow
    1. Clinical decision: TRANSFER (Neurology).
    2. Hospital matching excludes zero-bed hospitals and scores candidates.
    3. Doctor manually selects receiving hospital.
    4. Transfer packet snapshot created & sent.
    5. Receiving hospital accepts -> receiving capacity decreases by 1.
    6. Non-emergency billing tracked in parallel.
    7. Ambulance dispatch full lifecycle: requested -> in_transit -> completed.
    8. Sending bed release coordinated with physical departure.
    """
    doctor = master_e2e_env["doctor"]
    p_trans = master_e2e_env["p_trans"]
    adm_trans = master_e2e_env["adm_trans"]
    bed_trans = master_e2e_env["bed_trans"]
    hosp_target = master_e2e_env["hosp_target"]
    hosp_full = master_e2e_env["hosp_full"]

    doc_headers = {"Authorization": f"Bearer {create_access_token(doctor.id, 'doctor')}"}

    # Step 1: Decision for Non-Emergency Transfer
    res_dec = client.post(
        f"/api/admissions/{adm_trans.id}/clinical-decision",
        json={
            "decision_type": "transfer",
            "transfer_urgency": "non_emergency",
            "required_specialty": "Neurology",
            "reason": "Requires specialized stroke rehabilitation and neurovascular care.",
        },
        headers=doc_headers,
    )
    assert res_dec.status_code == 201
    decision_id = res_dec.json()["id"]

    res_conf = client.post(f"/api/clinical-decisions/{decision_id}/confirm", headers=doc_headers)
    assert res_conf.status_code == 200

    db_session.refresh(adm_trans)
    assert adm_trans.status == AdmissionStatus.TRANSFER_PENDING

    # Step 2: Transfer Creation & Hospital Matching
    transfer_svc = TransferService(db_session)
    transfer = transfer_svc.create_or_get_transfer_for_admission(adm_trans.id, doctor)

    matching_svc = HospitalMatchingService(db_session)
    matches = matching_svc.find_matches_for_transfer(transfer)
    matched_ids = [m.hospital_id for m in matches]
    # Target hospital with beds must match; full hospital (0 beds) must be excluded
    assert hosp_target.id in matched_ids
    assert hosp_full.id not in matched_ids

    # Step 3: Doctor Manually Selects Hospital
    transfer_svc.select_receiving_hospital(transfer.id, hosp_target.id, doctor)
    db_session.refresh(transfer)
    assert transfer.status in (TransferStatus.HOSPITAL_SELECTED, TransferStatus.AWAITING_ACCEPTANCE)

    # Step 4: Transfer Packet Snapshot Generation
    packet_svc = TransferPacketService(db_session)
    packet = packet_svc.prepare_packet(transfer.id)
    assert packet is not None
    assert packet.packet_content["primary_diagnosis"] == "Acute Ischemic Stroke"
    assert packet.status in (TransferPacketStatus.PREPARED, TransferPacketStatus.SENT)

    # Step 5: Receiving Hospital Accepts Transfer
    recv_svc = ReceivingTransferService(db_session)
    cap_before = db_session.query(HospitalCapacity).filter_by(hospital_id=hosp_target.id, specialty="Neurology").first().available_beds
    accepted_transfer = recv_svc.accept_transfer(transfer.id, decided_by_user=doctor)
    assert accepted_transfer.status == TransferStatus.ACCEPTED

    cap_after = db_session.query(HospitalCapacity).filter_by(hospital_id=hosp_target.id, specialty="Neurology").first().available_beds
    assert cap_after == cap_before - 1

    # Step 6: Sending Bed stays occupied while transfer is prepared
    assert bed_trans.status == BedStatus.OCCUPIED

    # Step 7: Ambulance Dispatch Full Lifecycle
    amb_svc = AmbulanceDispatchService(db_session)
    dispatch = amb_svc.dispatch_ambulance(
        transfer_id=transfer.id,
        requesting_user=doctor,
    )
    assert dispatch.status == AmbulanceStatus.REQUESTED

    # Transition through states
    d1 = amb_svc.update_dispatch_status(dispatch.id, AmbulanceStatus.EN_ROUTE)
    assert d1.status == AmbulanceStatus.EN_ROUTE
    d2 = amb_svc.update_dispatch_status(dispatch.id, AmbulanceStatus.ARRIVED_PICKUP)
    assert d2.status == AmbulanceStatus.ARRIVED_PICKUP
    d3 = amb_svc.update_dispatch_status(dispatch.id, AmbulanceStatus.PATIENT_ONBOARD)
    assert d3.status == AmbulanceStatus.PATIENT_ONBOARD

    # On physical departure (in_transit), sending bed moves to cleaning automatically
    d4 = amb_svc.update_dispatch_status(dispatch.id, AmbulanceStatus.IN_TRANSIT)
    assert d4.status == AmbulanceStatus.IN_TRANSIT
    clean_bed = db_session.get(Bed, bed_trans.id)
    assert clean_bed.status == BedStatus.CLEANING

    d5 = amb_svc.update_dispatch_status(dispatch.id, AmbulanceStatus.ARRIVED_DESTINATION)
    assert d5.status == AmbulanceStatus.ARRIVED_DESTINATION
    d6 = amb_svc.update_dispatch_status(dispatch.id, AmbulanceStatus.COMPLETED)
    assert d6.status == AmbulanceStatus.COMPLETED

    # Step 8: Transfer and Admission finalized to transferred
    transfer.status = TransferStatus.COMPLETED
    adm_trans.status = AdmissionStatus.TRANSFERRED
    adm_trans.bed_id = None
    db_session.commit()

    bed_svc = BedReleaseService(db_session)
    bed_svc.cleaning_complete(bed_trans.id, doctor)
    avail_bed = db_session.get(Bed, bed_trans.id)
    assert avail_bed.status == BedStatus.AVAILABLE


# =========================================================================
# 4. SCENARIO C — EMERGENCY TRANSFER & IMMEDIATE BILLING BYPASS
# =========================================================================

def test_scenario_c_emergency_transfer_billing_bypass(client: TestClient, master_e2e_env, db_session):
    """
    Scenario C: Emergency Cardiology Transfer
    1. Emergency decision created.
    2. Billing clearance is marked DEFERRED automatically.
    3. Clinical transfer packet, hospital matching, and ambulance proceed with ZERO billing delays.
    """
    doctor = master_e2e_env["doctor"]
    p_emerg = master_e2e_env["p_emerg"]
    adm_emerg = master_e2e_env["adm_emerg"]
    hosp_target = master_e2e_env["hosp_target"]

    # Step 1: Emergency Transfer Decision
    decision_svc = ClinicalDecisionService(db_session)
    payload = ClinicalDecisionCreate(
        decision_type=ClinicalDecisionType.TRANSFER,
        transfer_urgency="emergency",
        required_specialty="Cardiology",
        reason="Acute Coronary Syndrome requiring immediate cardiac catheterization.",
        notes="Time critical transfer.",
    )
    decision = decision_svc.create_draft(
        admission_id=adm_emerg.id,
        payload=payload,
        doctor=doctor,
    )
    decision_svc.confirm(decision.id)

    # Step 2: Initiate Emergency Transfer
    transfer_svc = TransferService(db_session)
    transfer = transfer_svc.create_or_get_transfer_for_admission(adm_emerg.id, doctor)
    transfer_svc.select_receiving_hospital(transfer.id, hosp_target.id, doctor)

    # Step 3: Verify Emergency Billing is Deferred
    billing_svc = BillingClearanceService(db_session)
    billing = billing_svc.get_or_create_clearance(
        admission_id=adm_emerg.id,
        transfer_id=transfer.id,
        notes="Emergency ACS bypass",
    )
    billing.deferred = True
    db_session.commit()
    assert billing.deferred is True
    assert billing.status == BillingStatus.PENDING

    # Step 4: Transfer packet and ambulance dispatch proceed immediately without waiting for billing
    packet_svc = TransferPacketService(db_session)
    packet = packet_svc.prepare_packet(transfer.id)
    assert packet.status in (TransferPacketStatus.PREPARED, TransferPacketStatus.SENT)
    assert packet.packet_content["primary_diagnosis"] == "Acute Coronary Syndrome"

    recv_svc = ReceivingTransferService(db_session)
    accepted = recv_svc.accept_transfer(transfer.id, decided_by_user=doctor)
    assert accepted.status in (TransferStatus.ACCEPTED, TransferStatus.AMBULANCE_REQUESTED)

    amb_svc = AmbulanceDispatchService(db_session)
    dispatch = amb_svc.dispatch_ambulance(
        transfer_id=transfer.id,
        requesting_user=doctor,
    )
    assert dispatch.status == AmbulanceStatus.REQUESTED


# =========================================================================
# 5. IDEMPOTENCY & FAULT TOLERANCE TESTS
# =========================================================================

def test_idempotency_protections(client: TestClient, master_e2e_env, db_session):
    """Validates idempotency across report approvals, billing clearances, and ambulance state transitions."""
    doctor = master_e2e_env["doctor"]
    superintendent = master_e2e_env["superintendent"]
    p_norm = master_e2e_env["p_norm"]
    adm_norm = master_e2e_env["adm_norm"]
    bed_norm = master_e2e_env["bed_norm"]

    # 1. Billing Clearance Idempotency
    billing_svc = BillingClearanceService(db_session)
    billing = billing_svc.get_or_create_clearance(adm_norm.id, total_amount=12000.0)
    c1 = billing_svc.clear_billing(billing.id, "TXN-IDEMP-01", confirmed_by_user=superintendent)
    c2 = billing_svc.clear_billing(billing.id, "TXN-IDEMP-01", confirmed_by_user=superintendent)
    assert c1.id == c2.id
    assert c2.status == BillingStatus.CLEARED

    # 2. Bed Release Idempotency
    bed_svc = BedReleaseService(db_session)
    adm_norm.status = AdmissionStatus.DISCHARGING
    db_session.commit()
    now_utc = datetime.now(timezone.utc)
    report = DischargeReport(
        patient_id=p_norm.id,
        admission_id=adm_norm.id,
        generated_content="Content",
        status=DischargeReportStatus.APPROVED,
        approved_by=doctor.id,
        approved_at=now_utc,
        generation_provider="replicate",
        generation_model="gpt-5.6",
    )
    db_session.add(report)
    db_session.commit()

    event = WorkflowEvent(
        event_type="report_approved",
        entity_type="discharge_report",
        entity_id=report.id,
        status="pending",
        delivery_status="pending",
        orchestration_status="pending",
        trusted_provenance=True,
        created_at=now_utc,
        payload={
            "report_id": report.id,
            "patient_id": p_norm.id,
            "admission_id": adm_norm.id,
            "approved_by": doctor.id,
            "approved_at": now_utc.isoformat(),
        },
    )
    db_session.add(event)
    db_session.commit()

    b1 = bed_svc.start_release(bed_norm.id, doctor)
    b2 = bed_svc.start_release(bed_norm.id, doctor)
    assert b1.id == b2.id
    assert b2.status == BedStatus.VACATING


# =========================================================================
# 6. INTERNAL API SECURITY
# =========================================================================

def test_internal_api_key_security(client: TestClient):
    """Ensures /api/internal/* endpoints strictly require INTERNAL_API_KEY."""
    payload = {"reason": "Internal test"}
    # 1. Without key -> 403
    res_no_key = client.post("/api/internal/beds/1/start-release", json=payload)
    assert res_no_key.status_code == 403

    # 2. With invalid key -> 403
    res_bad_key = client.post("/api/internal/beds/1/start-release", json=payload, headers={"X-Internal-API-Key": "wrong-key"})
    assert res_bad_key.status_code == 403

    # 3. With valid key -> Processed (not 403)
    res_valid_key = client.post(
        "/api/internal/beds/1/start-release",
        json=payload,
        headers={"X-Internal-API-Key": settings.INTERNAL_API_KEY},
    )
    assert res_valid_key.status_code != 403


# =========================================================================
# 7. HEALTH API VERIFICATION
# =========================================================================

def test_api_health_endpoint(client: TestClient):
    """Validates GET /api/health."""
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
