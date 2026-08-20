from datetime import datetime, timezone
import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import relationship

from app.db.session import Base


class ClinicalDecisionType(str, enum.Enum):
    DISCHARGE = "discharge"
    TRANSFER = "transfer"


class TransferUrgency(str, enum.Enum):
    EMERGENCY = "emergency"
    NON_EMERGENCY = "non_emergency"


class ClinicalDecisionStatus(str, enum.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class ClinicalDecision(Base):
    __tablename__ = "clinical_decisions"
    __table_args__ = (
        Index(
            "uq_clinical_decisions_active_admission",
            "admission_id",
            unique=True,
            postgresql_where=text("status IN ('draft', 'confirmed')"),
            sqlite_where=text("status IN ('draft', 'confirmed')"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True)
    admission_id = Column(Integer, ForeignKey("admissions.id", ondelete="RESTRICT"), nullable=False, index=True)
    decision_type = Column(Enum(ClinicalDecisionType, name="clinical_decision_type_enum", native_enum=False), nullable=False)
    transfer_urgency = Column(Enum(TransferUrgency, name="transfer_urgency_enum", native_enum=False), nullable=True)
    reason = Column(Text, nullable=False)
    required_specialty = Column(String(120), nullable=True)
    notes = Column(Text, nullable=True)
    decided_by = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(
        Enum(ClinicalDecisionStatus, name="clinical_decision_status_enum", native_enum=False),
        default=ClinicalDecisionStatus.DRAFT,
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False,
    )

    patient = relationship("Patient", back_populates="clinical_decisions")
    admission = relationship("Admission", back_populates="clinical_decisions")
    deciding_doctor = relationship("User", back_populates="clinical_decisions")

    @property
    def decided_by_name(self) -> str:
        return self.deciding_doctor.name
