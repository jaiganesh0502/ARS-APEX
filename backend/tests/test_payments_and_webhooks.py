from datetime import date
from decimal import Decimal
import pytest
from app.models import (
    Admission,
    AdmissionStatus,
    Bed,
    BedStatus,
    BillingClearance,
    BillingStatus,
    DischargeReport,
    DischargeReportStatus,
    Invoice,
    PaymentStatus,
    Patient,
    User,
    UserRole,
)
from app.services.billing_service import BillingService


def test_receptionist_manual_payment_and_discharge_readiness(db_session):
    patient = Patient(first_name="Vikram", last_name="Singh", patient_code="PT-PAY-1", date_of_birth=date(1980, 11, 10), gender="Male")
    db_session.add(patient)
    db_session.flush()

    doctor = User(name="Dr. Attending", email="docpay@test.org", role=UserRole.DOCTOR, is_active=True)
    receptionist = User(name="Priya (Reception)", email="recpay@test.org", role=UserRole.RECEPTIONIST, is_active=True)
    db_session.add_all([doctor, receptionist])
    db_session.flush()

    bed = Bed(bed_number="MED-12", ward="General Medical Ward", status=BedStatus.OCCUPIED, current_patient_id=patient.id)
    db_session.add(bed)
    db_session.flush()

    admission = Admission(
        patient_id=patient.id,
        attending_doctor_id=doctor.id,
        bed_id=bed.id,
        primary_diagnosis="Gastroenteritis",
        status=AdmissionStatus.DISCHARGING,
        discharge_ready=False,
    )
    db_session.add(admission)
    db_session.flush()

    # Pre-approved clinical report
    report = DischargeReport(
        admission_id=admission.id,
        patient_id=patient.id,
        generated_content="DRAFT clinical summary",
        generation_provider="clinical_document_pipeline",
        generation_model="ocr_extractor_v1",
        status=DischargeReportStatus.APPROVED,
        approved_by=doctor.id,
    )
    db_session.add(report)
    db_session.commit()

    # Generate invoice
    billing_svc = BillingService(db_session)
    invoice = billing_svc.generate_or_get_invoice(admission.id)
    total_amount = invoice.total_amount

    # 1. Partial payment
    partial_amount = Decimal("1000.00")
    billing_svc.record_manual_payment(
        invoice_id=invoice.id,
        amount=partial_amount,
        payment_method="cash",
        reference="RCP-CASH-001",
        user=receptionist,
    )
    db_session.refresh(invoice)
    db_session.refresh(admission)

    assert invoice.amount_paid == partial_amount
    assert invoice.balance_amount == total_amount - partial_amount
    assert invoice.payment_status == PaymentStatus.PENDING
    assert admission.discharge_ready is False  # Not ready yet (balance remains)

    # 2. Final settlement
    remaining_balance = invoice.balance_amount
    billing_svc.record_manual_payment(
        invoice_id=invoice.id,
        amount=remaining_balance,
        payment_method="upi_manual",
        reference="RCP-UPI-002",
        user=receptionist,
    )
    db_session.refresh(invoice)
    db_session.refresh(admission)

    assert invoice.balance_amount == Decimal("0.00")
    assert invoice.payment_status == PaymentStatus.PAID_MANUAL
    assert invoice.billing_clearance.status == BillingStatus.CLEARED
    # Both clinical approved AND payment cleared -> discharge_ready!
    assert admission.discharge_ready is True


def test_online_payment_webhook_idempotency(db_session):
    patient = Patient(first_name="Deepak", last_name="Chopra", patient_code="PT-PAY-2", date_of_birth=date(1975, 6, 25), gender="Male")
    db_session.add(patient)
    db_session.flush()

    doctor = User(name="Dr. Clinician", email="doccli@test.org", role=UserRole.DOCTOR, is_active=True)
    db_session.add(doctor)
    db_session.flush()

    admission = Admission(
        patient_id=patient.id,
        attending_doctor_id=doctor.id,
        primary_diagnosis="Bronchitis",
        status=AdmissionStatus.DISCHARGING,
    )
    db_session.add(admission)
    db_session.commit()

    billing_svc = BillingService(db_session)
    invoice = billing_svc.generate_or_get_invoice(admission.id)

    webhook_payload = {
        "invoice_number": invoice.invoice_number,
        "transaction_reference": "PG-GATEWAY-TXN-998877",
        "amount": float(invoice.total_amount),
        "status": "captured",
    }

    # 1. First webhook delivery
    res1 = billing_svc.handle_online_payment_webhook(webhook_payload)
    assert res1["success"] is True
    assert res1["payment_status"] == PaymentStatus.PAID_ONLINE.value
    assert res1["balance_amount"] == 0.0

    # 2. Duplicate webhook delivery (must be idempotent without double-counting)
    res2 = billing_svc.handle_online_payment_webhook(webhook_payload)
    assert res2["success"] is True
    assert res2.get("duplicate") is True

    db_session.refresh(invoice)
    assert len(invoice.payments) == 1
    assert invoice.amount_paid == invoice.total_amount
