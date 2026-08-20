from datetime import datetime, timezone
import enum
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class AdmissionStatus(str, enum.Enum):
    ADMITTED = "admitted"
    DISCHARGING = "discharging"
    TRANSFER_PENDING = "transfer_pending"
    TRANSFERRED = "transferred"
    DISCHARGED = "discharged"


class Admission(Base):
    __tablename__ = "admissions"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    admission_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    primary_diagnosis = Column(Text, nullable=False)
    attending_doctor_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    status = Column(
        Enum(AdmissionStatus, name="admission_status_enum", native_enum=False),
        default=AdmissionStatus.ADMITTED,
        nullable=False,
        index=True
    )
    bed_id = Column(Integer, ForeignKey("beds.id", ondelete="SET NULL"), nullable=True)
    discharge_ready = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    patient = relationship("Patient", back_populates="admissions")
    attending_doctor = relationship("User", back_populates="attended_admissions")
    bed = relationship("Bed", back_populates="admissions")
    medical_records = relationship("MedicalRecord", back_populates="admission")
    medications = relationship("Medication", back_populates="admission")
    vitals = relationship("Vital", back_populates="admission")
    discharge_reports = relationship("DischargeReport", back_populates="admission", cascade="all, delete-orphan")
    transfers = relationship("Transfer", back_populates="admission", cascade="all, delete-orphan")
    clinical_decisions = relationship("ClinicalDecision", back_populates="admission")
