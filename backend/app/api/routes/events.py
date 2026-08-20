from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_roles, require_staff, require_superintendent
from app.models.user import User, UserRole
from app.models.workflow_event import WorkflowEvent
from app.schemas.workflow_event import (
    WorkflowEventRead,
    WorkflowTelemetryRead,
    WorkflowEventDetailRead,
    WorkflowDashboardCounts,
    WorkflowEventRetryResponse,
)
from app.services.workflow_event_service import WorkflowEventService

router = APIRouter(tags=["Workflow Events"])


@router.get("/events", response_model=List[WorkflowEventRead])
def list_events(
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _current_user: User = Depends(
        require_roles(
            UserRole.DOCTOR,
            UserRole.MEDICAL_SUPERINTENDENT,
            UserRole.WARD_ADMIN,
        )
    ),
):
    """
    Standard event audit log with minimal metadata for authorized operational roles.
    """
    query = db.query(WorkflowEvent)
    if event_type:
        query = query.filter(WorkflowEvent.event_type == event_type)
    if status:
        query = query.filter(WorkflowEvent.status == status)
    return query.order_by(WorkflowEvent.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/workflow-events", response_model=List[WorkflowTelemetryRead])
def list_workflow_telemetry_events(
    status: Optional[str] = None,
    delivery_status: Optional[str] = None,
    orchestration_status: Optional[str] = None,
    event_type: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_staff),
):
    """
    Detailed telemetry log for operations dashboard with delivery and orchestration tracking.
    """
    evt_svc = WorkflowEventService(db)
    return evt_svc.list_events(
        status=status,
        delivery_status=delivery_status,
        orchestration_status=orchestration_status,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        skip=skip,
        limit=limit,
    )


@router.get("/workflow-events/counts", response_model=WorkflowDashboardCounts)
def get_workflow_dashboard_counts(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_staff),
):
    """
    Aggregate counts for the Operations & Orchestration Dashboard.
    """
    evt_svc = WorkflowEventService(db)
    return evt_svc.get_dashboard_counts()


@router.get("/workflow-events/{event_id}", response_model=WorkflowEventDetailRead)
def get_workflow_event_detail(
    event_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_superintendent),
):
    """
    Retrieve full workflow event detail with audit payload. Never exposes secrets.
    Restricted to Medical Superintendent / Operational Admins.
    """
    event = db.query(WorkflowEvent).filter(WorkflowEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow event not found")
    return event


@router.post("/workflow-events/{event_id}/retry", response_model=WorkflowEventRetryResponse)
def retry_workflow_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superintendent),
):
    """
    Retry webhook delivery for a pending or failed workflow event.
    Restricted to Medical Superintendent / Operational Admins.
    """
    evt_svc = WorkflowEventService(db)
    event = evt_svc.retry_event(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow event not found")

    return WorkflowEventRetryResponse(
        event_id=event.id,
        delivery_status=event.delivery_status,
        attempt_count=event.attempt_count,
        message=f"Event #{event.id} delivery re-attempted. Status: {event.delivery_status}",
    )
