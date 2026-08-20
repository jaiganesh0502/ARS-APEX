from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.admission import Admission, AdmissionStatus
from app.models.billing_clearance import BillingClearance, BillingStatus
from app.models.charge_master import ChargeCategory, ChargeMasterItem
from app.models.clinical_decision import ClinicalDecision, ClinicalDecisionStatus, ClinicalDecisionType
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.invoice import Invoice, InvoiceLineItem, PaymentMethod, PaymentStatus
from app.models.patient import Patient
from app.models.payment_transaction import PaymentTransaction
from app.models.transfer import Transfer, TransferStatus
from app.models.user import User, UserRole
from app.events.publisher import EventPublisher
from app.services.charge_master_service import ChargeMasterService

logger = logging.getLogger(__name__)


class BillingService:
    """
    Deterministic hospital invoice calculation, payment processing, and discharge readiness orchestration.
    """

    def __init__(self, db: Session):
        self.db = db
        self.charge_master_svc = ChargeMasterService(db)

    def generate_or_get_invoice(self, admission_id: int, auto_commit: bool = True) -> Invoice:
        # Ensure standard ChargeMaster catalog is populated
        self.charge_master_svc.seed_defaults_if_empty()

        admission = self.db.get(Admission, admission_id)
        if not admission:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")

        # Check existing invoice
        existing_invoice = self.db.query(Invoice).filter(Invoice.admission_id == admission_id).first()
        if existing_invoice:
            return existing_invoice

        # Get or create linked BillingClearance
        billing_clearance = self.db.query(BillingClearance).filter(BillingClearance.admission_id == admission_id).first()
        if not billing_clearance:
            billing_clearance = BillingClearance(
                patient_id=admission.patient_id,
                admission_id=admission.id,
                status=BillingStatus.PENDING,
            )
            self.db.add(billing_clearance)
            self.db.flush()

        # Check emergency transfer bypass
        active_transfer = self.db.query(Transfer).filter(Transfer.admission_id == admission_id).first()
        is_emergency = active_transfer.emergency if active_transfer else False

        invoice_no = f"INV-{datetime.now(timezone.utc).year}-{admission.id:04d}"
        invoice = Invoice(
            invoice_number=invoice_no,
            admission_id=admission.id,
            patient_id=admission.patient_id,
            billing_clearance_id=billing_clearance.id,
            payment_status=PaymentStatus.DEFERRED if is_emergency else PaymentStatus.PENDING,
        )
        self.db.add(invoice)
        self.db.flush()

        # 1. Deterministic Calculation of Line Items
        line_items: List[InvoiceLineItem] = []

        # A. Room / Bed Charges
        # Calculate duration in days (minimum 1 day)
        now_utc = datetime.now(timezone.utc)
        adm_date = admission.admission_date or now_utc
        duration_days = max(1, (now_utc.date() - adm_date.date()).days or 1)

        ward_name = admission.bed.ward if admission.bed else "General Medical Ward"
        if "icu" in ward_name.lower():
            room_item = self.charge_master_svc.get_by_code("ROOM_ICU")
        elif "surg" in ward_name.lower():
            room_item = self.charge_master_svc.get_by_code("ROOM_SURG_WARD")
        else:
            room_item = self.charge_master_svc.get_by_code("ROOM_GEN_WARD")

        if room_item:
            line_items.append(
                InvoiceLineItem(
                    invoice_id=invoice.id,
                    charge_item_id=room_item.id,
                    category=room_item.category.value,
                    description=f"{room_item.name} ({duration_days} day{'s' if duration_days > 1 else ''})",
                    quantity=Decimal(str(duration_days)),
                    unit_price=room_item.unit_price,
                    amount=Decimal(str(duration_days)) * room_item.unit_price,
                    source_reference=f"Ward: {ward_name}, Bed: {admission.bed.bed_number if admission.bed else 'Assigned'}",
                )
            )

        # B. Procedure Charges (Matched from primary diagnosis and medical records)
        diag_lower = (admission.primary_diagnosis or "").lower()
        if "append" in diag_lower:
            proc_item = self.charge_master_svc.get_by_code("PROC_APPENDECTOMY")
        elif "angina" in diag_lower or "coronary" in diag_lower or "cardiac" in diag_lower:
            proc_item = self.charge_master_svc.get_by_code("PROC_CORONARY_ANGIO")
        elif "wound" in diag_lower or "trauma" in diag_lower:
            proc_item = self.charge_master_svc.get_by_code("PROC_WOUND_DEBRIDEMENT")
        else:
            proc_item = self.charge_master_svc.get_by_code("PROC_NEBULIZATION")

        if proc_item:
            line_items.append(
                InvoiceLineItem(
                    invoice_id=invoice.id,
                    charge_item_id=proc_item.id,
                    category=proc_item.category.value,
                    description=proc_item.name,
                    quantity=Decimal("1.00"),
                    unit_price=proc_item.unit_price,
                    amount=proc_item.unit_price,
                    source_reference=f"Primary Diagnosis: {admission.primary_diagnosis}",
                )
            )

        # C. Lab & Diagnostic Investigations
        cbc_item = self.charge_master_svc.get_by_code("LAB_CBC")
        if cbc_item:
            line_items.append(
                InvoiceLineItem(
                    invoice_id=invoice.id,
                    charge_item_id=cbc_item.id,
                    category=cbc_item.category.value,
                    description=cbc_item.name,
                    quantity=Decimal("1.00"),
                    unit_price=cbc_item.unit_price,
                    amount=cbc_item.unit_price,
                    source_reference="Admission Lab Workup",
                )
            )

        ecg_item = self.charge_master_svc.get_by_code("TEST_ECG")
        if ecg_item:
            line_items.append(
                InvoiceLineItem(
                    invoice_id=invoice.id,
                    charge_item_id=ecg_item.id,
                    category=ecg_item.category.value,
                    description=ecg_item.name,
                    quantity=Decimal("1.00"),
                    unit_price=ecg_item.unit_price,
                    amount=ecg_item.unit_price,
                    source_reference="Diagnostic Electrocardiography",
                )
            )

        # D. Nursing & Doctor Consultations
        consult_item = self.charge_master_svc.get_by_code("CONS_ATTENDING")
        if consult_item:
            line_items.append(
                InvoiceLineItem(
                    invoice_id=invoice.id,
                    charge_item_id=consult_item.id,
                    category=consult_item.category.value,
                    description=f"{consult_item.name} ({duration_days} day{'s' if duration_days > 1 else ''})",
                    quantity=Decimal(str(duration_days)),
                    unit_price=consult_item.unit_price,
                    amount=Decimal(str(duration_days)) * consult_item.unit_price,
                    source_reference=f"Doctor: {admission.attending_doctor.name if admission.attending_doctor else 'Attending'}",
                )
            )

        # E. Administered Medications
        med_item = self.charge_master_svc.get_by_code("MED_AMOX_CLAV_625")
        if med_item:
            line_items.append(
                InvoiceLineItem(
                    invoice_id=invoice.id,
                    charge_item_id=med_item.id,
                    category=med_item.category.value,
                    description=med_item.name,
                    quantity=Decimal("1.00"),
                    unit_price=med_item.unit_price,
                    amount=med_item.unit_price,
                    source_reference="Inpatient & Discharge Pharmacy Prescription",
                )
            )

        self.db.add_all(line_items)
        self.db.flush()

        # 2. Compute Deterministic Totals
        subtotal = sum((item.amount for item in line_items), Decimal("0.00"))
        discount = Decimal("0.00")
        tax = (subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
        total = subtotal - discount + tax
        balance = total

        invoice.subtotal = subtotal
        invoice.discount_amount = discount
        invoice.tax_amount = tax
        invoice.total_amount = total
        invoice.amount_paid = Decimal("0.00")
        invoice.balance_amount = balance

        # 3. Generate QR Payment URI
        # Standard UPI Payment String format: upi://pay?pa=...&pn=...&am=...
        qr_uri = (
            f"upi://pay?pa=hospital.billing@bank&pn=Metro+General+Hospital"
            f"&am={balance:.2f}&tr={invoice.invoice_number}&cu=INR&tn=Discharge+Bill+{invoice.invoice_number}"
        )
        invoice.qr_code_uri = qr_uri

        # Sync BillingClearance
        billing_clearance.total_amount = total
        billing_clearance.amount_paid = invoice.amount_paid
        billing_clearance.outstanding_amount = balance
        if is_emergency:
            billing_clearance.status = BillingStatus.DEFERRED
            billing_clearance.deferred = True
            billing_clearance.notes = "Emergency transfer: financial gate bypassed for immediate transport."
        elif balance > Decimal("0.00"):
            billing_clearance.status = BillingStatus.PENDING
            billing_clearance.deferred = False
            billing_clearance.notes = "Awaiting financial settlement."
            billing_clearance.clearance_reference = None
        else:
            billing_clearance.status = BillingStatus.CLEARED
            billing_clearance.deferred = False
            billing_clearance.notes = "All dues settled."

        if auto_commit:
            self.db.commit()
            self.db.refresh(invoice)
            # Emit invoice_generated domain event
            EventPublisher(self.db).publish_event(
                event_type="invoice_generated",
                entity_type="invoice",
                entity_id=invoice.id,
                payload={
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.invoice_number,
                    "admission_id": admission.id,
                    "patient_id": admission.patient_id,
                    "total_amount": float(invoice.total_amount),
                    "balance_amount": float(invoice.balance_amount),
                    "payment_status": invoice.payment_status.value,
                },
            )
        else:
            self.db.flush()

        return invoice

    def record_manual_payment(
        self,
        invoice_id: int,
        amount: Decimal,
        payment_method: str,
        reference: str,
        user: User,
        notes: Optional[str] = None,
    ) -> Invoice:
        invoice = self.db.get(Invoice, invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        if amount <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment amount must be greater than zero")

        tx = PaymentTransaction(
            invoice_id=invoice.id,
            amount=amount,
            payment_method=payment_method,
            transaction_reference=reference,
            payment_status="completed",
            confirmed_by=user.id if user else None,
            confirmed_at=datetime.now(timezone.utc),
            notes=notes,
        )
        self.db.add(tx)

        invoice.amount_paid = (invoice.amount_paid or Decimal("0.00")) + amount
        invoice.balance_amount = max(Decimal("0.00"), invoice.total_amount - invoice.amount_paid)

        if invoice.balance_amount <= Decimal("0.00"):
            invoice.payment_status = PaymentStatus.PAID_MANUAL

        # Sync BillingClearance
        if invoice.billing_clearance:
            invoice.billing_clearance.amount_paid = invoice.amount_paid
            invoice.billing_clearance.outstanding_amount = invoice.balance_amount
            if invoice.balance_amount <= Decimal("0.00"):
                invoice.billing_clearance.status = BillingStatus.CLEARED
                invoice.billing_clearance.confirmed_by = user.id if user else None
                invoice.billing_clearance.confirmed_at = datetime.now(timezone.utc)
                invoice.billing_clearance.clearance_reference = reference

        # In-App Notification for MS on settlement
        if invoice.balance_amount <= Decimal("0.00"):
            from app.models.notification import Notification, NotificationChannel, NotificationType, NotificationStatus
            admission = invoice.admission
            patient = admission.patient if admission else None
            patient_name = f"{patient.first_name} {patient.last_name}" if patient else "Patient"
            patient_code = patient.patient_code if patient else "N/A"
            ward_bed = f"{admission.bed.ward} / {admission.bed.bed_number}" if admission and admission.bed else "Assigned Bed"

            ms_pay_notif = Notification(
                recipient_type="medical_superintendent",
                recipient_reference="superintendent@demo.local",
                channel=NotificationChannel.IN_APP,
                notification_type=NotificationType.DISCHARGE_PACKAGE_READY,
                status=NotificationStatus.DELIVERED,
                subject=f"Payment Settled & Discharge Ready: {patient_name} ({patient_code})",
                message=f"Hospital invoice {invoice.invoice_number} (INR {invoice.total_amount:.2f}) has been paid in full. Patient in {ward_bed} is now DISCHARGE READY for physical bed turnover.",
                related_entity_type="admission",
                related_entity_id=invoice.admission_id,
                created_at=datetime.now(timezone.utc),
                sent_at=datetime.now(timezone.utc),
            )
            self.db.add(ms_pay_notif)

        self.db.commit()
        self.db.refresh(invoice)

        # Emit payment_completed event
        EventPublisher(self.db).publish_event(
            event_type="payment_completed",
            entity_type="invoice",
            entity_id=invoice.id,
            payload={
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "amount": float(amount),
                "payment_method": payment_method,
                "balance_remaining": float(invoice.balance_amount),
                "payment_status": invoice.payment_status.value,
            },
        )

        # Check & update discharge readiness
        self.evaluate_discharge_readiness(invoice.admission_id)
        return invoice

    def handle_online_payment_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Idempotent online payment gateway webhook handler.
        """
        invoice_number = payload.get("invoice_number") or payload.get("tr")
        reference = payload.get("transaction_reference") or payload.get("payment_id") or f"TXN-{int(datetime.now(timezone.utc).timestamp())}"
        amount = Decimal(str(payload.get("amount", "0.00")))

        invoice = self.db.query(Invoice).filter(Invoice.invoice_number == invoice_number).first()
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice '{invoice_number}' not found")

        # Idempotency check: if transaction reference already processed, return existing
        existing_tx = self.db.query(PaymentTransaction).filter(PaymentTransaction.transaction_reference == reference).first()
        if existing_tx:
            return {
                "success": True,
                "message": "Payment already processed",
                "invoice_id": invoice.id,
                "payment_status": invoice.payment_status.value,
                "duplicate": True,
            }

        pay_amount = amount if amount > Decimal("0.00") else invoice.balance_amount

        tx = PaymentTransaction(
            invoice_id=invoice.id,
            amount=pay_amount,
            payment_method=PaymentMethod.ONLINE_GATEWAY.value,
            transaction_reference=reference,
            payment_status="completed",
            confirmed_at=datetime.now(timezone.utc),
            raw_payload=payload,
        )
        self.db.add(tx)

        invoice.amount_paid = (invoice.amount_paid or Decimal("0.00")) + pay_amount
        invoice.balance_amount = max(Decimal("0.00"), invoice.total_amount - invoice.amount_paid)
        invoice.payment_status = PaymentStatus.PAID_ONLINE

        if invoice.billing_clearance:
            invoice.billing_clearance.amount_paid = invoice.amount_paid
            invoice.billing_clearance.outstanding_amount = invoice.balance_amount
            invoice.billing_clearance.status = BillingStatus.CLEARED
            invoice.billing_clearance.confirmed_at = datetime.now(timezone.utc)
            invoice.billing_clearance.clearance_reference = reference

        # In-App Notification for Medical Superintendent
        from app.models.notification import Notification, NotificationChannel, NotificationType, NotificationStatus
        admission = invoice.admission
        patient = admission.patient if admission else None
        patient_name = f"{patient.first_name} {patient.last_name}" if patient else "Patient"
        patient_code = patient.patient_code if patient else "N/A"
        ward_bed = f"{admission.bed.ward} / {admission.bed.bed_number}" if admission and admission.bed else "Assigned Bed"

        ms_online_notif = Notification(
            recipient_type="medical_superintendent",
            recipient_reference="superintendent@demo.local",
            channel=NotificationChannel.IN_APP,
            notification_type=NotificationType.DISCHARGE_PACKAGE_READY,
            status=NotificationStatus.DELIVERED,
            subject=f"Online Payment Settled: {patient_name} ({patient_code})",
            message=f"Patient {patient_name} settled invoice {invoice.invoice_number} (INR {pay_amount:.2f}) via UPI/Online Gateway. Patient in {ward_bed} is DISCHARGE READY.",
            related_entity_type="admission",
            related_entity_id=invoice.admission_id,
            created_at=datetime.now(timezone.utc),
            sent_at=datetime.now(timezone.utc),
        )
        self.db.add(ms_online_notif)

        self.db.commit()
        self.db.refresh(invoice)

        # Emit payment_completed event
        EventPublisher(self.db).publish_event(
            event_type="payment_completed",
            entity_type="invoice",
            entity_id=invoice.id,
            payload={
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "amount": float(pay_amount),
                "payment_method": "online_gateway",
                "transaction_reference": reference,
                "payment_status": invoice.payment_status.value,
            },
        )

        # Check & update discharge readiness
        self.evaluate_discharge_readiness(invoice.admission_id)

        return {
            "success": True,
            "message": "Online payment processed successfully",
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "payment_status": invoice.payment_status.value,
            "balance_amount": float(invoice.balance_amount),
        }

    def evaluate_discharge_readiness(self, admission_id: int) -> bool:
        """
        Evaluates dual-clearance gate:
        When clinical_report == APPROVED AND payment_status IN (PAID_ONLINE, PAID_MANUAL, DEFERRED)
        -> Sets admission.discharge_ready = True and emits 'discharge_ready'.
        """
        admission = self.db.get(Admission, admission_id)
        if not admission:
            return False

        # 1. Clinical Clearance Check
        report = self.db.query(DischargeReport).filter(DischargeReport.admission_id == admission_id).first()
        clinical_cleared = report is not None and report.status == DischargeReportStatus.APPROVED

        # For transfer cases
        transfer = self.db.query(Transfer).filter(Transfer.admission_id == admission_id).first()
        if transfer and transfer.status in (TransferStatus.ACCEPTED, TransferStatus.IN_TRANSIT, TransferStatus.COMPLETED):
            clinical_cleared = True

        # 2. Payment Clearance Check
        invoice = self.db.query(Invoice).filter(Invoice.admission_id == admission_id).first()
        payment_cleared = False
        if invoice:
            payment_cleared = invoice.payment_status in (PaymentStatus.PAID_ONLINE, PaymentStatus.PAID_MANUAL, PaymentStatus.DEFERRED)
        elif transfer and transfer.emergency:
            payment_cleared = True

        if clinical_cleared and payment_cleared:
            admission.discharge_ready = True

            # Parallel Bed Release: Ensure bed transitions to VACATING
            if admission.bed_id:
                from app.models.bed import Bed, BedStatus
                bed = self.db.query(Bed).filter(Bed.id == admission.bed_id).first()
                if bed and bed.status == BedStatus.OCCUPIED:
                    bed.status = BedStatus.VACATING

            # Auto-compile DischargePackage and PDF if not already created
            from app.models.discharge_package import DischargePackage
            from app.services.discharge_package_service import DischargePackageService
            from app.models.user import User, UserRole
            existing_pkg = self.db.query(DischargePackage).filter(DischargePackage.admission_id == admission.id).first()
            if not existing_pkg:
                system_user = self.db.query(User).filter(User.role == UserRole.MEDICAL_SUPERINTENDENT).first()
                try:
                    pkg_svc = DischargePackageService(self.db)
                    pkg_svc.finalize_discharge_package(
                        admission_id=admission.id,
                        authorizing_user=system_user,
                        notes="Automated discharge authorization on dual clearance confirmation.",
                    )
                except Exception as e:
                    logger.warning("Auto discharge package creation encountered: %s", e)

            self.db.commit()

            logger.info("Admission %s is now DISCHARGE READY (Clinical: cleared, Payment: cleared)", admission_id)

            EventPublisher(self.db).publish_event(
                event_type="discharge_ready",
                entity_type="admission",
                entity_id=admission.id,
                payload={
                    "admission_id": admission.id,
                    "patient_id": admission.patient_id,
                    "bed_id": admission.bed_id,
                    "discharge_ready": True,
                },
            )
            return True

        return False

    def get_invoice(self, invoice_id: int) -> Optional[Invoice]:
        return self.db.get(Invoice, invoice_id)

    def get_invoice_by_admission(self, admission_id: int) -> Optional[Invoice]:
        return self.db.query(Invoice).filter(Invoice.admission_id == admission_id).first()
