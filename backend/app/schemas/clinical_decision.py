from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.clinical_decision import ClinicalDecisionStatus, ClinicalDecisionType, TransferUrgency


class ClinicalDecisionPayload(BaseModel):
    decision_type: ClinicalDecisionType
    transfer_urgency: Optional[TransferUrgency] = None
    reason: str = Field(min_length=1)
    required_specialty: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = None

    @field_validator("reason", "required_specialty", "notes", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_decision_fields(self):
        if not self.reason:
            raise ValueError("Reason is required")
        if self.decision_type == ClinicalDecisionType.DISCHARGE:
            if self.transfer_urgency is not None or self.required_specialty is not None:
                raise ValueError("Discharge decisions cannot include transfer fields")
        elif self.transfer_urgency is None or not self.required_specialty:
            raise ValueError("Transfer urgency and required specialty are required")
        return self


class ClinicalDecisionCreate(ClinicalDecisionPayload):
    pass


class ClinicalDecisionUpdate(ClinicalDecisionPayload):
    pass


class ClinicalDecisionRead(ClinicalDecisionPayload):
    id: int
    patient_id: int
    admission_id: int
    decided_by: int
    decided_by_name: str
    decided_at: Optional[datetime] = None
    status: ClinicalDecisionStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
