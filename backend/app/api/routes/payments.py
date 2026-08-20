from decimal import Decimal
from typing import Any, Dict, Optional
from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, require_billing_staff, require_receptionist
from app.api.dependencies.database import get_db
from app.models.invoice import Invoice, PaymentMethod, PaymentStatus
from app.models.user import User, UserRole
from app.services.billing_service import BillingService

router = APIRouter(prefix="", tags=["Payments"])


class ManualPaymentRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Payment amount collected")
    payment_method: str = Field(..., description="Payment method: cash, card, upi_manual")
    reference: str = Field(..., description="Receipt number or transaction reference")
    notes: Optional[str] = Field(None, description="Additional cashier/receptionist notes")


class OnlinePaymentSimulateRequest(BaseModel):
    invoice_number: str
    amount: Optional[Decimal] = None
    transaction_reference: Optional[str] = None


@router.post(
    "/invoices/{invoice_id}/payments/manual",
    summary="Record manual offline payment by Receptionist (cash, card, UPI receipt)",
)
def record_manual_payment(
    invoice_id: int,
    req: ManualPaymentRequest,
    current_user: User = Depends(require_billing_staff),
    db: Session = Depends(get_db),
):
    svc = BillingService(db)
    invoice = svc.record_manual_payment(
        invoice_id=invoice_id,
        amount=req.amount,
        payment_method=req.payment_method,
        reference=req.reference,
        user=current_user,
        notes=req.notes,
    )
    return {
        "success": True,
        "message": "Manual payment recorded successfully",
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "amount_paid_total": float(invoice.amount_paid),
        "balance_remaining": float(invoice.balance_amount),
        "payment_status": invoice.payment_status.value if hasattr(invoice.payment_status, "value") else str(invoice.payment_status),
    }


@router.post(
    "/payments/webhook",
    summary="Online payment gateway webhook callback (idempotent)",
)
def payment_gateway_webhook(
    payload: Dict[str, Any] = Body(...),
    x_signature: Optional[str] = Header(None, alias="X-Payment-Signature"),
    db: Session = Depends(get_db),
):
    svc = BillingService(db)
    result = svc.handle_online_payment_webhook(payload)
    return result


@router.post(
    "/payments/simulate-online",
    summary="Simulate successful online payment callback for test/demo environments",
)
def simulate_online_payment(
    req: OnlinePaymentSimulateRequest,
    db: Session = Depends(get_db),
):
    svc = BillingService(db)
    payload = {
        "invoice_number": req.invoice_number,
        "amount": float(req.amount) if req.amount else None,
        "transaction_reference": req.transaction_reference or f"SIM-UPI-{int(Decimal('1000'))}",
        "status": "success",
    }
    return svc.handle_online_payment_webhook(payload)
