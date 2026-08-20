import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.workflow_event import WorkflowEvent

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Persists internal domain events in the database audit table.

    This component does not dispatch webhooks or publish events externally.
    """

    def __init__(self, db: Session):
        self.db = db

    def publish_event(
        self,
        event_type: str,
        entity_type: str,
        entity_id: int,
        payload: Dict[str, Any]
    ) -> WorkflowEvent:
        """Persist an internal workflow audit event."""
        logger.info(f"Persisting domain event: {event_type} on {entity_type}:{entity_id}")
        
        event = WorkflowEvent(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            status="pending",
            trusted_provenance=True,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
