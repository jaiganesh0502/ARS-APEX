import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class BillingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    CLEARED = "cleared"
    FAILED = "failed"
    WAIVED = "waived"
    DEFERRED = "deferred"


class BillingClearance(Base):
    __tablename__ = "billing_clearances"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    admission_id = Column(Integer, ForeignKey("admissions.id"), nullable=False, index=True)
    transfer_id = Column(Integer, ForeignKey("transfers.id"), nullable=True, index=True)
    discharge_report_id = Column(Integer, ForeignKey("discharge_reports.id"), nullable=True, index=True)

    status = Column(
        Enum(
            BillingStatus,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
        ),
        default=BillingStatus.PENDING,
        nullable=False,
        index=True,
    )

    total_amount = Column(Numeric(10, 2), nullable=True)
    amount_paid = Column(Numeric(10, 2), nullable=True)
    outstanding_amount = Column(Numeric(10, 2), nullable=True)

    clearance_reference = Column(String(100), nullable=True, index=True)
    confirmed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    deferred = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    patient = relationship("Patient", backref="billing_clearances")
    admission = relationship("Admission", backref="billing_clearances")
    transfer = relationship("Transfer", backref="billing_clearances")
    discharge_report = relationship("DischargeReport", backref="billing_clearances")
    confirmer = relationship("User", foreign_keys=[confirmed_by])
