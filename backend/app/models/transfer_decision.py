from datetime import datetime, timezone
import enum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from app.db.session import Base


class TransferDecisionType(str, enum.Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class TransferDecision(Base):
    __tablename__ = "transfer_decisions"

    id = Column(Integer, primary_key=True, index=True)
    transfer_id = Column(Integer, ForeignKey("transfers.id", ondelete="CASCADE"), nullable=False, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="RESTRICT"), nullable=False, index=True)
    decision = Column(
        Enum(TransferDecisionType, name="transfer_decision_type_enum", native_enum=False),
        nullable=False,
        index=True
    )
    reason = Column(Text, nullable=True)
    decided_by = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    decided_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    transfer = relationship("Transfer", back_populates="decisions")
    hospital = relationship("Hospital")
    deciding_user = relationship("User", foreign_keys=[decided_by])
