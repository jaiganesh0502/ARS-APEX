from typing import List, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_doctor, require_staff, require_superintendent
from app.models.admission import Admission, AdmissionStatus
from app.models.user import User
from app.schemas.admission import AdmissionRead, AdmissionCreate, AdmissionDetail
from app.schemas.transfer import TransferRead
from app.services.admission_assignment_service import AdmissionAssignmentService
from app.services.transfer_service import TransferService

router = APIRouter(prefix="/admissions", tags=["Admissions"])
logger = logging.getLogger(__name__)


@router.get("", response_model=List[AdmissionRead])
def list_admissions(
    status: Optional[AdmissionStatus] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_staff),
):
    query = db.query(Admission)
    if status:
        query = query.filter(Admission.status == status)
    return query.offset(skip).limit(limit).all()


@router.get("/{admission_id}", response_model=AdmissionDetail)
def get_admission(
    admission_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_staff),
):
    admission = db.query(Admission).filter(Admission.id == admission_id).first()
    if not admission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")
    return admission


@router.post("", response_model=AdmissionRead, status_code=status.HTTP_201_CREATED)
def create_admission(
    admission_in: AdmissionCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_staff),
):
    try:
        return AdmissionAssignmentService(db).create(admission_in)
    except HTTPException:
        raise
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Unable to create admission")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create admission",
        ) from error


@router.post("/{admission_id}/transfer", response_model=TransferRead, status_code=status.HTTP_201_CREATED)
def create_transfer_for_admission(
    admission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    """
    Create a new transfer case or return existing active transfer for an admission.
    Requires a confirmed clinical transfer decision. Restricted to Doctors.
    """
    try:
        return TransferService(db).create_or_get_transfer_for_admission(
            admission_id=admission_id,
            requesting_user=current_user,
        )
    except HTTPException:
        raise
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Unable to create transfer for admission %s", admission_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create transfer case",
        ) from error
