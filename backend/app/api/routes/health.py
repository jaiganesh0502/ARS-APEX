from fastapi import APIRouter
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """
    Health check endpoint to verify backend service readiness.
    """
    return HealthResponse(
        status="ok",
        service="discharge-orchestration-api"
    )
