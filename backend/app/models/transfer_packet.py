from datetime import datetime, timezone
import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship

from app.db.session import Base


class TransferPacketStatus(str, enum.Enum):
    PREPARED = "prepared"
    SENT = "sent"
    VIEWED = "viewed"


class TransferPacket(Base):
    __tablename__ = "transfer_packets"

    id = Column(Integer, primary_key=True, index=True)
    transfer_id = Column(Integer, ForeignKey("transfers.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    admission_id = Column(Integer, ForeignKey("admissions.id", ondelete="CASCADE"), nullable=False, index=True)
    packet_content = Column(JSON, nullable=False, default=dict)
    status = Column(
        Enum(TransferPacketStatus, name="transfer_packet_status_enum", native_enum=False),
        default=TransferPacketStatus.PREPARED,
        nullable=False,
        index=True
    )
    prepared_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    viewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    transfer = relationship("Transfer", back_populates="packets")
    patient = relationship("Patient")
    admission = relationship("Admission")
