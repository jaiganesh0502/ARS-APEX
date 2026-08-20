from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.models.transfer import TransferStatus


class HospitalMatchRead(BaseModel):
    hospital_id: int
    hospital_name: str
    required_specialty: str
    available_beds: int
    total_beds: int
    distance_km: float
    capacity_score: float
    distance_score: float
    match_score: int
    match_reasons: List[str]
    emergency: bool
    contact_number: str
    is_recommended: bool = False

    model_config = ConfigDict(from_attributes=True)


class HospitalSelectPayload(BaseModel):
    hospital_id: int


class TransferBase(BaseModel):
    patient_id: int
    admission_id: int
    clinical_decision_id: Optional[int] = None
    sending_hospital_id: int
    receiving_hospital_id: Optional[int] = None
    required_specialty: str
    emergency: bool = False
    status: TransferStatus = TransferStatus.MATCHING


class TransferCreate(BaseModel):
    patient_id: int
    admission_id: int
    sending_hospital_id: int
    required_specialty: str
    emergency: bool = False
    clinical_decision_id: Optional[int] = None


class TransferUpdateStatus(BaseModel):
    status: TransferStatus
    receiving_hospital_id: Optional[int] = None


class TransferRead(TransferBase):
    id: int
    requested_by: Optional[int] = None
    requested_at: datetime
    selected_hospital_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransferSummary(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    patient_code: str
    admission_id: int
    primary_diagnosis: str
    required_specialty: str
    emergency: bool
    status: TransferStatus
    sending_hospital_id: int
    sending_hospital_name: str
    receiving_hospital_id: Optional[int] = None
    receiving_hospital_name: Optional[str] = None
    requested_at: datetime
    selected_hospital_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TransferDetailRead(TransferRead):
    patient_name: str
    patient_code: str
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    primary_diagnosis: str
    ward: Optional[str] = None
    bed_number: Optional[str] = None
    clinical_reason: Optional[str] = None
    clinical_notes: Optional[str] = None
    sending_hospital_name: str
    sending_hospital_contact: Optional[str] = None
    receiving_hospital_name: Optional[str] = None
    receiving_hospital_contact: Optional[str] = None
    receiving_hospital_available_beds: Optional[int] = None
    receiving_hospital_distance_km: Optional[float] = None
    requested_by_name: Optional[str] = None
    packet_id: Optional[int] = None
    packet_status: Optional[str] = None
    rejection_reason: Optional[str] = None
    acceptance_notes: Optional[str] = None
    latest_decision: Optional[str] = None
    ambulance_dispatch_id: Optional[int] = None
    ambulance_status: Optional[str] = None
    ambulance_reference: Optional[str] = None
    ambulance_vehicle: Optional[str] = None
    ambulance_eta_minutes: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
