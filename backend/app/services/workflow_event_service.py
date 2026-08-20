import asyncio
from datetime import datetime, timezone
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.workflow_event import WorkflowEvent
from app.integrations.n8n.client import N8NClient
from app.core.config import settings

logger = logging.getLogger(__name__)


class WorkflowEventService:
    """
    Service for creating, persisting, delivering, and managing audit & orchestration events.
    """

    def __init__(self, db: Session, n8n_client: Optional[N8NClient] = None):
        self.db = db
        self.n8n = n8n_client or N8NClient()

    def record_event(
        self,
        event_type: str,
        entity_type: str,
        entity_id: int,
        payload: Dict[str, Any],
        trusted_provenance: bool = True,
    ) -> WorkflowEvent:
        """
        Persist a domain event to PostgreSQL. Database transaction commits first.
        """
        event = WorkflowEvent(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            status="pending",
            delivery_status="pending",
            orchestration_status="pending",
            attempt_count=0,
            trusted_provenance=trusted_provenance,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        logger.info(f"Recorded WorkflowEvent #{event.id}: {event_type} on {entity_type}:{entity_id}")
        return event

    def dispatch_event(self, event_id: int) -> bool:
        """
        Dispatch the workflow event webhook to n8n synchronously.
        Updates delivery_status, attempt_count, last_attempt_at, and last_error.
        """
        event = self.db.query(WorkflowEvent).filter(WorkflowEvent.id == event_id).first()
        if not event:
            logger.warning(f"Cannot dispatch non-existent WorkflowEvent #{event_id}")
            return False

        event.attempt_count += 1
        now = datetime.now(timezone.utc)
        event.last_attempt_at = now

        webhook_payload = {
            "event_id": event.id,
            "event_type": event.event_type,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "payload": event.payload,
            "created_at": event.created_at.isoformat() if event.created_at else now.isoformat(),
        }

        # Run async client in current event loop or asyncio.run
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # In an active event loop (e.g. FastAPI route), create task or run
                import nest_asyncio
                # Run coroutine directly
                coro = self.n8n.send_webhook(event.event_type, webhook_payload)
                result = loop.run_until_complete(coro) if not loop.is_running() else asyncio.run(coro)
            else:
                result = loop.run_until_complete(self.n8n.send_webhook(event.event_type, webhook_payload))
        except RuntimeError:
            result = asyncio.run(self.n8n.send_webhook(event.event_type, webhook_payload))
        except Exception as exc:
            logger.error(f"Dispatch error for event #{event.id}: {exc}")
            result = {"success": False, "error": str(exc), "status_code": None}

        if result.get("success"):
            event.delivery_status = "delivered"
            event.delivered_at = datetime.now(timezone.utc)
            event.last_error = None
            if event.orchestration_status == "pending":
                event.orchestration_status = "processing"
        else:
            event.delivery_status = "failed"
            event.last_error = result.get("error") or "Unknown delivery failure"

        self.db.commit()
        self.db.refresh(event)
        return result.get("success", False)

    def record_orchestration_result(
        self,
        event_id: int,
        status: str,
        error: Optional[str] = None,
    ) -> Optional[WorkflowEvent]:
        """
        Record result of downstream orchestration reported by n8n.
        Status: 'completed' | 'failed' | 'processing'
        """
        event = self.db.query(WorkflowEvent).filter(WorkflowEvent.id == event_id).first()
        if not event:
            return None

        event.orchestration_status = status
        if status == "completed":
            event.status = "completed"
            event.last_error = None
        elif status == "failed":
            event.status = "failed"
            if error:
                event.last_error = error

        self.db.commit()
        self.db.refresh(event)
        return event

    def retry_event(self, event_id: int) -> Optional[WorkflowEvent]:
        """
        Manual or internal retry for a pending or failed event.
        """
        event = self.db.query(WorkflowEvent).filter(WorkflowEvent.id == event_id).first()
        if not event:
            return None

        self.dispatch_event(event_id)
        self.db.refresh(event)
        return event

    def list_events(
        self,
        status: Optional[str] = None,
        delivery_status: Optional[str] = None,
        orchestration_status: Optional[str] = None,
        event_type: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[WorkflowEvent]:
        query = self.db.query(WorkflowEvent)
        if status:
            query = query.filter(WorkflowEvent.status == status)
        if delivery_status:
            query = query.filter(WorkflowEvent.delivery_status == delivery_status)
        if orchestration_status:
            query = query.filter(WorkflowEvent.orchestration_status == orchestration_status)
        if event_type:
            query = query.filter(WorkflowEvent.event_type == event_type)
        if entity_type:
            query = query.filter(WorkflowEvent.entity_type == entity_type)
        if entity_id:
            query = query.filter(WorkflowEvent.entity_id == entity_id)

        return query.order_by(WorkflowEvent.created_at.desc(), WorkflowEvent.id.desc()).offset(skip).limit(limit).all()

    def get_dashboard_counts(self) -> Dict[str, int]:
        total = self.db.query(func.count(WorkflowEvent.id)).scalar() or 0
        del_pending = self.db.query(func.count(WorkflowEvent.id)).filter(WorkflowEvent.delivery_status == "pending").scalar() or 0
        del_delivered = self.db.query(func.count(WorkflowEvent.id)).filter(WorkflowEvent.delivery_status == "delivered").scalar() or 0
        del_failed = self.db.query(func.count(WorkflowEvent.id)).filter(WorkflowEvent.delivery_status == "failed").scalar() or 0

        orch_pending = self.db.query(func.count(WorkflowEvent.id)).filter(WorkflowEvent.orchestration_status == "pending").scalar() or 0
        orch_processing = self.db.query(func.count(WorkflowEvent.id)).filter(WorkflowEvent.orchestration_status == "processing").scalar() or 0
        orch_completed = self.db.query(func.count(WorkflowEvent.id)).filter(WorkflowEvent.orchestration_status == "completed").scalar() or 0
        orch_failed = self.db.query(func.count(WorkflowEvent.id)).filter(WorkflowEvent.orchestration_status == "failed").scalar() or 0

        return {
            "total_events": total,
            "delivery_pending": del_pending,
            "delivery_delivered": del_delivered,
            "delivery_failed": del_failed,
            "orchestration_pending": orch_pending,
            "orchestration_processing": orch_processing,
            "orchestration_completed": orch_completed,
            "orchestration_failed": orch_failed,
        }
