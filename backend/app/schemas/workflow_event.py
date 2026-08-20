from datetime import datetime
from typing import Dict, Any
from pydantic import BaseModel, ConfigDict


class WorkflowEventBase(BaseModel):
    event_type: str
    entity_type: str
    entity_id: int
    payload: Dict[str, Any]
    status: str = "pending"


class WorkflowEventCreate(WorkflowEventBase):
    pass


class WorkflowEventRead(BaseModel):
    id: int
    event_type: str
    entity_type: str
    entity_id: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
