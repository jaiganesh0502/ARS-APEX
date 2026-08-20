from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, ConfigDict


class MedicationBase(BaseModel):
    patient_id: int
    admission_id: int
    medication_name: str
    dosage: str
    frequency: str
    route: str
    start_date: date
    end_date: Optional[date] = None


class MedicationCreate(MedicationBase):
    pass


class MedicationRead(MedicationBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
