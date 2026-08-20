from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from sqlalchemy.orm import relationship

from app.db.session import Base


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    specialties = Column(JSON, default=list, nullable=False)
    contact_number = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    capacities = relationship("HospitalCapacity", back_populates="hospital", cascade="all, delete-orphan")
    transfers_sent = relationship("Transfer", foreign_keys="Transfer.sending_hospital_id", back_populates="sending_hospital")
    transfers_received = relationship("Transfer", foreign_keys="Transfer.receiving_hospital_id", back_populates="receiving_hospital")
