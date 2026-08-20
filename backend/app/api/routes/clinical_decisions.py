import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_doctor, require_staff
from app.models.user import User
from app.schemas.clinical_decision import ClinicalDecisionCreate, ClinicalDecisionRead, ClinicalDecisionUpdate
from app.services.clinical_decision_service import ClinicalDecisionService

router = APIRouter(tags=["Clinical Decisions"])
logger = logging.getLogger(__name__)


@router.post("/admissions/{admission_id}/clinical-decision", response_model=ClinicalDecisionRead, status_code=status.HTTP_201_CREATED)
def create_clinical_decision(
    admission_id: int,
    payload: ClinicalDecisionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    try:
        return ClinicalDecisionService(db).create_draft(admission_id, payload, current_user)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Unable to create clinical decision")
        raise HTTPException(status_code=500, detail="Unable to save clinical decision")


@router.get("/admissions/{admission_id}/clinical-decision", response_model=ClinicalDecisionRead)
def get_clinical_decision(
    admission_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_staff),
):
    return ClinicalDecisionService(db).get_current(admission_id)


@router.put("/clinical-decisions/{decision_id}", response_model=ClinicalDecisionRead)
def update_clinical_decision(
    decision_id: int,
    payload: ClinicalDecisionUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_doctor),
):
    return ClinicalDecisionService(db).update_draft(decision_id, payload)


@router.post("/clinical-decisions/{decision_id}/confirm", response_model=ClinicalDecisionRead)
def confirm_clinical_decision(
    decision_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_doctor),
):
    try:
        return ClinicalDecisionService(db).confirm(decision_id)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Unable to confirm clinical decision")
        raise HTTPException(status_code=500, detail="Unable to confirm clinical decision")
