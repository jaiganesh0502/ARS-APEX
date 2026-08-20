from datetime import datetime, timezone
import enum
from typing import Optional
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Enum, Index, String
from sqlalchemy.orm import relationship

from app.db.session import Base


class DischargeReportStatus(str, enum.Enum):
    DRAFT = "draft"
    GENERATED = "generated"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"


class DischargeReport(Base):
    __tablename__ = "discharge_reports"
    __table_args__ = (
        Index("uq_discharge_reports_admission", "admission_id", unique=True),
    )

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    admission_id = Column(Integer, ForeignKey("admissions.id", ondelete="CASCADE"), nullable=False, index=True)
    generated_content = Column(Text, nullable=False)
    edited_content = Column(Text, nullable=True)
    generation_provider = Column(String(40), nullable=False, default="replicate")
    generation_model = Column(String(160), nullable=False)
    status = Column(
        Enum(DischargeReportStatus, name="discharge_report_status_enum", native_enum=False),
        default=DischargeReportStatus.DRAFT,
        nullable=False,
        index=True
    )
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    patient = relationship("Patient", back_populates="discharge_reports")
    admission = relationship("Admission", back_populates="discharge_reports")
    approving_doctor = relationship("User", back_populates="approved_discharge_reports")

    @property
    def effective_content(self) -> str:
        return self.edited_content if self.edited_content is not None else self.generated_content

    @property
    def approving_doctor_name(self) -> Optional[str]:
        return self.approving_doctor.name if self.approving_doctor else None
