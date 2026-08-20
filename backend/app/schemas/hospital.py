from datetime import datetime
from typing import List
from pydantic import BaseModel, ConfigDict


class HospitalBase(BaseModel):
    name: str
    latitude: float
    longitude: float
    specialties: List[str] = []
    contact_number: str


class HospitalCreate(HospitalBase):
    pass


class HospitalRead(HospitalBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
