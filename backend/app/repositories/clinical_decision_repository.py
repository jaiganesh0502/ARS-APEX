from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.models.clinical_decision import ClinicalDecision, ClinicalDecisionStatus
from app.repositories.base import BaseRepository


class ClinicalDecisionRepository(BaseRepository[ClinicalDecision]):
    def __init__(self, db: Session):
        super().__init__(ClinicalDecision, db)

    def get_with_context(self, decision_id: int) -> Optional[ClinicalDecision]:
        return self.db.query(ClinicalDecision).options(
            joinedload(ClinicalDecision.patient),
            joinedload(ClinicalDecision.admission),
            joinedload(ClinicalDecision.deciding_doctor),
        ).filter(ClinicalDecision.id == decision_id).first()

    def get_active_for_admission(self, admission_id: int) -> Optional[ClinicalDecision]:
        return self.db.query(ClinicalDecision).options(
            joinedload(ClinicalDecision.patient),
            joinedload(ClinicalDecision.admission),
            joinedload(ClinicalDecision.deciding_doctor),
        ).filter(
            ClinicalDecision.admission_id == admission_id,
            ClinicalDecision.status != ClinicalDecisionStatus.CANCELLED,
        ).order_by(ClinicalDecision.created_at.desc(), ClinicalDecision.id.desc()).first()
