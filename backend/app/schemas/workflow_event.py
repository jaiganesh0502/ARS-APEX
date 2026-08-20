from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, ConfigDict


class WorkflowEventBase(BaseModel):
    event_type: str
    entity_type: str
    entity_id: int
    payload: Dict[str, Any]
    status: str = "pending"


class WorkflowEventCreate(WorkflowEventBase):
    trusted_provenance: bool = True


class WorkflowEventRead(BaseModel):
    id: int
    event_type: str
    entity_type: str
    entity_id: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowTelemetryRead(BaseModel):
    id: int
    event_type: str
    entity_type: str
    entity_id: int
    status: str
    delivery_status: str
    orchestration_status: str
    attempt_count: int
    last_attempt_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    last_error: Optional[str] = None
    trusted_provenance: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowEventDetailRead(WorkflowTelemetryRead):
    payload: Dict[str, Any]


class WorkflowEventRetryResponse(BaseModel):
    event_id: int
    delivery_status: str
    attempt_count: int
    message: str


class WorkflowDashboardCounts(BaseModel):
    total_events: int
    delivery_pending: int
    delivery_delivered: int
    delivery_failed: int
    orchestration_pending: int
    orchestration_processing: int
    orchestration_completed: int
    orchestration_failed: int
