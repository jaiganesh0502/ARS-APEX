import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.api.routes import api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("discharge-api")


async def event_dispatcher_loop():
    """
    Background worker loop that periodically checks for pending workflow events
    and dispatches them to n8n.
    """
    logger.info("Starting background workflow event dispatcher loop...")
    while True:
        try:
            await asyncio.sleep(2.0)
            if settings.ORCHESTRATION_MODE != "manual":
                from app.db.session import SessionLocal
                from app.models.workflow_event import WorkflowEvent
                from app.services.workflow_event_service import WorkflowEventService

                db = SessionLocal()
                try:
                    pending_events = (
                        db.query(WorkflowEvent)
                        .filter(WorkflowEvent.delivery_status == "pending")
                        .order_by(WorkflowEvent.id.asc())
                        .limit(10)
                        .all()
                    )
                    if pending_events:
                        logger.info(f"Found {len(pending_events)} pending workflow events to dispatch.")
                        evt_svc = WorkflowEventService(db)
                        for event in pending_events:
                            logger.info(f"Dispatching WorkflowEvent #{event.id} ({event.event_type}) to n8n...")
                            evt_svc.dispatch_event(event.id)
                except Exception as err:
                    logger.error(f"Error in event_dispatcher_loop query: {err}")
                finally:
                    db.close()
        except asyncio.CancelledError:
            logger.info("Event dispatcher loop stopped.")
            break
        except Exception as err:
            logger.error(f"Unexpected error in event_dispatcher_loop: {err}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Hospital Discharge Orchestration API...")
    dispatcher_task = asyncio.create_task(event_dispatcher_loop())
    yield
    logger.info("Shutting down Hospital Discharge Orchestration API...")
    dispatcher_task.cancel()
    try:
        await dispatcher_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Hospital Discharge & Inter-Hospital Transfer Orchestration API with AI & n8n integration",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Consistent Global Error Handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder({
            "success": False,
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "path": request.url.path,
            }
        })
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({
            "success": False,
            "error": {
                "code": 422,
                "message": "Validation Error",
                "details": exc.errors(),
                "path": request.url.path,
            }
        })
    )


# Mount API Router under /api
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {
        "message": "Hospital Discharge & Transfer Orchestration API",
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health"
    }
