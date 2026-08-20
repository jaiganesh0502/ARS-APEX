import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.api.dependencies.internal_auth import verify_internal_api_key
from app.models.bed import Bed, BedStatus
from app.models.user import User, UserRole
from app.services.bed_release_service import BedReleaseService
from app.services.transfer_service import TransferService
from app.services.transfer_packet_service import TransferPacketService
from app.services.ambulance_dispatch_service import AmbulanceDispatchService
from app.services.billing_clearance_service import BillingClearanceService
from app.services.workflow_event_service import WorkflowEventService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/internal",
    tags=["Internal Orchestration"],
    dependencies=[Depends(verify_internal_api_key)],
)


class InternalEventPayload(BaseModel):
    event_id: Optional[int] = None
    reason: Optional[str] = None
    notes: Optional[str] = None


class InternalErrorPayload(BaseModel):
    error: str
    details: Optional[Dict[str, Any]] = None


class InternalCompletePayload(BaseModel):
    result: Optional[Dict[str, Any]] = None


def _get_system_user(db: Session) -> User:
    """Helper to retrieve or create a system user for automated orchestration actions."""
    system_user = db.query(User).filter(User.email == "orchestrator@system.internal").first()
    if not system_user:
        system_user = User(
            name="n8n Automated Orchestrator",
            email="orchestrator@system.internal",
            role=UserRole.WARD_ADMIN,
        )
        db.add(system_user)
        db.commit()
        db.refresh(system_user)
    return system_user


@router.post("/beds/{bed_id}/start-release")
def internal_start_bed_release(
    bed_id: int,
    payload: Optional[InternalEventPayload] = None,
    db: Session = Depends(get_db),
):
    """
    Automated bed turnover trigger: transitions bed from OCCUPIED to VACATING. Idempotent.
    """
    bed = db.query(Bed).filter(Bed.id == bed_id).first()
    if not bed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bed not found")

    # Idempotent return if already vacating or beyond
    if bed.status == BedStatus.VACATING:
        return {"success": True, "bed_id": bed.id, "status": bed.status.value, "message": "Bed is already vacating"}

    service = BedReleaseService(db)
    system_user = _get_system_user(db)

    updated_bed = service.start_release(bed_id, system_user)
    return {
        "success": True,
        "bed_id": updated_bed.id,
        "status": updated_bed.status.value,
        "message": "Bed release started (vacating)",
    }


@router.post("/admissions/{admission_id}/start-transfer-matching")
def internal_start_transfer_matching(
    admission_id: int,
    payload: Optional[InternalEventPayload] = None,
    db: Session = Depends(get_db),
):
    """
    Initializes transfer case and calculates ranked hospital matches.
    STOPS for human doctor hospital selection.
    """
    system_user = _get_system_user(db)
    trf_svc = TransferService(db)

    transfer = trf_svc.create_or_get_transfer_for_admission(admission_id, requesting_user=system_user)
    matches = trf_svc.get_matches_for_transfer(transfer.id)

    return {
        "success": True,
        "transfer_id": transfer.id,
        "status": transfer.status.value,
        "matches_count": len(matches),
        "matches": [m.model_dump() for m in matches],
        "message": "Transfer matching initialized. Awaiting manual physician hospital selection.",
    }


@router.post("/transfers/{transfer_id}/prepare-packet")
def internal_prepare_transfer_packet(
    transfer_id: int,
    payload: Optional[InternalEventPayload] = None,
    db: Session = Depends(get_db),
):
    """
    Prepares structured clinical transfer packet. Idempotent.
    """
    pkt_svc = TransferPacketService(db)
    packet = pkt_svc.prepare_packet(transfer_id)
    return {
        "success": True,
        "packet_id": packet.id,
        "transfer_id": packet.transfer_id,
        "status": packet.status.value,
    }


@router.post("/transfers/{transfer_id}/send-packet")
def internal_send_transfer_packet(
    transfer_id: int,
    payload: Optional[InternalEventPayload] = None,
    db: Session = Depends(get_db),
):
    """
    Delivers structured clinical packet into receiving hospital review queue. Idempotent.
    """
    system_user = _get_system_user(db)
    pkt_svc = TransferPacketService(db)
    packet = pkt_svc.send_packet(transfer_id, sender_user=system_user)
    return {
        "success": True,
        "packet_id": packet.id,
        "transfer_id": packet.transfer_id,
        "status": packet.status.value,
        "message": "Transfer packet sent to receiving facility review queue.",
    }


