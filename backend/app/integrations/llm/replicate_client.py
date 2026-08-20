import json
from typing import Any, Callable, Iterable

import httpx

from app.core.config import settings
from app.integrations.llm.client import LLMClientInterface

try:
    import replicate
except ImportError:  # pragma: no cover - exercised only without installed dependencies
    replicate = None


DISCHARGE_SYSTEM_PROMPT = """You produce a clinical discharge report draft, not a final medical record.
Use only the provided structured context. Never infer or fabricate diagnoses, dates,
medications, test results, follow-up appointments, or instructions. State \"Not documented\"
where required information is absent. Preserve uncertainty and conflicting source information.
Do not declare that discharge, bed release, or downstream orchestration occurred.

Start with the heading: DRAFT — REQUIRES PHYSICIAN REVIEW AND SIGN-OFF
Return plain text with these sections:
Patient and Admission
Primary Diagnosis
Relevant Clinical History
Hospital Course and Treatment
Medication Summary
Recent Clinical Status
Discharge Decision Rationale
Recommended Follow-up for Physician Review
Outstanding Items and Missing Information"""

DRAFT_REVIEW_MARKER = "DRAFT — REQUIRES PHYSICIAN REVIEW AND SIGN-OFF"


class LLMConfigurationError(Exception):
    """Raised when the generation provider is not configured."""


class LLMProviderError(Exception):
    """Raised when the generation provider cannot produce usable content."""


class LLMTimeoutError(LLMProviderError):
    """Raised when the generation provider times out."""


class ReplicateLLMClient(LLMClientInterface):
    def __init__(
        self,
        token: str,
        stream: Callable[..., Iterable[Any]] | None = None,
    ):
        if not token.strip():
            raise LLMConfigurationError("Replicate is not configured")
        if stream is None and replicate is None:
            raise LLMProviderError("The generation provider is unavailable")

        self.token = token
        self.model = settings.LLM_MODEL
        self._stream = stream or replicate.Client(api_token=token).stream

    def generate_discharge_summary(self, patient_context: dict[str, Any]) -> str:
        try:
            events = self._stream(
                self.model,
                input={
                    "prompt": json.dumps(patient_context, default=str, sort_keys=True),
                    "system_prompt": DISCHARGE_SYSTEM_PROMPT,
                    "reasoning_effort": settings.LLM_REASONING_EFFORT,
                    "verbosity": settings.LLM_VERBOSITY,
                    "max_completion_tokens": settings.LLM_MAX_COMPLETION_TOKENS,
                },
            )
            output = "".join(str(event) for event in events).strip()
        except (TimeoutError, httpx.TimeoutException) as error:
            raise LLMTimeoutError("The generation provider timed out") from error
        except Exception as error:
            raise LLMProviderError("The generation provider failed") from error

        if not output:
            raise LLMProviderError("The generation provider returned no content")
        if not output.startswith(DRAFT_REVIEW_MARKER):
            raise LLMProviderError(
                "The generation provider omitted the required review heading"
            )
        return output
