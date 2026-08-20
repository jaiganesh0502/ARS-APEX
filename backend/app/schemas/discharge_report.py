from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, field_validator
from app.models.discharge_report import DischargeReportStatus


class DischargeReportBase(BaseModel):
    patient_id: int
    admission_id: int
    generated_content: str
    edited_content: Optional[str] = None
    generation_provider: str
    generation_model: str
    status: DischargeReportStatus = DischargeReportStatus.DRAFT


class DischargeReportCreate(BaseModel):
    patient_id: int
    admission_id: int
    generated_content: str

    model_config = ConfigDict(extra="forbid")


class DischargeReportEdit(BaseModel):
    edited_content: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("edited_content")
    @classmethod
    def edited_content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("edited_content must not be blank")
        return value


class DischargeReportApprove(BaseModel):
    acknowledged: Literal[True]
    clinical_notes: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class DischargeReportRead(DischargeReportBase):
    id: int
    effective_content: str
    approving_doctor_name: Optional[str] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
