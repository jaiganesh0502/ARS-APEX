from typing import Optional
from fastapi import Header, HTTPException, status
from app.core.config import settings


async def verify_internal_api_key(
    x_internal_api_key: Optional[str] = Header(None, alias="X-Internal-API-Key")
) -> str:
    """
    Dependency to verify internal service-to-service API key for /api/internal/* routes.
    """
    if not x_internal_api_key or x_internal_api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid or missing X-Internal-API-Key",
        )
    return x_internal_api_key
