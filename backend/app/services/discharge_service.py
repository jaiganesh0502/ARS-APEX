from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.services.base import BaseService
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.admission import Admission, AdmissionStatus
from app.models.clinical_decision import ClinicalDecisionStatus, ClinicalDecisionType
from app.models.user import User, UserRole
from app.models.workflow_event import WorkflowEvent
from app.core.config import settings
from app.integrations.llm.client import LLMClientInterface
from app.repositories.clinical_decision_repository import ClinicalDecisionRepository
from app.repositories.discharge_repository import DischargeRepository
from app.services.discharge_context import build_discharge_context


def _is_duplicate_admission_report_error(error: IntegrityError) -> bool:
    """Recognize only the admission-level discharge-report uniqueness constraint."""
    constraint_name = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
    if constraint_name == "uq_discharge_reports_admission":
        return True

    detail = str(error.orig).lower()
    return (
        "uq_discharge_reports_admission" in detail
        or "unique constraint failed: discharge_reports.admission_id" in detail
    )


class DischargeService(BaseService):
    """
    Clinical Discharge Service.
    
    SAFETY CONSTRAINT:
    AI models only generate 'draft' or 'generated' reports.
    A report can ONLY transition to 'approved' via explicit doctor sign-off.
    """

    def __init__(self, db: Session):
        super().__init__(db)
        self.repo = DischargeRepository(db)
        self.clinical_decision_repo = ClinicalDecisionRepository(db)

    def generate_report(
        self, admission_id: int, llm_client: LLMClientInterface
    ) -> DischargeReport:
        """Generate and persist an unapproved report after clinical eligibility checks."""
        admission = self.db.query(Admission).filter(Admission.id == admission_id).first()
        if not admission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admission not found",
            )
        if admission.status != AdmissionStatus.DISCHARGING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Admission must be discharging before generating a report",
            )

        decision = self.clinical_decision_repo.get_active_for_admission(admission_id)
        if (
            not decision
            or decision.status != ClinicalDecisionStatus.CONFIRMED
            or decision.decision_type != ClinicalDecisionType.DISCHARGE
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A confirmed discharge decision is required before generating a report",
            )
        if self.repo.get_by_admission_id(admission_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A discharge report already exists for this admission",
            )

        generated_content = llm_client.generate_discharge_summary(
            build_discharge_context(admission, decision)
        )
        if not isinstance(generated_content, str) or not generated_content.strip():
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI generation returned no content",
            )

        report = DischargeReport(
            patient_id=admission.patient_id,
            admission_id=admission.id,
            generated_content=generated_content.strip(),
            edited_content=None,
            generation_provider="replicate",
            generation_model=settings.LLM_MODEL,
            status=DischargeReportStatus.GENERATED,
            approved_by=None,
            approved_at=None,
        )
        try:
            return self.repo.create(report)
        except IntegrityError as error:
            if not _is_duplicate_admission_report_error(error):
                raise
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A discharge report already exists for this admission",
            ) from error

    def create_ai_draft_report(self, patient_id: int, admission_id: int, generated_content: str) -> DischargeReport:
        """
        Record an AI-generated draft discharge report.
        Strictly sets status to 'generated'. Never auto-approves.
        """
        admission = self.db.query(Admission).filter(Admission.id == admission_id).first()
        if not admission:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")

        report = DischargeReport(
            patient_id=patient_id,
            admission_id=admission_id,
            generated_content=generated_content,
            edited_content=None,
            generation_provider="legacy",
            generation_model="legacy-placeholder",
            status=DischargeReportStatus.GENERATED,
            approved_by=None,
            approved_at=None,
        )
        return self.repo.create(report)

    def edit_report(self, report_id: int, edited_content: str, doctor: User) -> DischargeReport:
        """Doctor modifies the draft content before final approval."""
        if not doctor or doctor.role != UserRole.DOCTOR:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can edit discharge reports")
        if not isinstance(edited_content, str) or not edited_content.strip():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Edited report content cannot be empty")
        report = (
            self.db.query(DischargeReport)
            .populate_existing()
            .with_for_update()
            .filter(DischargeReport.id == report_id)
            .first()
        )
        if not report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge report not found")
        
        if report.status not in {
            DischargeReportStatus.GENERATED,
            DischargeReportStatus.UNDER_REVIEW,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only generated or under-review reports can be edited",
            )

        transition_count = self.db.execute(
            update(DischargeReport)
            .where(
                DischargeReport.id == report.id,
                DischargeReport.status.in_((
                    DischargeReportStatus.GENERATED,
                    DischargeReportStatus.UNDER_REVIEW,
                )),
            )
            .values(
                edited_content=edited_content,
                status=DischargeReportStatus.UNDER_REVIEW,
            )
        ).rowcount
        if transition_count != 1:
            self.db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Discharge report is no longer editable")
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        self.db.refresh(report)
        return report

    def approve_report(
        self, report_id: int, doctor: User, clinical_notes: Optional[str] = None
    ) -> DischargeReport:
        """
        Explicit doctor approval of the discharge report.
        Persists the internal audit event in the same transaction as approval.
        """
        report = (
            self.db.query(DischargeReport)
            .populate_existing()
            .with_for_update()
            .filter(DischargeReport.id == report_id)
            .first()
        )
        if not report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge report not found")

        if not doctor or doctor.role != UserRole.DOCTOR:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can approve discharge reports")
        admission = (
            self.db.query(Admission)
            .populate_existing()
            .with_for_update()
            .filter(Admission.id == report.admission_id)
            .first()
        )
        if not admission:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")
        if report.status == DischargeReportStatus.APPROVED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Discharge report is already approved")
        if report.status not in {
            DischargeReportStatus.GENERATED,
            DischargeReportStatus.UNDER_REVIEW,
        }:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Discharge report is not ready for approval")
        if not isinstance(report.effective_content, str) or not report.effective_content.strip():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Discharge report content cannot be empty before approval")
        if admission.status not in (AdmissionStatus.ADMITTED, AdmissionStatus.DISCHARGING):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Admission must be active before report approval")

        if admission.status == AdmissionStatus.ADMITTED:
            admission.status = AdmissionStatus.DISCHARGING

        now = datetime.now(timezone.utc)
        transition_count = self.db.execute(
            update(DischargeReport)
            .where(
                DischargeReport.id == report.id,
                DischargeReport.status.in_((
                    DischargeReportStatus.GENERATED,
                    DischargeReportStatus.UNDER_REVIEW,
                )),
            )
            .values(
                status=DischargeReportStatus.APPROVED,
                approved_by=doctor.id,
                approved_at=now,
            )
        ).rowcount
        if transition_count != 1:
            self.db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Discharge report is no longer ready for approval")
        # 1. Parallel Administrative Branch: Create Pending Billing Clearance & Deterministic Invoice
        from app.models.billing_clearance import BillingClearance, BillingStatus
        existing_billing = (
            self.db.query(BillingClearance)
            .filter(BillingClearance.admission_id == report.admission_id)
            .first()
        )
        if not existing_billing:
            billing = BillingClearance(
                patient_id=report.patient_id,
                admission_id=report.admission_id,
                discharge_report_id=report.id,
                status=BillingStatus.PENDING,
                total_amount=Decimal("0.00"),
                amount_paid=Decimal("0.00"),
                outstanding_amount=Decimal("0.00"),
                deferred=False,
                notes="Awaiting finance department billing verification.",
            )
            self.db.add(billing)
            self.db.flush()

        from app.services.billing_service import BillingService
        billing_svc = BillingService(self.db)
        billing_svc.generate_or_get_invoice(report.admission_id, auto_commit=False)

        # 2. Parallel Bed Release Branch: Transition Bed from OCCUPIED to VACATING
        if admission.bed_id:
            from app.models.bed import Bed, BedStatus
            bed = self.db.query(Bed).filter(Bed.id == admission.bed_id).first()
            if bed and bed.status == BedStatus.OCCUPIED:
                bed.status = BedStatus.VACATING
                self.db.add(WorkflowEvent(
                    event_type="bed_release_started",
                    entity_type="bed",
                    entity_id=bed.id,
                    status="pending",
                    delivery_status="pending",
                    trusted_provenance=True,
                    payload={
                        "bed_id": bed.id,
                        "patient_id": report.patient_id,
                        "admission_id": report.admission_id,
                        "previous_status": "occupied",
                        "new_status": "vacating",
                    },
                ))

        # 3. In-App Notification for Medical Superintendent
        from app.models.notification import Notification, NotificationChannel, NotificationType, NotificationStatus
        patient = admission.patient
        patient_name = f"{patient.first_name} {patient.last_name}" if patient else f"Patient #{report.patient_id}"
        patient_code = patient.patient_code if patient else "N/A"
        ward_bed = f"{admission.bed.ward} / {admission.bed.bed_number}" if admission.bed else "Unassigned"

        ms_notif = Notification(
            recipient_type="medical_superintendent",
            recipient_reference="superintendent@demo.local",
            channel=NotificationChannel.IN_APP,
            notification_type=NotificationType.DISCHARGE_PACKAGE_READY,
            status=NotificationStatus.DELIVERED,
            subject=f"Discharge Approved: {patient_name} ({patient_code})",
            message=f"Dr. {doctor.name} approved clinical discharge for {patient_name} in Bed {ward_bed}. Awaiting financial clearance for departure.",
            related_entity_type="admission",
            related_entity_id=admission.id,
            created_at=now,
            sent_at=now,
        )
        self.db.add(ms_notif)

        # 3. Emit report_approved workflow event
        event = WorkflowEvent(
            event_type="report_approved",
            entity_type="discharge_report",
            entity_id=report.id,
            status="pending",
            delivery_status="pending",
            orchestration_status="pending",
            attempt_count=0,
            trusted_provenance=True,
            payload={
                "report_id": report.id,
                "patient_id": report.patient_id,
                "admission_id": report.admission_id,
                "bed_id": admission.bed_id,
                "approved_by": doctor.id,
                "approved_at": now.isoformat(),
            },
        )
        self.db.add(event)

        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        self.db.refresh(report)

        return report
