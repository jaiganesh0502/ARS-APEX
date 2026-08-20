from fastapi import APIRouter
from app.api.routes import (
    health,
    users,
    patients,
    admissions,
    beds,
    discharge,
    transfers,
    hospitals,
    ambulance,
    events,
    clinical_decisions,
    receiving,
    billing,
    internal,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(users.router)
api_router.include_router(patients.router)
api_router.include_router(admissions.router)
api_router.include_router(beds.router)
api_router.include_router(discharge.router)
api_router.include_router(transfers.router)
api_router.include_router(receiving.router)
api_router.include_router(hospitals.router)
api_router.include_router(ambulance.router)
api_router.include_router(events.router)
api_router.include_router(clinical_decisions.router)
api_router.include_router(billing.router)
api_router.include_router(internal.router)

__all__ = ["api_router"]
