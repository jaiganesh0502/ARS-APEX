from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

from app.models.admission import AdmissionStatus
from app.models.bed import BedStatus


class PatientBase(BaseModel):
    patient_code: str
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str
    blood_group: Optional[str] = None
    phone: Optional[str] = None
    emergency_contact: Optional[str] = None


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    phone: Optional[str] = None
    emergency_contact: Optional[str] = None


class PatientRead(PatientBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PatientSummary(BaseModel):
    id: int
    patient_code: str
    first_name: str
    last_name: str
    age: int
    gender: str
    primary_diagnosis: Optional[str] = None
    admission_status: Optional[AdmissionStatus] = None
    ward: Optional[str] = None
    bed_number: Optional[str] = None


class PatientListResponse(BaseModel):
    items: List[PatientSummary]
    page: int
    page_size: int
    total: int


class PatientDemographics(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    age: int
    gender: str
    blood_group: Optional[str] = None
    phone: Optional[str] = None
    emergency_contact: Optional[str] = None


class PatientAdmissionDetail(BaseModel):
    id: int
    admission_date: datetime
    primary_diagnosis: str
    status: AdmissionStatus
    attending_doctor_id: int
    attending_doctor: str


class PatientBedDetail(BaseModel):
    ward: str
    bed_number: str
    status: BedStatus


class PatientMedicalRecordDetail(BaseModel):
    id: int
    diagnosis: str
    treatment_course: str
    notes: Optional[str] = None
    created_at: datetime


class PatientMedicationDetail(BaseModel):
    id: int
    medication_name: str
    dosage: str
    frequency: str
    route: str
    start_date: date
    end_date: Optional[date] = None


class PatientVitalDetail(BaseModel):
    id: int
    temperature: float
    heart_rate: int
    blood_pressure_systolic: int
    blood_pressure_diastolic: int
    oxygen_saturation: float
    recorded_at: datetime


class PatientDetail(BaseModel):
    id: int
    patient_code: str
    demographics: PatientDemographics
    admission: Optional[PatientAdmissionDetail] = None
    bed: Optional[PatientBedDetail] = None
    medical_record: Optional[PatientMedicalRecordDetail] = None
    medications: List[PatientMedicationDetail] = Field(default_factory=list)
    vitals: List[PatientVitalDetail] = Field(default_factory=list)
