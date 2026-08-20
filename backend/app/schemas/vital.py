from datetime import datetime
from pydantic import BaseModel, ConfigDict


class VitalBase(BaseModel):
    patient_id: int
    admission_id: int
    temperature: float
    heart_rate: int
    blood_pressure_systolic: int
    blood_pressure_diastolic: int
    oxygen_saturation: float
    recorded_at: datetime


class VitalCreate(VitalBase):
    pass


class VitalRead(VitalBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
