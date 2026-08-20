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
    Hospital,
    Invoice,
    PaymentStatus,
    Patient,
    Transfer,
    TransferStatus,
    User,
    UserRole,
)
from app.services.billing_service import BillingService
from app.services.charge_master_service import ChargeMasterService


def test_charge_master_catalog_lookup(db_session):
    svc = ChargeMasterService(db_session)
    svc.seed_defaults_if_empty()

    items = svc.list_items()
    assert len(items) > 0

    appendectomy = svc.get_by_code("PROC_APPENDECTOMY")
    assert appendectomy is not None
    assert appendectomy.unit_price == Decimal("35000.00")

    icu = svc.get_by_code("ROOM_ICU")
    assert icu is not None
    assert icu.unit_price == Decimal("8500.00")


def test_deterministic_invoice_calculation(db_session):
    # Setup patient, doctor, bed, admission
    patient = Patient(first_name="Ramesh", last_name="Patel", patient_code="PT-BILL-1", date_of_birth=date(1978, 2, 15), gender="Male")
    db_session.add(patient)
    db_session.flush()

    doctor = User(name="Dr. Billing Specialist", email="docbill@test.org", role=UserRole.DOCTOR, is_active=True)
    db_session.add(doctor)
    db_session.flush()

    bed = Bed(bed_number="SURG-01", ward="General Surgery Ward", status=BedStatus.OCCUPIED, current_patient_id=patient.id)
    db_session.add(bed)
    db_session.flush()

    admission = Admission(
        patient_id=patient.id,
        attending_doctor_id=doctor.id,
        bed_id=bed.id,
        primary_diagnosis="Post-op Appendectomy",
        status=AdmissionStatus.DISCHARGING,
    )
    db_session.add(admission)
    db_session.commit()

    # Generate invoice
    billing_svc = BillingService(db_session)
    invoice = billing_svc.generate_or_get_invoice(admission.id)

    assert invoice is not None
    assert invoice.invoice_number.startswith("INV-")
    assert invoice.payment_status == PaymentStatus.PENDING
    assert invoice.subtotal > Decimal("0.00")
    assert invoice.tax_amount == (invoice.subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
    assert invoice.total_amount == invoice.subtotal + invoice.tax_amount
    assert invoice.balance_amount == invoice.total_amount
    assert "upi://pay" in invoice.qr_code_uri

    # Verify line items
    categories = {item.category for item in invoice.line_items}
    assert "room" in categories
    assert "procedure" in categories
    assert "investigation" in categories


def test_emergency_transfer_billing_bypass(db_session):
    patient = Patient(first_name="Anita", last_name="Roy", patient_code="PT-BILL-2", date_of_birth=date(1992, 7, 20), gender="Female")
    db_session.add(patient)
    db_session.flush()

    doctor = User(name="Dr. Emergency", email="docemg@test.org", role=UserRole.DOCTOR, is_active=True)
    hospital = Hospital(name="Origin Hospital", latitude=37.77, longitude=-122.41, specialties=["Cardiology"], contact_number="+1-555-0100")
    db_session.add_all([doctor, hospital])
    db_session.flush()

    admission = Admission(
        patient_id=patient.id,
        attending_doctor_id=doctor.id,
        primary_diagnosis="Acute STEMI Cardiac Shock",
        status=AdmissionStatus.TRANSFER_PENDING,
    )
    db_session.add(admission)
    db_session.flush()

    # Create emergency transfer
    transfer = Transfer(
        admission_id=admission.id,
        patient_id=patient.id,
        sending_hospital_id=hospital.id,
        required_specialty="Cardiology",
        emergency=True,
        status=TransferStatus.MATCHING,
    )
    db_session.add(transfer)
    db_session.commit()

    billing_svc = BillingService(db_session)
    invoice = billing_svc.generate_or_get_invoice(admission.id)

    assert invoice.payment_status == PaymentStatus.DEFERRED
    assert invoice.billing_clearance.status == BillingStatus.DEFERRED
    assert invoice.billing_clearance.deferred is True
