from datetime import datetime, date, timezone
from sqlalchemy import Column, Integer, String, Date, DateTime
from sqlalchemy.orm import relationship

from app.db.session import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    patient_code = Column(String(50), unique=True, index=True, nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String(20), nullable=False)
    blood_group = Column(String(10), nullable=True)
    phone = Column(String(30), nullable=True)
    emergency_contact = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    admissions = relationship("Admission", back_populates="patient", cascade="all, delete-orphan")
    medical_records = relationship("MedicalRecord", back_populates="patient")
    medications = relationship("Medication", back_populates="patient")
    vitals = relationship("Vital", back_populates="patient")
    discharge_reports = relationship("DischargeReport", back_populates="patient", cascade="all, delete-orphan")
    transfers = relationship("Transfer", back_populates="patient", cascade="all, delete-orphan")
    clinical_decisions = relationship("ClinicalDecision", back_populates="patient")
    portal_user = relationship("User", back_populates="patient", uselist=False)
