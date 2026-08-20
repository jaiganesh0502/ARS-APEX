from abc import ABC, abstractmethod
from typing import List, Dict, Any


class NotificationClientInterface(ABC):
    """
    Abstract interface for multi-channel dispatch (SMS, Email, Pager, Push notifications).
    """

    @abstractmethod
    async def send_notification(
        self,
        recipient: str,
        channel: str,
        title: str,
        message: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """Dispatch notification to clinician, transport coordinator, or ward admin."""
        pass
