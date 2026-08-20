from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.admission import Admission, AdmissionStatus
from app.models.clinical_decision import ClinicalDecision, ClinicalDecisionStatus, ClinicalDecisionType
from app.models.user import User
from app.models.workflow_event import WorkflowEvent
from app.repositories.clinical_decision_repository import ClinicalDecisionRepository
from app.schemas.clinical_decision import ClinicalDecisionPayload


class ClinicalDecisionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ClinicalDecisionRepository(db)

    def _admission(self, admission_id: int) -> Admission:
        admission = self.db.query(Admission).filter(Admission.id == admission_id).first()
        if not admission:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")
        return admission

    def create_draft(self, admission_id: int, payload: ClinicalDecisionPayload, doctor: User) -> ClinicalDecision:
        admission = self._admission(admission_id)
        if admission.status != AdmissionStatus.ADMITTED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Admission is not eligible for a new clinical decision")
        if self.repo.get_active_for_admission(admission_id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An active clinical decision already exists")
        decision = ClinicalDecision(
            patient_id=admission.patient_id, admission_id=admission.id, decided_by=doctor.id,
            status=ClinicalDecisionStatus.DRAFT, **payload.model_dump(),
        )
        self.db.add(decision)
        self.db.commit()
        return self.repo.get_with_context(decision.id)

    def get_current(self, admission_id: int) -> ClinicalDecision:
        self._admission(admission_id)
        decision = self.repo.get_active_for_admission(admission_id)
        if not decision:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinical decision not found")
        return decision

    def update_draft(self, decision_id: int, payload: ClinicalDecisionPayload) -> ClinicalDecision:
        decision = self.repo.get_with_context(decision_id)
        if not decision:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinical decision not found")
        if decision.status != ClinicalDecisionStatus.DRAFT:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft decisions can be edited")
        if decision.admission.status != AdmissionStatus.ADMITTED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Admission state no longer permits editing")
        for field, value in payload.model_dump().items():
            setattr(decision, field, value)
        self.db.commit()
        return self.repo.get_with_context(decision.id)

    def confirm(self, decision_id: int) -> ClinicalDecision:
        decision = self.repo.get_with_context(decision_id)
        if not decision:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinical decision not found")
        if decision.status != ClinicalDecisionStatus.DRAFT:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Clinical decision is not a draft")
        if decision.admission.status != AdmissionStatus.ADMITTED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Admission state no longer permits confirmation")

        decision.status = ClinicalDecisionStatus.CONFIRMED
        decision.decided_at = datetime.now(timezone.utc)
        is_discharge = decision.decision_type == ClinicalDecisionType.DISCHARGE
        decision.admission.status = AdmissionStatus.DISCHARGING if is_discharge else AdmissionStatus.TRANSFER_PENDING
        self.db.add(WorkflowEvent(
            event_type="clinical_discharge_decision_confirmed" if is_discharge else "clinical_transfer_decision_confirmed",
            entity_type="clinical_decision", entity_id=decision.id, status="pending",
            trusted_provenance=True,
            payload={
                "patient_id": decision.patient_id, "admission_id": decision.admission_id,
                "decision_id": decision.id, "decision_type": decision.decision_type.value,
                "transfer_urgency": decision.transfer_urgency.value if decision.transfer_urgency else None,
                "required_specialty": decision.required_specialty,
            },
        ))
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return self.repo.get_with_context(decision.id)
