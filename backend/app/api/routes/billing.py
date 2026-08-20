import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_superintendent
from app.models.admission import Admission
from app.models.bed import Bed
from app.models.billing_clearance import BillingClearance, BillingStatus
from app.models.discharge_report import DischargeReport
from app.models.patient import Patient
from app.models.transfer import Transfer
from app.models.user import User
from app.schemas.billing_clearance import (
    BillingClearanceConfirmPayload,
    BillingClearanceDetailRead,
    BillingClearanceRead,
)
from app.services.billing_clearance_service import BillingClearanceService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Billing Clearance"])


def _to_detail_read(b: BillingClearance, db: Session) -> BillingClearanceDetailRead:
    patient = db.query(Patient).filter(Patient.id == b.patient_id).first()
    admission = db.query(Admission).filter(Admission.id == b.admission_id).first()
    bed = db.query(Bed).filter(Bed.id == admission.bed_id).first() if admission and admission.bed_id else None
    report = db.query(DischargeReport).filter(DischargeReport.id == b.discharge_report_id).first() if b.discharge_report_id else None
    transfer = db.query(Transfer).filter(Transfer.id == b.transfer_id).first() if b.transfer_id else None
    confirmer = db.query(User).filter(User.id == b.confirmed_by).first() if b.confirmed_by else None

    return BillingClearanceDetailRead(
        id=b.id,
        patient_id=b.patient_id,
        admission_id=b.admission_id,
        transfer_id=b.transfer_id,
        discharge_report_id=b.discharge_report_id,
        status=b.status,
        total_amount=float(b.total_amount) if b.total_amount is not None else None,
        amount_paid=float(b.amount_paid) if b.amount_paid is not None else None,
        outstanding_amount=float(b.outstanding_amount) if b.outstanding_amount is not None else None,
        clearance_reference=b.clearance_reference,
        confirmed_by=b.confirmed_by,
        confirmed_at=b.confirmed_at,
        deferred=b.deferred,
        notes=b.notes,
        created_at=b.created_at,
        updated_at=b.updated_at,
        patient_name=f"{patient.first_name} {patient.last_name}" if patient else None,
        patient_code=patient.patient_code if patient else None,
        primary_diagnosis=admission.primary_diagnosis if admission else None,
        bed_number=bed.bed_number if bed else None,
        ward=bed.ward if bed else None,
        confirmed_by_name=confirmer.name if confirmer else None,
        report_status=report.status.value if report else None,
        transfer_status=transfer.status.value if transfer else None,
    )


@router.get("/admissions/{admission_id}/billing-clearance", response_model=Optional[BillingClearanceDetailRead])
def get_admission_billing_clearance(
    admission_id: int,
    db: Session = Depends(get_db),
):
    """
    Retrieve current billing clearance state for an admission.
    """
    billing_svc = BillingClearanceService(db)
    clearance = billing_svc.get_by_admission_id(admission_id)
    if not clearance:
        return None
    return _to_detail_read(clearance, db)


@router.get("/billing-clearances", response_model=List[BillingClearanceDetailRead])
def list_billing_clearances(
    status: Optional[BillingStatus] = None,
    deferred: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    List billing clearances for finance/bed manager review.
    """
    billing_svc = BillingClearanceService(db)
    clearances = billing_svc.list_clearances(status=status, deferred=deferred, skip=skip, limit=limit)
    return [_to_detail_read(b, db) for b in clearances]


@router.post("/billing-clearances/{billing_id}/clear", response_model=BillingClearanceDetailRead)
def confirm_billing_clearance(
    billing_id: int,
    payload: BillingClearanceConfirmPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superintendent),
):
    """
    Confirm billing clearance (simulated finance approval). Idempotent.
    Restricted to Medical Superintendent / Ward Admin roles.
    """
    billing_svc = BillingClearanceService(db)
    updated = billing_svc.clear_billing(
        billing_id=billing_id,
        clearance_reference=payload.clearance_reference,
        notes=payload.notes,
        confirmed_by_user=current_user,
    )
    return _to_detail_read(updated, db)
