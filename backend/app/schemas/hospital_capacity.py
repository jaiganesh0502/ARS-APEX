from datetime import datetime
from pydantic import BaseModel, ConfigDict


class HospitalCapacityBase(BaseModel):
    hospital_id: int
    specialty: str
    available_beds: int
    total_beds: int


class HospitalCapacityCreate(HospitalCapacityBase):
    pass


class HospitalCapacityUpdate(BaseModel):
    available_beds: int
    total_beds: int


class HospitalCapacityRead(HospitalCapacityBase):
    id: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
