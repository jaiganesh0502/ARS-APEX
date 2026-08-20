from datetime import datetime, timezone
import enum
from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.orm import relationship

from app.db.session import Base


class UserRole(str, enum.Enum):
    DOCTOR = "doctor"
    WARD_ADMIN = "ward_admin"
    RECEIVING_DOCTOR = "receiving_doctor"
    RECEIVING_ADMIN = "receiving_admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    role = Column(Enum(UserRole, name="user_role_enum", native_enum=False), default=UserRole.DOCTOR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    attended_admissions = relationship("Admission", back_populates="attending_doctor")
    approved_discharge_reports = relationship("DischargeReport", back_populates="approving_doctor")
    clinical_decisions = relationship("ClinicalDecision", back_populates="deciding_doctor")