@router.post("/transfers/{transfer_id}/dispatch-ambulance")
def internal_dispatch_ambulance(
    transfer_id: int,
    payload: Optional[InternalEventPayload] = None,
    db: Session = Depends(get_db),
):
    """
    Dispatches ambulance with calculated simulated ETA duration. Idempotent.
    """
    system_user = _get_system_user(db)
    amb_svc = AmbulanceDispatchService(db)
    dispatch = amb_svc.dispatch_ambulance(transfer_id, requesting_user=system_user)
    return {
        "success": True,
        "dispatch_id": dispatch.id,
        "dispatch_reference": dispatch.dispatch_reference,
        "status": dispatch.status.value,
        "distance_km": float(dispatch.distance_km),
        "current_eta_minutes": dispatch.current_eta_minutes,
        "vehicle_number": dispatch.vehicle_number,
    }


@router.post("/admissions/{admission_id}/billing-clearance")
def internal_get_or_create_billing_clearance(
    admission_id: int,
    payload: Optional[InternalEventPayload] = None,
    db: Session = Depends(get_db),
):
    """
    Retrieves or initializes pending billing clearance for an admission. Idempotent.
    """
    billing_svc = BillingClearanceService(db)
    clearance = billing_svc.get_or_create_clearance(admission_id)
    return {
        "success": True,
        "billing_id": clearance.id,
        "admission_id": clearance.admission_id,
        "status": clearance.status.value,
        "outstanding_amount": float(clearance.outstanding_amount or 0.0),
        "deferred": clearance.deferred,
    }


@router.post("/billing-clearances/{billing_id}/finalize-handoff")
def internal_finalize_handoff(
    billing_id: int,
    payload: Optional[InternalEventPayload] = None,
    db: Session = Depends(get_db),
):
    """
    Finalizes discharge handoff authorization if doctor approved AND billing cleared.
    """
    billing_svc = BillingClearanceService(db)
    clearance = billing_svc.get_by_id(billing_id)
    if not clearance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing clearance not found")

    result = billing_svc.finalize_discharge_authorization(clearance.admission_id)

    # Automatically generate the final discharge package and PDF
    from app.services.discharge_package_service import DischargePackageService
    from app.models.discharge_package import DischargePackage
    pkg = db.query(DischargePackage).filter(DischargePackage.admission_id == clearance.admission_id).first()
    if not pkg:
        system_user = _get_system_user(db)
        pkg_svc = DischargePackageService(db)
        package = pkg_svc.finalize_discharge_package(
            admission_id=clearance.admission_id,
            authorizing_user=system_user,
            notes="Automated discharge package authorization by n8n workflow on billing clearance",
        )
        result["package_id"] = package.id
        result["pdf_ready"] = bool(package.pdf_path)

    return result


@router.post("/admissions/{admission_id}/finalize-discharge")
def internal_finalize_discharge(
    admission_id: int,
    payload: Optional[InternalEventPayload] = None,
    db: Session = Depends(get_db),
):
    """
    Automated n8n trigger to finalize discharge package and generate PDF once billing clears.
    """
    from app.services.discharge_package_service import DischargePackageService
    system_user = _get_system_user(db)
    pkg_svc = DischargePackageService(db)
    package = pkg_svc.finalize_discharge_package(
        admission_id=admission_id,
        authorizing_user=system_user,
        notes=payload.reason if payload else "Automated discharge package authorization by n8n workflow",
    )
    return {
        "success": True,
        "package_id": package.id,
        "admission_id": package.admission_id,
        "status": package.status.value,
        "pdf_ready": bool(package.pdf_path),
    }


@router.post("/workflow-events/{event_id}/complete")
def internal_complete_workflow_event(
    event_id: int,
    payload: Optional[InternalCompletePayload] = None,
    db: Session = Depends(get_db),
):
    """
    Callback endpoint for n8n to report successful workflow execution.
    """
    evt_svc = WorkflowEventService(db)
    event = evt_svc.record_orchestration_result(event_id, "completed")
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow event not found")
    return {"success": True, "event_id": event.id, "orchestration_status": event.orchestration_status}


@router.post("/workflow-events/{event_id}/fail")
def internal_fail_workflow_event(
    event_id: int,
    payload: InternalErrorPayload,
    db: Session = Depends(get_db),
):
    """
    Callback endpoint for n8n to report failed workflow execution.
    """
    evt_svc = WorkflowEventService(db)
    event = evt_svc.record_orchestration_result(event_id, "failed", error=payload.error)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow event not found")
    return {"success": True, "event_id": event.id, "orchestration_status": event.orchestration_status}


@router.post("/workflow-events/{event_id}/retry")
def internal_retry_workflow_event(
    event_id: int,
    db: Session = Depends(get_db),
):
    """
    Re-attempts delivery of an event to n8n.
    """
    evt_svc = WorkflowEventService(db)
    event = evt_svc.retry_event(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow event not found")
    return {
        "success": True,
        "event_id": event.id,
        "delivery_status": event.delivery_status,
        "attempt_count": event.attempt_count,
        "last_error": event.last_error,
    }
