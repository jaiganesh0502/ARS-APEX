from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Integer, String, JSON, DateTime, false

from app.db.session import Base


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    payload = Column(JSON, default=dict, nullable=False)
    # Legacy status maintained for backwards compatibility
    status = Column(String(50), default="pending", nullable=False, index=True)

    # Granular Event Delivery & Orchestration Tracking
    delivery_status = Column(String(30), default="pending", server_default="pending", nullable=False, index=True)
    orchestration_status = Column(String(30), default="pending", server_default="pending", nullable=False, index=True)
    attempt_count = Column(Integer, default=0, server_default="0", nullable=False)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(String(1000), nullable=True)

    trusted_provenance = Column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
