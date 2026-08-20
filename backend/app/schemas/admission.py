from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.models.admission import AdmissionStatus
from app.schemas.medical_record import MedicalRecordRead
from app.schemas.medication import MedicationRead
from app.schemas.vital import VitalRead


class AdmissionBase(BaseModel):
    patient_id: int
    admission_date: datetime
    primary_diagnosis: str
    attending_doctor_id: int
    status: AdmissionStatus = AdmissionStatus.ADMITTED
    bed_id: Optional[int] = None


class AdmissionCreate(AdmissionBase):
    pass


class AdmissionUpdateStatus(BaseModel):
    status: AdmissionStatus
    bed_id: Optional[int] = None


class AdmissionRead(AdmissionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdmissionDetail(AdmissionRead):
    medical_records: List[MedicalRecordRead] = []
    medications: List[MedicationRead] = []
    vitals: List[VitalRead] = []
