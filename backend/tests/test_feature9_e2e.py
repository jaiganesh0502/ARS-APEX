import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.models.admission import Admission, AdmissionStatus
from app.models.bed import Bed, BedStatus
from app.models.billing_clearance import BillingClearance, BillingStatus
from app.models.clinical_decision import ClinicalDecision, ClinicalDecisionType
from app.models.discharge_package import DischargePackage, DischargePackageStatus
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.hospital import Hospital
from app.models.hospital_capacity import HospitalCapacity
from app.models.patient import Patient
from app.models.transfer import Transfer, TransferStatus
from app.models.user import User, UserRole
from app.services.bed_release_service import BedReleaseService
from app.services.discharge_service import DischargeService
from app.services.receiving_transfer_service import ReceivingTransferService
from app.services.transfer_packet_service import TransferPacketService
from app.services.transfer_service import TransferService


def test_feature9_e2e_normal_discharge_to_pdf_package(client: TestClient, db_session):
    """
    Full End-to-End Test for Normal Discharge:
    1. Patient admission & AI report generation.
    2. Doctor reviews and approves report.
    3. Bed turnover proceeds non-blocking (occupied -> vacating -> cleaning -> available).
    4. Concurrently, billing is pending -> finalization rejected.
    5. Finance confirms billing -> cleared.
    6. Final discharge package authorized -> patient summary & vector PDF generated.
    7. PDF downloaded and verified.
    8. In-app notification verified in inbox.
    """
    doctor = User(name="Dr. E2E Lead", email="lead.f9@hospital.org", role=UserRole.DOCTOR)
    patient = Patient(
        patient_code="PT-F9-E2E",
        first_name="Arjun",
        last_name="Rampal",
        date_of_birth=datetime(1985, 2, 14).date(),
        gender="Male",
    )
    db_session.add_all([doctor, patient])
    db_session.flush()

    bed = Bed(bed_number="F9-401", ward="General Ward", status=BedStatus.OCCUPIED, current_patient_id=patient.id)
    db_session.add(bed)
    db_session.flush()

    admission = Admission(
        patient_id=patient.id,
        primary_diagnosis="Acute Gastroenteritis with Dehydration",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.DISCHARGING,
        bed_id=bed.id,
    )
    db_session.add(admission)
    db_session.flush()

    report = DischargeReport(
        patient_id=patient.id,
        admission_id=admission.id,
        generated_content="Patient fully recovered with IV rehydration.\nPrescriptions:\n- ORS sachets\n- Probiotics 1 cap BD\nDiet: Light bland diet.\nActivity: Rest for 48 hours.\nFollow up: General Medicine OPD in 5 days.",
        generation_provider="replicate",
        generation_model="openai/gpt-5.6-luna",
        status=DischargeReportStatus.GENERATED,
    )
    db_session.add(report)
    db_session.commit()

    # Step 1: Doctor approves discharge report
    discharge_svc = DischargeService(db_session)
    discharge_svc.approve_report(report.id, doctor)

    # Step 2: Bed Turnover starts in parallel (non-blocking)
    bed_svc = BedReleaseService(db_session)
    vac_bed = bed_svc.start_release(bed.id, doctor)
    assert vac_bed.status == BedStatus.VACATING

    # Step 3: Verify billing is pending & finalization blocked
    res_block = client.post(f"/api/admissions/{admission.id}/final-discharge-package")
    assert res_block.status_code == 409

    # Step 4: Bed turnover completes to CLEANING -> AVAILABLE
    clean_bed = bed_svc.patient_departed(bed.id, doctor)
    assert clean_bed.status == BedStatus.CLEANING
    avail_bed = bed_svc.cleaning_complete(bed.id, doctor)
    assert avail_bed.status == BedStatus.AVAILABLE

    # Step 5: Finance confirms billing clearance
    billing = db_session.query(BillingClearance).filter_by(admission_id=admission.id).first()
    assert billing is not None
    res_clear = client.post(
        f"/api/billing-clearances/{billing.id}/clear",
        json={"clearance_reference": "TXN-F9-FULL-PAID", "notes": "Cashless TPA settled"},
    )
    assert res_clear.status_code == 200
    assert res_clear.json()["status"] == "cleared"

    # Step 6: Final Discharge Package is authorized
    res_pkg = client.post(f"/api/admissions/{admission.id}/final-discharge-package")
    assert res_pkg.status_code == 200
    pkg_data = res_pkg.json()
    assert pkg_data["status"] == "pdf_ready"
    assert pkg_data["pdf_ready"] is True
    assert pkg_data["patient_summary"]["why_you_were_admitted"] is not None
    assert pkg_data["clinical_snapshot"]["clearance_reference"] == "TXN-F9-FULL-PAID"
    pkg_id = pkg_data["id"]

    # Step 7: Download PDF
    res_pdf = client.get(f"/api/discharge-packages/{pkg_id}/pdf")
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert len(res_pdf.content) > 1000

    # Step 8: Check in-app notification delivered
    res_notif = client.get(f"/api/notifications?recipient_reference=PT-F9-E2E")
    assert res_notif.status_code == 200
    notifs = res_notif.json()
    assert notifs["total"] >= 1
    assert notifs["items"][0]["notification_type"] == "discharge_package_ready"


