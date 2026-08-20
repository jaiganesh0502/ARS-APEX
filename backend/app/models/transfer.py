from datetime import datetime, timezone
import enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, text
from sqlalchemy.orm import relationship

from app.db.session import Base


class TransferStatus(str, enum.Enum):
    MATCHING = "matching"
    HOSPITAL_SELECTED = "hospital_selected"
    AWAITING_ACCEPTANCE = "awaiting_acceptance"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    AMBULANCE_REQUESTED = "ambulance_requested"
    IN_TRANSIT = "in_transit"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Transfer(Base):
    __tablename__ = "transfers"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    admission_id = Column(Integer, ForeignKey("admissions.id", ondelete="CASCADE"), nullable=False, index=True)
    clinical_decision_id = Column(Integer, ForeignKey("clinical_decisions.id", ondelete="RESTRICT"), nullable=True, index=True)
    sending_hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="RESTRICT"), nullable=False, index=True)
    receiving_hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True, index=True)
    required_specialty = Column(String(100), nullable=False)
    emergency = Column(Boolean, default=False, nullable=False)
    status = Column(
        Enum(TransferStatus, name="transfer_status_enum", native_enum=False),
        default=TransferStatus.MATCHING,
        nullable=False,
        index=True
    )
    requested_by = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    requested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    selected_hospital_at = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    patient = relationship("Patient", back_populates="transfers")
    admission = relationship("Admission", back_populates="transfers")
    clinical_decision = relationship("ClinicalDecision")
    sending_hospital = relationship("Hospital", foreign_keys=[sending_hospital_id], back_populates="transfers_sent")
    receiving_hospital = relationship("Hospital", foreign_keys=[receiving_hospital_id], back_populates="transfers_received")
    requester = relationship("User", foreign_keys=[requested_by])
    ambulance_dispatches = relationship("AmbulanceDispatch", back_populates="transfer", cascade="all, delete-orphan")
    packets = relationship("TransferPacket", back_populates="transfer", cascade="all, delete-orphan")
    decisions = relationship("TransferDecision", back_populates="transfer", cascade="all, delete-orphan")
