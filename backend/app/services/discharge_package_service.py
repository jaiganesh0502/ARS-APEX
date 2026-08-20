import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.admission import Admission
from app.models.billing_clearance import BillingClearance, BillingStatus
from app.models.discharge_package import DischargePackage, DischargePackageStatus
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.notification import Notification, NotificationChannel, NotificationStatus, NotificationType
from app.models.patient import Patient
from app.models.user import User
from app.models.workflow_event import WorkflowEvent
from app.services.patient_summary_service import PatientSummaryService
from app.services.pdf_generation_service import PDFGenerationService

logger = logging.getLogger(__name__)


class DischargePackageService:
    """
    Manages final discharge package authorization, clinical snapshot freezing,
    patient summary generation, vector PDF export, and in-app notifications.
    """

    def __init__(self, db: Session):
        self.db = db
        self.summary_svc = PatientSummaryService()
        self.pdf_svc = PDFGenerationService()

    def get_by_admission_id(self, admission_id: int) -> Optional[DischargePackage]:
        return (
            self.db.query(DischargePackage)
            .filter(DischargePackage.admission_id == admission_id)
            .first()
        )

    def get_by_id(self, package_id: int) -> Optional[DischargePackage]:
        return self.db.query(DischargePackage).filter(DischargePackage.id == package_id).first()

    def finalize_discharge_package(
        self,
        admission_id: int,
        authorizing_user: Optional[User] = None,
        notes: Optional[str] = None,
    ) -> DischargePackage:
        """
        Authorize and generate final discharge package.
        Strictly gated on:
          1. DischargeReport.status == APPROVED
          2. BillingClearance.status == CLEARED (or WAIVED/DEFERRED)
        Bed status (vacating/cleaning/available) does NOT block authorization.
        Idempotent: Duplicate calls return the existing package.
        """
        # Idempotency check
        existing = self.get_by_admission_id(admission_id)
        if existing:
            # If package exists but PDF generation was not completed, attempt PDF generation
            if not existing.pdf_path:
                self._generate_pdf_for_package(existing)
            return existing

        admission = self.db.get(Admission, admission_id)
        if not admission:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")

        # 1. Gate Check: Physician-Approved Report
        report = (
            self.db.query(DischargeReport)
            .filter(DischargeReport.admission_id == admission_id)
            .first()
        )
        if not report or report.status != DischargeReportStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Discharge package authorization requires an approved clinical discharge report.",
            )

        # 2. Gate Check: Cleared Billing Clearance
        billing = (
            self.db.query(BillingClearance)
            .filter(BillingClearance.admission_id == admission_id)
            .first()
        )
        if not billing or billing.status in (
            BillingStatus.PENDING,
            BillingStatus.PROCESSING,
            BillingStatus.FAILED,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Discharge package authorization requires cleared billing clearance.",
            )

        patient = admission.patient or self.db.get(Patient, admission.patient_id)
        patient_code = patient.patient_code if patient else f"PT-{admission.patient_id}"
        patient_name = f"{patient.first_name} {patient.last_name}" if patient else "Patient"

        # 3. Freeze Clinical Snapshot
        clinical_snapshot = {
            "admission_id": admission.id,
            "patient_id": admission.patient_id,
            "patient_code": patient_code,
            "patient_name": patient_name,
            "date_of_birth": patient.date_of_birth.isoformat() if patient and patient.date_of_birth else None,
            "gender": patient.gender if patient else None,
            "primary_diagnosis": admission.primary_diagnosis,
            "admission_date": admission.admission_date.isoformat() if admission.admission_date else None,
            "attending_doctor_name": report.approving_doctor_name or (admission.attending_doctor.name if admission.attending_doctor else "Attending Physician"),
            "report_id": report.id,
            "effective_content": report.effective_content,
            "generation_model": report.generation_model,
            "approved_at": report.approved_at.isoformat() if report.approved_at else None,
            "clearance_reference": billing.clearance_reference if billing else "VERIFIED",
            "total_amount": float(billing.total_amount) if billing and billing.total_amount else None,
            "notes": notes,
        }

        # 4. Generate Patient Summary
        patient_summary = self.summary_svc.generate_summary(report.effective_content, patient_name)

        # 5. Create Package Record
        package = DischargePackage(
            patient_id=admission.patient_id,
            admission_id=admission.id,
            discharge_report_id=report.id,
            billing_clearance_id=billing.id if billing else None,
            status=DischargePackageStatus.AUTHORIZED,
            clinical_snapshot=clinical_snapshot,
            patient_summary=patient_summary,
            authorized_by=authorizing_user.id if authorizing_user else None,
            authorized_at=datetime.now(timezone.utc),
        )
        self.db.add(package)
        admission.discharge_ready = True
        self.db.flush()

        # 6. Generate PDF Document
        self._generate_pdf_for_package(package, patient_code, patient_name, report, billing)

        # 7. Create In-App Notification
        notification = Notification(
            recipient_type="patient",
            recipient_reference=patient_code,
            channel=NotificationChannel.IN_APP,
            notification_type=NotificationType.DISCHARGE_PACKAGE_READY,
            status=NotificationStatus.DELIVERED,
            subject="Your discharge documents are ready.",
            message="Your official discharge documentation and plain-language care instructions are now available for review and download.",
            related_entity_type="discharge_package",
            related_entity_id=package.id,
            created_at=datetime.now(timezone.utc),
            sent_at=datetime.now(timezone.utc),
        )
        self.db.add(notification)

        # 8. Emit Domain Event
        event = WorkflowEvent(
            event_type="discharge_package_ready",
            entity_type="discharge_package",
            entity_id=package.id,
            status="pending",
            delivery_status="pending",
            orchestration_status="pending",
            attempt_count=0,
            trusted_provenance=True,
            payload={
                "package_id": package.id,
                "admission_id": admission.id,
                "patient_id": admission.patient_id,
                "status": package.status.value,
                "pdf_ready": bool(package.pdf_path),
            },
        )
        self.db.add(event)

        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(package)
        return package

    def retry_pdf_generation(self, package_id: int) -> DischargePackage:
        """
        Idempotently regenerates or repairs a missing PDF for an authorized package.
        """
        package = self.get_by_id(package_id)
        if not package:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge package not found")

        self._generate_pdf_for_package(package)
        self.db.commit()
        self.db.refresh(package)
        return package

    def _generate_pdf_for_package(
        self,
        package: DischargePackage,
        patient_code: Optional[str] = None,
        patient_name: Optional[str] = None,
        report: Optional[DischargeReport] = None,
        billing: Optional[BillingClearance] = None,
    ) -> None:
        try:
            p_code = patient_code or package.clinical_snapshot.get("patient_code", f"PT-{package.patient_id}")
            p_name = patient_name or package.clinical_snapshot.get("patient_name", "Patient")
            b_ref = billing.clearance_reference if billing else package.clinical_snapshot.get("clearance_reference")
            doc_name = (
                report.approving_doctor_name
                if report
                else package.clinical_snapshot.get("attending_doctor_name")
            )
            app_at = report.approved_at if report else None

            pdf_path = self.pdf_svc.generate_discharge_pdf(
                package_id=package.id,
                patient_code=p_code,
                patient_name=p_name,
                clinical_snapshot=package.clinical_snapshot,
                patient_summary=package.patient_summary,
                billing_reference=b_ref,
                approving_doctor_name=doc_name,
                approved_at=app_at,
            )
            package.pdf_path = pdf_path
            package.pdf_generated_at = datetime.now(timezone.utc)
            package.status = DischargePackageStatus.PDF_READY
        except Exception as err:
            logger.error("PDF generation failed for package %s: %s", package.id, err)
            package.status = DischargePackageStatus.AUTHORIZED
