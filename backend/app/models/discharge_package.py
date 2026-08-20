import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class DischargePackageStatus(str, enum.Enum):
    DRAFT = "draft"
    AUTHORIZED = "authorized"
    PDF_READY = "pdf_ready"
    DELIVERED = "delivered"
    FAILED = "failed"


class DischargePackage(Base):
    __tablename__ = "discharge_packages"
    __table_args__ = (
        Index("uq_discharge_packages_admission", "admission_id", unique=True),
    )

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    admission_id = Column(Integer, ForeignKey("admissions.id", ondelete="CASCADE"), nullable=False, index=True)
    discharge_report_id = Column(Integer, ForeignKey("discharge_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    billing_clearance_id = Column(Integer, ForeignKey("billing_clearances.id", ondelete="SET NULL"), nullable=True, index=True)

    status = Column(
        Enum(
            DischargePackageStatus,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
            name="discharge_package_status_enum",
        ),
        default=DischargePackageStatus.AUTHORIZED,
        nullable=False,
        index=True,
    )

    clinical_snapshot = Column(JSON, nullable=False, default=dict)
    patient_summary = Column(JSON, nullable=False, default=dict)

    pdf_path = Column(String(500), nullable=True)
    pdf_generated_at = Column(DateTime(timezone=True), nullable=True)

    authorized_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    authorized_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    patient = relationship("Patient")
    admission = relationship("Admission")
    discharge_report = relationship("DischargeReport")
    billing_clearance = relationship("BillingClearance")
    authorizing_user = relationship("User", foreign_keys=[authorized_by])
