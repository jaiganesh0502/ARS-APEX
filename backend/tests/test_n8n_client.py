import pytest
from unittest.mock import AsyncMock, patch
import httpx

from app.integrations.n8n.client import N8NClient
from app.models.workflow_event import WorkflowEvent
from app.services.workflow_event_service import WorkflowEventService
from app.core.config import settings


@pytest.mark.asyncio
async def test_n8n_client_manual_mode_bypass():
    """Verify manual mode returns immediate success bypass without network call."""
    with patch.object(settings, "ORCHESTRATION_MODE", "manual"):
        client = N8NClient()
        res = await client.send_webhook("report_approved", {"event_id": 1})
        assert res["success"] is True
        assert res["data"] == {"mode": "manual_bypass"}


@pytest.mark.asyncio
async def test_n8n_client_http_delivery_success():
    """Verify HTTP client delivers signed payload with correct headers and handles 200 response."""
    with patch.object(settings, "ORCHESTRATION_MODE", "n8n"):
        client = N8NClient(
            base_url="http://mock-n8n:5678",
            webhook_url="http://mock-n8n:5678/webhook/",
            webhook_secret="test-secret-key",
            timeout_seconds=2.0,
        )

        mock_resp = httpx.Response(200, json={"received": True})
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            res = await client.send_webhook("report_approved", {"event_id": 1, "test": "val"})
            assert res["success"] is True
            assert res["status_code"] == 200

            mock_post.assert_called_once()
            _, kwargs = mock_post.call_args
            assert kwargs["headers"]["X-Workflow-Secret"] == "test-secret-key"


@pytest.mark.asyncio
async def test_n8n_client_timeout_handling():
    """Verify network timeout returns clean error dict without raising unhandled exception."""
    with patch.object(settings, "ORCHESTRATION_MODE", "n8n"):
        client = N8NClient(timeout_seconds=0.1)

        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Connection timed out")):
            res = await client.send_webhook("report_approved", {"event_id": 1})
            assert res["success"] is False
            assert "timeout" in res["error"]


def test_workflow_event_service_dispatch_and_orchestration_tracking(db_session):
    """Verify WorkflowEventService updates delivery_status and orchestration_status distinctly."""
    evt_svc = WorkflowEventService(db_session)
    event = evt_svc.record_event(
        event_type="report_approved",
        entity_type="discharge_report",
        entity_id=1,
        payload={"admission_id": 10},
    )

    assert event.delivery_status == "pending"
    assert event.orchestration_status == "pending"
    assert event.attempt_count == 0

    # Simulate dispatch in manual mode
    evt_svc.dispatch_event(event.id)
    assert event.delivery_status == "delivered"
    assert event.attempt_count == 1
    assert event.delivered_at is not None

    # Simulate n8n completion callback
    updated = evt_svc.record_orchestration_result(event.id, status="completed")
    assert updated.orchestration_status == "completed"
    assert updated.status == "completed"
