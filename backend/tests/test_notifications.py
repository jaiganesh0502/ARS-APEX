import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.models.admission import Admission, AdmissionStatus
from app.models.bed import Bed, BedStatus
from app.models.billing_clearance import BillingClearance, BillingStatus
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.notification import Notification, NotificationStatus, NotificationType
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.services.discharge_package_service import DischargePackageService
from app.services.discharge_service import DischargeService


@pytest.fixture
def notif_test_env(db_session):
    doctor = User(name="Dr. Notification", email="notif.doc@hospital.org", role=UserRole.DOCTOR)
    db_session.add(doctor)
    db_session.flush()

    patient = Patient(
        patient_code="PT-NOTIF-99",
        first_name="Kavita",
        last_name="Krishnan",
        date_of_birth=datetime(1992, 11, 4).date(),
        gender="Female",
    )
    db_session.add(patient)
    db_session.flush()

    bed = Bed(bed_number="NOTIF-301", ward="Medical", status=BedStatus.OCCUPIED, current_patient_id=patient.id)
    db_session.add(bed)
    db_session.flush()

    admission = Admission(
        patient_id=patient.id,
        primary_diagnosis="Community Acquired Pneumonia",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.DISCHARGING,
        bed_id=bed.id,
    )
    db_session.add(admission)
    db_session.flush()

    report = DischargeReport(
        patient_id=patient.id,
        admission_id=admission.id,
        generated_content="Patient clinically cured. Complete oral antibiotics course.",
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
        total_amount=12000.0,
        amount_paid=12000.0,
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


def test_notification_created_on_package_authorization(client: TestClient, db_session, notif_test_env):
    """
    Verify authorizing a package creates an in-app notification for the patient.
    """
    admission = notif_test_env["admission"]
    report = notif_test_env["report"]
    billing = notif_test_env["billing"]
    doctor = notif_test_env["doctor"]

    discharge_svc = DischargeService(db_session)
    discharge_svc.approve_report(report.id, doctor)

    billing.status = BillingStatus.CLEARED
    billing.clearance_reference = "TXN-NOTIF-01"
    db_session.commit()

    pkg_svc = DischargePackageService(db_session)
    package = pkg_svc.finalize_discharge_package(admission.id, authorizing_user=doctor)

    # Query notifications API
    res = client.get(f"/api/notifications?recipient_reference=PT-NOTIF-99")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    item = data["items"][0]
    assert item["notification_type"] == "discharge_package_ready"
    assert item["related_entity_id"] == package.id
    assert "ready" in item["subject"].lower()

    # Mark as read
    notif_id = item["id"]
    res_read = client.post(f"/api/notifications/{notif_id}/read")
    assert res_read.status_code == 200
    assert res_read.json()["status"] == "read"


def test_duplicate_authorization_does_not_duplicate_notification(db_session, notif_test_env):
    """
    Verify re-authorizing does not spam notifications.
    """
    admission = notif_test_env["admission"]
    report = notif_test_env["report"]
    billing = notif_test_env["billing"]
    doctor = notif_test_env["doctor"]

    discharge_svc = DischargeService(db_session)
    discharge_svc.approve_report(report.id, doctor)

    billing.status = BillingStatus.CLEARED
    billing.clearance_reference = "TXN-NOTIF-01"
    db_session.commit()

    pkg_svc = DischargePackageService(db_session)
    pkg_svc.finalize_discharge_package(admission.id, authorizing_user=doctor)
    count1 = db_session.query(Notification).filter_by(recipient_reference="PT-NOTIF-99").count()

    pkg_svc.finalize_discharge_package(admission.id, authorizing_user=doctor)
    count2 = db_session.query(Notification).filter_by(recipient_reference="PT-NOTIF-99").count()

    assert count1 == count2 == 1