def test_feature9_emergency_transfer_documents_unblocked(client: TestClient, db_session):
    """
    Emergency Transfer Document Independence Test:
    Emergency transfers bypass billing (deferred) and clinical transfer packets
    remain IMMEDIATELY accessible and unaffected by billing clearance gates.
    """
    doctor = User(name="Dr. Trauma Lead", email="trauma.f9@hospital.org", role=UserRole.DOCTOR)
    patient = Patient(
        patient_code="PT-F9-EMG",
        first_name="Ravi",
        last_name="Shastri",
        date_of_birth=datetime(1990, 7, 21).date(),
        gender="Male",
    )
    db_session.add_all([doctor, patient])
    db_session.flush()

    hosp_dest = Hospital(
        name="Apex Neuro Institute",
        latitude=13.0850,
        longitude=80.2750,
        specialties=["Neurosurgery", "Trauma Care"],
        contact_number="+91-44-33334444",
    )
    db_session.add(hosp_dest)
    db_session.flush()

    cap = HospitalCapacity(hospital_id=hosp_dest.id, specialty="Neurosurgery", total_beds=10, available_beds=4)
    db_session.add(cap)
    db_session.flush()

    bed = Bed(bed_number="EMG-901", ward="ICU", status=BedStatus.OCCUPIED, current_patient_id=patient.id)
    db_session.add(bed)
    db_session.flush()

    admission = Admission(
        patient_id=patient.id,
        primary_diagnosis="Intracranial Hemorrhage",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.TRANSFER_PENDING,
        bed_id=bed.id,
    )
    db_session.add(admission)
    db_session.flush()

    decision = ClinicalDecision(
        patient_id=patient.id,
        admission_id=admission.id,
        decision_type=ClinicalDecisionType.TRANSFER,
        transfer_urgency="emergency",
        reason="Emergency craniotomy required.",
        required_specialty="Neurosurgery",
        decided_by=doctor.id,
        status="confirmed",
    )
    db_session.add(decision)
    db_session.commit()

    # Create transfer
    trf_svc = TransferService(db_session)
    transfer = trf_svc.create_or_get_transfer_for_admission(admission.id, requesting_user=doctor)
    transfer.emergency = True
    transfer.receiving_hospital_id = hosp_dest.id
    transfer.required_specialty = "Neurosurgery"
    transfer.status = TransferStatus.HOSPITAL_SELECTED
    db_session.commit()

    # Receiving hospital accepts
    recv_svc = ReceivingTransferService(db_session)
    recv_svc.accept_transfer(transfer.id, notes="OR prepared", decided_by_user=doctor)

    # Verify billing status is DEFERRED
    billing = db_session.query(BillingClearance).filter_by(admission_id=admission.id).first()
    assert billing is not None
    assert billing.status == BillingStatus.DEFERRED
    assert billing.deferred is True

    # Prepare and access clinical transfer packet IMMEDIATELY
    packet_svc = TransferPacketService(db_session)
    packet = packet_svc.prepare_packet(transfer.id)
    assert packet is not None
    assert packet.packet_content["patient_summary"]["patient_code"] == "PT-F9-EMG"
