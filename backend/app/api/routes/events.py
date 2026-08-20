from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_role
from app.api.dependencies.database import get_db
from app.models.user import User, UserRole
from app.models.workflow_event import WorkflowEvent
from app.schemas.workflow_event import WorkflowEventRead

router = APIRouter(prefix="/events", tags=["Workflow Events"])


@router.get("", response_model=List[WorkflowEventRead])
def list_events(
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role([UserRole.DOCTOR, UserRole.WARD_ADMIN])),
):
    query = db.query(WorkflowEvent)
    if event_type:
        query = query.filter(WorkflowEvent.event_type == event_type)
    if status:
        query = query.filter(WorkflowEvent.status == status)
    return query.order_by(WorkflowEvent.created_at.desc()).offset(skip).limit(limit).all()
