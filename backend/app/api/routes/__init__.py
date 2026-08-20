from fastapi import APIRouter
from app.api.routes import (
    health,
    users,
    patients,
    admissions,
    beds,
    discharge,
    discharge_packages,
    transfers,
    receiving,
    hospitals,
    ambulance,
    events,
    clinical_decisions,
    billing,
    internal,
    notifications,
    auth,
    patient_portal,
    documents,
    invoices,
    payments,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(patients.router)
api_router.include_router(patient_portal.router)
api_router.include_router(admissions.router)
api_router.include_router(documents.router)
api_router.include_router(invoices.router)
api_router.include_router(payments.router)
api_router.include_router(beds.router)
api_router.include_router(discharge.router)
api_router.include_router(discharge_packages.router)
api_router.include_router(transfers.router)
api_router.include_router(receiving.router)
api_router.include_router(hospitals.router)
api_router.include_router(ambulance.router)
api_router.include_router(events.router)
api_router.include_router(clinical_decisions.router)
api_router.include_router(billing.router)
api_router.include_router(internal.router)
api_router.include_router(notifications.router)

__all__ = ["api_router"]
