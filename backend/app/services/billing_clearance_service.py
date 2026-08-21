from datetime import datetime, timezone
import logging
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.admission import Admission, AdmissionStatus
from app.models.billing_clearance import BillingClearance, BillingStatus
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.patient import Patient
from app.models.transfer import Transfer
from app.models.user import User
from app.services.workflow_event_service import WorkflowEventService

logger = logging.getLogger(__name__)


class BillingClearanceService:
    """
    Manages hospital billing clearance gates, emergency deferrals, and discharge finalizations.
    """

    def __init__(self, db: Session):
        self.db = db
        self.event_svc = WorkflowEventService(db)

    @staticmethod
    def requires_billing_clearance(case_type: str, emergency: bool = False) -> bool:
        """
        Centralized domain rule:
        - Normal discharge -> True
        - Non-emergency transfer -> True
        - Emergency transfer -> False
        """
        if emergency:
            return False
        if case_type in ("discharge", "transfer"):
            return True
        return True

    def get_by_admission_id(self, admission_id: int) -> Optional[BillingClearance]:
        return (
            self.db.query(BillingClearance)
            .filter(BillingClearance.admission_id == admission_id)
            .order_by(BillingClearance.id.desc())
            .first()
        )

    def get_by_id(self, billing_id: int) -> Optional[BillingClearance]:
        return self.db.query(BillingClearance).filter(BillingClearance.id == billing_id).first()

    def get_or_create_clearance(
        self,
        admission_id: int,
        transfer_id: Optional[int] = None,
        discharge_report_id: Optional[int] = None,
        total_amount: Optional[float] = None,
        outstanding_amount: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> BillingClearance:
        """
        Create or retrieve billing clearance for an admission. Idempotent.
        """
        existing = self.get_by_admission_id(admission_id)
        if existing:
            if transfer_id and not existing.transfer_id:
                existing.transfer_id = transfer_id
            if discharge_report_id and not existing.discharge_report_id:
                existing.discharge_report_id = discharge_report_id
            self.db.commit()
            self.db.refresh(existing)
            return existing

        admission = self.db.query(Admission).filter(Admission.id == admission_id).first()
        if not admission:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")

        # Synthetic default amounts for MVP demo
        default_total = total_amount if total_amount is not None else 18500.00
        default_out = outstanding_amount if outstanding_amount is not None else default_total

        clearance = BillingClearance(
            patient_id=admission.patient_id,
            admission_id=admission.id,
            transfer_id=transfer_id,
            discharge_report_id=discharge_report_id,
            status=BillingStatus.PENDING,
            total_amount=default_total,
            amount_paid=0.00,
            outstanding_amount=default_out,
            deferred=False,
            notes=notes or "Awaiting finance department billing verification.",
        )
        self.db.add(clearance)
        self.db.commit()
        self.db.refresh(clearance)

        # Emit audit events
        self.event_svc.record_event(
            event_type="billing_clearance_created",
            entity_type="billing_clearance",
            entity_id=clearance.id,
            payload={
                "billing_id": clearance.id,
                "admission_id": clearance.admission_id,
                "patient_id": clearance.patient_id,
                "status": clearance.status.value,
                "outstanding_amount": float(clearance.outstanding_amount or 0.0),
            },
        )
        self.event_svc.record_event(
            event_type="billing_clearance_pending",
            entity_type="billing_clearance",
            entity_id=clearance.id,
            payload={
                "billing_id": clearance.id,
                "admission_id": clearance.admission_id,
                "status": "pending",
            },
        )

        logger.info(f"Created pending billing clearance #{clearance.id} for admission #{admission_id}")
        return clearance

    def clear_billing(
        self,
        billing_id: int,
        clearance_reference: str,
        notes: Optional[str] = None,
        confirmed_by_user: Optional[User] = None,
    ) -> BillingClearance:
        """
        Confirm billing clearance (simulating finance department approval). Idempotent.
        """
        clearance = self.get_by_id(billing_id)
        if not clearance:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing clearance not found")

        # Idempotent return if already cleared
        if clearance.status == BillingStatus.CLEARED:
            logger.info(f"Billing clearance #{billing_id} is already CLEARED. Returning idempotent record.")
            return clearance

        now = datetime.now(timezone.utc)
        clearance.status = BillingStatus.CLEARED
        clearance.clearance_reference = clearance_reference
        clearance.confirmed_at = now
        clearance.confirmed_by = confirmed_by_user.id if confirmed_by_user else None
        clearance.amount_paid = clearance.total_amount
        clearance.outstanding_amount = 0.00
        if notes:
            clearance.notes = f"{clearance.notes or ''}\n[Clearance Note]: {notes}".strip()

        self.db.commit()
        self.db.refresh(clearance)

        # Emit billing_cleared event for n8n continuation
        self.event_svc.record_event(
            event_type="billing_cleared",
            entity_type="billing_clearance",
            entity_id=clearance.id,
            payload={
                "billing_id": clearance.id,
                "admission_id": clearance.admission_id,
                "patient_id": clearance.patient_id,
                "clearance_reference": clearance.clearance_reference,
                "confirmed_at": now.isoformat(),
            },
        )

        logger.info(f"Cleared billing clearance #{clearance.id} (Ref: {clearance_reference})")

        # Evaluate dual clearance and auto-dispatch ambulance / bed turnover
        try:
            from app.services.billing_service import BillingService
            BillingService(self.db).evaluate_discharge_readiness(clearance.admission_id)
        except Exception as e:
            logger.warning("Discharge readiness evaluation on clear_billing encountered: %s", e)

        return clearance

    def defer_billing_for_emergency(
        self,
        admission_id: int,
        transfer_id: Optional[int] = None,
    ) -> BillingClearance:
        """
        Emergency transfers skip billing gate: status = deferred, deferred = True.
        """
        existing = self.get_by_admission_id(admission_id)
        if existing:
            existing.status = BillingStatus.DEFERRED
            existing.deferred = True
            existing.notes = "Billing clearance deferred for emergency priority transfer."
            if transfer_id:
                existing.transfer_id = transfer_id
            self.db.commit()
            self.db.refresh(existing)
            clearance = existing
        else:
            admission = self.db.query(Admission).filter(Admission.id == admission_id).first()
            if not admission:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")

            clearance = BillingClearance(
                patient_id=admission.patient_id,
                admission_id=admission.id,
                transfer_id=transfer_id,
                status=BillingStatus.DEFERRED,
                deferred=True,
                total_amount=0.00,
                amount_paid=0.00,
                outstanding_amount=0.00,
                notes="Billing clearance deferred for emergency priority transfer.",
            )
            self.db.add(clearance)
            self.db.commit()
            self.db.refresh(clearance)

        self.event_svc.record_event(
            event_type="billing_deferred",
            entity_type="billing_clearance",
            entity_id=clearance.id,
            payload={
                "billing_id": clearance.id,
                "admission_id": clearance.admission_id,
                "transfer_id": transfer_id,
                "status": "deferred",
                "emergency": True,
            },
        )
        logger.info(f"Deferred billing clearance #{clearance.id} for emergency transfer #{transfer_id}")
        return clearance

    def finalize_discharge_authorization(
        self,
        admission_id: int,
    ) -> Dict[str, Any]:
        """
        Finalize patient-facing discharge authorization.
        Strictly requires:
        1. DischargeReport.status == APPROVED
        2. BillingClearance.status == CLEARED (or DEFERRED)
        """
        admission = self.db.query(Admission).filter(Admission.id == admission_id).first()
        if not admission:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")

        report = (
            self.db.query(DischargeReport)
            .filter(DischargeReport.admission_id == admission_id)
            .order_by(DischargeReport.id.desc())
            .first()
        )
        if not report or report.status != DischargeReportStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot finalize discharge: AI discharge report has not been approved by physician.",
            )

        billing = self.get_by_admission_id(admission_id)
        if not billing or (billing.status not in (BillingStatus.CLEARED, BillingStatus.DEFERRED, BillingStatus.WAIVED)):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot finalize discharge: Billing clearance is pending confirmation.",
            )

        # Emit final authorization event
        now = datetime.now(timezone.utc)
        self.event_svc.record_event(
            event_type="final_discharge_authorized",
            entity_type="admission",
            entity_id=admission_id,
            payload={
                "admission_id": admission_id,
                "patient_id": admission.patient_id,
                "report_id": report.id,
                "billing_id": billing.id,
                "authorized_at": now.isoformat(),
            },
        )

        return {
            "success": True,
            "admission_id": admission_id,
            "patient_id": admission.patient_id,
            "report_id": report.id,
            "billing_id": billing.id,
            "billing_status": billing.status.value,
            "authorized_at": now.isoformat(),
            "message": "Final discharge handoff authorized successfully.",
        }

    def list_clearances(
        self,
        status: Optional[BillingStatus] = None,
        deferred: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[BillingClearance]:
        query = self.db.query(BillingClearance)
        if status:
            query = query.filter(BillingClearance.status == status)
        if deferred is not None:
            query = query.filter(BillingClearance.deferred == deferred)
        return query.order_by(BillingClearance.created_at.desc()).offset(skip).limit(limit).all()
