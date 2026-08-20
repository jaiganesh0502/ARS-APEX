import logging
from typing import Dict, Any, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class N8NClient:
    """
    Low-level HTTP transport client for dispatching signed workflow events to n8n.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ):
        self.base_url = base_url or settings.N8N_BASE_URL
        self.webhook_url = webhook_url or settings.N8N_WEBHOOK_URL
        self.webhook_secret = webhook_secret or settings.N8N_WEBHOOK_SECRET
        self.timeout_seconds = timeout_seconds or settings.N8N_TIMEOUT_SECONDS

    async def send_webhook(
        self,
        event_type: str,
        payload: Dict[str, Any],
        endpoint_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a signed webhook POST request to n8n.

        Returns a dictionary:
            {"success": bool, "status_code": int | None, "error": str | None, "data": Any}
        """
        if settings.ORCHESTRATION_MODE == "manual":
            logger.info("ORCHESTRATION_MODE is 'manual'. Skipping n8n webhook delivery.")
            return {
                "success": True,
                "status_code": 200,
                "error": None,
                "data": {"mode": "manual_bypass"},
            }

        url = endpoint_path if endpoint_path else f"{self.webhook_url.rstrip('/')}/{event_type}"

        headers = {
            "Content-Type": "application/json",
            "X-Workflow-Secret": self.webhook_secret,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code in (200, 201, 202, 204):
                    logger.info(f"Successfully delivered event '{event_type}' to n8n ({response.status_code})")
                    try:
                        resp_data = response.json()
                    except Exception:
                        resp_data = response.text
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "error": None,
                        "data": resp_data,
                    }
                else:
                    error_msg = f"n8n responded with status {response.status_code}: {response.text[:200]}"
                    logger.warning(f"n8n webhook warning for '{event_type}': {error_msg}")
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "error": error_msg,
                        "data": None,
                    }
        except httpx.TimeoutException as exc:
            error_msg = f"n8n webhook timeout ({self.timeout_seconds}s) connecting to {url}"
            logger.warning(error_msg)
            return {"success": False, "status_code": None, "error": error_msg, "data": None}
        except httpx.RequestError as exc:
            error_msg = f"n8n connection error: {str(exc)}"
            logger.warning(error_msg)
            return {"success": False, "status_code": None, "error": error_msg, "data": None}
        except Exception as exc:
            error_msg = f"Unexpected n8n client error: {str(exc)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "status_code": None, "error": error_msg, "data": None}


# Backwards-compatible alias
N8nClientInterface = N8NClient

__all__ = ["N8NClient", "N8nClientInterface"]

