from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.admission import AdmissionStatus
from app.models.bed import BedStatus


class BedBase(BaseModel):
    ward: str
    bed_number: str
    status: BedStatus = BedStatus.AVAILABLE
    current_patient_id: Optional[int] = None


class BedCreate(BedBase):
    pass


class BedRead(BedBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BedSummary(BaseModel):
    id: int
    ward: str
    bed_number: str
    status: BedStatus
    current_patient_id: Optional[int] = None
    patient_name: Optional[str] = None
    patient_code: Optional[str] = None
    admission_id: Optional[int] = None
    admission_status: Optional[AdmissionStatus] = None
    primary_diagnosis: Optional[str] = None
    release_eligible: bool
    updated_at: datetime


class BedTransitionEventRead(BaseModel):
    event_type: str
    previous_status: Optional[BedStatus] = None
    new_status: Optional[BedStatus] = None
    created_at: datetime


class BedDetail(BedSummary):
    transition_history: list[BedTransitionEventRead]
