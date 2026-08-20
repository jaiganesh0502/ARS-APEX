from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.models.transfer_packet import TransferPacketStatus


class PatientSummaryPacket(BaseModel):
    patient_id: int
    patient_name: str
    patient_code: str
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    phone: Optional[str] = None
    emergency_contact: Optional[str] = None


class AdmissionSummaryPacket(BaseModel):
    admission_id: int
    admission_date: str
    ward: Optional[str] = None
    bed_number: Optional[str] = None
    status: str


class MedicationPacket(BaseModel):
    medication_name: str
    dosage: str
    frequency: str
    route: str
    start_date: str
    end_date: Optional[str] = None


class VitalPacket(BaseModel):
    temperature: float
    heart_rate: int
    blood_pressure: str
    oxygen_saturation: int
    recorded_at: str


class HospitalSummaryPacket(BaseModel):
    hospital_id: int
    hospital_name: str
    contact_number: Optional[str] = None


class DoctorSummaryPacket(BaseModel):
    doctor_id: Optional[int] = None
    name: str
    email: Optional[str] = None


class TransferPacketContent(BaseModel):
    transfer_id: int
    patient_summary: PatientSummaryPacket
    admission_summary: AdmissionSummaryPacket
    primary_diagnosis: str
    transfer_reason: str
    required_specialty: str
    urgency: str
    treatment_course: str
    current_medications: List[MedicationPacket] = []
    recent_vitals: List[VitalPacket] = []
    clinical_notes: Optional[str] = None
    approved_discharge_summary: Optional[str] = None
    sending_hospital: HospitalSummaryPacket
    sending_doctor: DoctorSummaryPacket
    receiving_hospital: HospitalSummaryPacket


class TransferPacketRead(BaseModel):
    id: int
    transfer_id: int
    patient_id: int
    admission_id: int
    packet_content: TransferPacketContent
    status: TransferPacketStatus
    prepared_at: datetime
    sent_at: Optional[datetime] = None
    viewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
