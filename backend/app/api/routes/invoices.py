from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, require_billing_staff, require_staff
from app.api.dependencies.database import get_db
from app.models.charge_master import ChargeCategory, ChargeMasterItem
from app.models.invoice import Invoice, InvoiceLineItem, PaymentStatus
from app.models.user import User, UserRole
from app.services.billing_service import BillingService
from app.services.charge_master_service import ChargeMasterService

router = APIRouter(prefix="", tags=["Invoices & Charge Master"])


@router.get(
    "/admissions/{admission_id}/invoice",
    summary="Get or generate deterministic invoice for an admission",
)
def get_admission_invoice(
    admission_id: int,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    svc = BillingService(db)
    invoice = svc.generate_or_get_invoice(admission_id)
    return format_invoice_response(invoice)


@router.post(
    "/admissions/{admission_id}/invoice/calculate",
    summary="Force calculate / recalculate deterministic invoice",
)
def calculate_admission_invoice(
    admission_id: int,
    current_user: User = Depends(require_billing_staff),
    db: Session = Depends(get_db),
):
    svc = BillingService(db)
    invoice = svc.generate_or_get_invoice(admission_id)
    return format_invoice_response(invoice)


@router.get(
    "/invoices/{invoice_id}",
    summary="Get detailed invoice breakdown by invoice ID",
)
def get_invoice_by_id(
    invoice_id: int,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    svc = BillingService(db)
    invoice = svc.get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return format_invoice_response(invoice)


@router.get(
    "/invoices",
    summary="List all inpatient invoices for reception billing queue",
)
def list_invoices(
    payment_status: Optional[str] = Query(None),
    current_user: User = Depends(require_billing_staff),
    db: Session = Depends(get_db),
):
    query = db.query(Invoice).order_by(Invoice.created_at.desc())
    if payment_status:
        query = query.filter(Invoice.payment_status == payment_status)
    invoices = query.limit(100).all()
    return [format_invoice_response(inv) for inv in invoices]


@router.get(
    "/charge-master",
    summary="List standard hospital ChargeMaster catalog",
)
def list_charge_master(
    category: Optional[str] = Query(None),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    svc = ChargeMasterService(db)
    svc.seed_defaults_if_empty()
    cat_enum = ChargeCategory(category) if category else None
    items = svc.list_items(category=cat_enum)
    return [
        {
            "id": i.id,
            "code": i.code,
            "category": i.category.value if hasattr(i.category, "value") else str(i.category),
            "name": i.name,
            "unit_price": float(i.unit_price),
            "description": i.description,
            "is_active": i.is_active,
        }
        for i in items
    ]


def format_invoice_response(invoice: Invoice) -> dict:
    patient = invoice.patient
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "admission_id": invoice.admission_id,
        "patient_id": invoice.patient_id,
        "patient_name": f"{patient.first_name} {patient.last_name}" if patient else "Patient",
        "patient_code": patient.patient_code if patient else "N/A",
        "subtotal": float(invoice.subtotal or 0.0),
        "discount_amount": float(invoice.discount_amount or 0.0),
        "tax_amount": float(invoice.tax_amount or 0.0),
        "total_amount": float(invoice.total_amount or 0.0),
        "amount_paid": float(invoice.amount_paid or 0.0),
        "balance_amount": float(invoice.balance_amount or 0.0),
        "payment_status": invoice.payment_status.value if hasattr(invoice.payment_status, "value") else str(invoice.payment_status),
        "qr_code_uri": invoice.qr_code_uri,
        "notes": invoice.notes,
        "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
        "line_items": [
            {
                "id": li.id,
                "category": li.category,
                "description": li.description,
                "quantity": float(li.quantity),
                "unit_price": float(li.unit_price),
                "amount": float(li.amount),
                "source_reference": li.source_reference,
            }
            for li in invoice.line_items
        ],
        "payments": [
            {
                "id": p.id,
                "amount": float(p.amount),
                "payment_method": p.payment_method,
                "transaction_reference": p.transaction_reference,
                "confirmed_at": p.confirmed_at.isoformat() if p.confirmed_at else None,
                "notes": p.notes,
            }
            for p in invoice.payments
        ],
    }
