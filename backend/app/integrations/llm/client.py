from abc import ABC, abstractmethod
from typing import Any


class LLMClientInterface(ABC):
    """
    Abstract interface for LLM report generation.
    Concrete provider implementations generate discharge report drafts.
    """

    @abstractmethod
    def generate_discharge_summary(self, patient_context: dict[str, Any]) -> str:
        """Generate clinical discharge report draft from structured patient context."""
        raise NotImplementedError
