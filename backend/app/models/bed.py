from datetime import datetime, timezone
import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from app.db.session import Base


class BedStatus(str, enum.Enum):
    OCCUPIED = "occupied"
    VACATING = "vacating"
    CLEANING = "cleaning"
    AVAILABLE = "available"
    RESERVED = "reserved"


class Bed(Base):
    __tablename__ = "beds"

    id = Column(Integer, primary_key=True, index=True)
    ward = Column(String(100), nullable=False, index=True)
    bed_number = Column(String(50), nullable=False, index=True)
    status = Column(
        Enum(BedStatus, name="bed_status_enum", native_enum=False),
        default=BedStatus.AVAILABLE,
        nullable=False,
        index=True
    )
    current_patient_id = Column(Integer, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    current_patient = relationship("Patient", foreign_keys=[current_patient_id])
    admissions = relationship("Admission", back_populates="bed")
