import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_superintendent
from app.models.user import User
from app.schemas.ambulance_dispatch import (
    AmbulanceCancelPayload,
    AmbulanceDashboardCounts,
    AmbulanceDispatchDetailRead,
    AmbulanceDispatchRead,
    AmbulanceDispatchSummaryRead,
    AmbulanceStatusUpdatePayload,
)
from app.services.ambulance_dispatch_service import AmbulanceDispatchService

router = APIRouter(prefix="/ambulance-dispatches", tags=["Ambulance Dispatches"])
logger = logging.getLogger(__name__)


@router.get("", response_model=List[AmbulanceDispatchSummaryRead])
def list_ambulance_dispatches(
    status: Optional[str] = Query(None, description="Filter by status (e.g. en_route, in_transit)"),
    emergency: Optional[bool] = Query(None, description="Filter by emergency priority"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_superintendent),
):
    """
    List ambulance dispatches with optional status and urgency filters.
    Restricted to Medical Superintendent / Fleet Operations.
    """
    return AmbulanceDispatchService(db).list_dispatches(
        status_filter=status,
        emergency_filter=emergency,
        skip=skip,
        limit=limit,
    )


@router.get("/counts", response_model=AmbulanceDashboardCounts)
def get_ambulance_dashboard_counts(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_superintendent),
):
    """
    Aggregated operational counts for ambulance telemetry dashboard.
    Restricted to Medical Superintendent / Fleet Operations.
    """
    return AmbulanceDispatchService(db).get_dashboard_counts()


@router.get("/{dispatch_id}", response_model=AmbulanceDispatchDetailRead)
def get_ambulance_dispatch_detail(
    dispatch_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_superintendent),
):
    """
    Retrieve full tracking telemetry and patient context for an ambulance dispatch.
    Restricted to Medical Superintendent / Fleet Operations.
    """
    return AmbulanceDispatchService(db).get_dispatch_detail(dispatch_id)


@router.post("/{dispatch_id}/status", response_model=AmbulanceDispatchRead)
def update_ambulance_status(
    dispatch_id: int,
    payload: AmbulanceStatusUpdatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superintendent),
):
    """
    Advance ambulance dispatch status through the validated state machine.
    Restricted to Medical Superintendent / Fleet Operations.
    """
    return AmbulanceDispatchService(db).update_dispatch_status(
        dispatch_id=dispatch_id,
        target_status=payload.status,
        actor=current_user,
    )


@router.post("/{dispatch_id}/cancel", response_model=AmbulanceDispatchRead)
def cancel_ambulance_dispatch(
    dispatch_id: int,
    payload: AmbulanceCancelPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superintendent),
):
    """
    Cancel an ambulance dispatch before patient pickup.
    Restricted to Medical Superintendent / Fleet Operations.
    """
    return AmbulanceDispatchService(db).cancel_dispatch(
        dispatch_id=dispatch_id,
        reason=payload.reason,
        actor=current_user,
    )
