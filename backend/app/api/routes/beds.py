import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user_stub
from app.api.dependencies.database import get_db
from app.models.bed import BedStatus
from app.models.user import User, UserRole
from app.schemas.bed import BedDetail, BedSummary
from app.services.bed_query_service import BedQueryService
from app.services.bed_release_service import BedReleaseService

router = APIRouter(prefix="/beds", tags=["Beds"])
logger = logging.getLogger(__name__)


@router.get("", response_model=List[BedSummary])
def list_beds(
    ward: Optional[str] = None,
    status: Optional[BedStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db)
):
    return BedQueryService(db).list_beds(status=status, ward=ward, skip=skip, limit=limit)


@router.get("/{bed_id}", response_model=BedDetail)
def get_bed(bed_id: int, db: Session = Depends(get_db)):
    bed = BedQueryService(db).get_bed(bed_id)
    if bed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bed not found")
    return bed


@router.post("/{bed_id}/start-release", response_model=BedDetail)
def start_bed_release(
    bed_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_stub),
):
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    if current_user.role not in {UserRole.DOCTOR, UserRole.WARD_ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors and ward administrators can start bed release",
        )

    try:
        bed = BedReleaseService(db).start_release_detail(bed_id, current_user)
    except HTTPException:
        raise
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Unable to start release for bed %s", bed_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to start bed release",
        ) from error

    return bed


@router.post("/{bed_id}/patient-departed", response_model=BedDetail)
def confirm_patient_departure(
    bed_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_stub),
):
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    if current_user.role not in {UserRole.DOCTOR, UserRole.WARD_ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors and ward administrators can confirm patient departure",
        )

    try:
        return BedReleaseService(db).patient_departed_detail(bed_id, current_user)
    except HTTPException:
        raise
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Unable to confirm departure for bed %s", bed_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to confirm patient departure",
        ) from error


@router.post("/{bed_id}/cleaning-complete", response_model=BedDetail)
def complete_bed_cleaning(
    bed_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_stub),
):
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    if current_user.role not in {UserRole.DOCTOR, UserRole.WARD_ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors and ward administrators can complete bed cleaning",
        )

    try:
        return BedReleaseService(db).cleaning_complete_detail(bed_id, current_user)
    except HTTPException:
        raise
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Unable to complete cleaning for bed %s", bed_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to complete bed cleaning",
        ) from error
