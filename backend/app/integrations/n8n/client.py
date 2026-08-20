from abc import ABC, abstractmethod
from typing import Dict, Any


class N8nClientInterface(ABC):
    """
    Abstract interface for triggering n8n webhook workflows.
    """

    @abstractmethod
    async def trigger_workflow(self, workflow_name: str, payload: Dict[str, Any]) -> bool:
        """Post an event payload to a configured n8n webhook endpoint."""
        pass
