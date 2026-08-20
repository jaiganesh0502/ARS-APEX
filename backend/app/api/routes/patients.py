import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import get_db, require_staff
from app.models.patient import Patient
from app.models.admission import AdmissionStatus
from app.models.user import User
from app.schemas.patient import PatientRead, PatientCreate, PatientListResponse, PatientDetail
from app.repositories.patient_repository import PatientRepository
from app.services.patient_service import PatientService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("", response_model=PatientListResponse)
def list_patients(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[AdmissionStatus] = None,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_staff),
):
    try:
        return PatientService(db).list_patients(page, page_size, search, status)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Unable to list patients")
        raise HTTPException(status_code=500, detail="Unable to load patients")


@router.get("/{patient_id}", response_model=PatientDetail)
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_staff),
):
    try:
        return PatientService(db).get_patient(patient_id)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Unable to load patient %s", patient_id)
        raise HTTPException(status_code=500, detail="Unable to load patient")


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def create_patient(
    patient_in: PatientCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_staff),
):
    repo = PatientRepository(db)
    existing = repo.get_by_patient_code(patient_in.patient_code)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Patient code already exists")
    
    patient = Patient(**patient_in.model_dump())
    return repo.create(patient)
