from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.transfer_decision import TransferDecisionType


class TransferAcceptPayload(BaseModel):
    notes: Optional[str] = None


class TransferRejectPayload(BaseModel):
    reason: str = Field(..., min_length=3, description="Mandatory justification for rejecting transfer request")


class TransferDecisionRead(BaseModel):
    id: int
    transfer_id: int
    hospital_id: int
    hospital_name: Optional[str] = None
    decision: TransferDecisionType
    reason: Optional[str] = None
    decided_by: Optional[int] = None
    decided_by_name: Optional[str] = None
    decided_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
