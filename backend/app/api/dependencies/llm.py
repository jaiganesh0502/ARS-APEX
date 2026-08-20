from fastapi import HTTPException, status

from app.core.config import settings
from app.integrations.llm.client import LLMClientInterface
from app.integrations.llm.replicate_client import (
    LLMConfigurationError,
    LLMProviderError,
    LLMTimeoutError,
    ReplicateLLMClient,
)


def get_llm_client() -> LLMClientInterface:
    """Resolve the configured provider while keeping configuration details private."""
    try:
        return ReplicateLLMClient(settings.REPLICATE_API_TOKEN)
    except LLMConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI generation is not configured",
        ) from error
    except LLMTimeoutError as error:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI generation timed out",
        ) from error
    except LLMProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI generation failed",
        ) from error
