import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_patient_entity, get_db
from app.models.admission import Admission
from app.models.discharge_package import DischargePackage
from app.models.patient import Patient

router = APIRouter(prefix="/patient-portal", tags=["Patient Portal"])


@router.get("/profile")
def get_patient_portal_profile(
    patient: Patient = Depends(get_current_patient_entity),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns the authenticated patient's profile and active admission status.
    Strictly isolated to the authenticated patient's own identity.
    """
    latest_admission = (
        db.query(Admission)
        .filter(Admission.patient_id == patient.id)
        .order_by(Admission.id.desc())
        .first()
    )

    package = (
        db.query(DischargePackage)
        .filter(DischargePackage.patient_id == patient.id)
        .order_by(DischargePackage.id.desc())
        .first()
    )

    has_pdf = bool(package and package.pdf_path and os.path.exists(package.pdf_path))

    from app.models.invoice import Invoice
    invoice = None
    if latest_admission:
        invoice = db.query(Invoice).filter(Invoice.admission_id == latest_admission.id).first()

    return {
        "patient": {
            "id": patient.id,
            "patient_code": patient.patient_code,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
            "gender": patient.gender,
            "blood_group": patient.blood_group,
            "phone": patient.phone,
        },
        "admission": {
            "id": latest_admission.id if latest_admission else None,
            "status": latest_admission.status.value if latest_admission else None,
            "primary_diagnosis": latest_admission.primary_diagnosis if latest_admission else None,
            "admission_date": latest_admission.admission_date.isoformat() if latest_admission and latest_admission.admission_date else None,
            "attending_doctor": latest_admission.attending_doctor.name if latest_admission and latest_admission.attending_doctor else None,
            "discharge_ready": latest_admission.discharge_ready if latest_admission else False,
        } if latest_admission else None,
        "bed": {
            "ward": latest_admission.bed.ward,
            "bed_number": latest_admission.bed.bed_number,
        } if latest_admission and latest_admission.bed else None,
        "invoice": {
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "subtotal": float(invoice.subtotal or 0.0),
            "discount_amount": float(invoice.discount_amount or 0.0),
            "tax_amount": float(invoice.tax_amount or 0.0),
            "total_amount": float(invoice.total_amount or 0.0),
            "amount_paid": float(invoice.amount_paid or 0.0),
            "balance_amount": float(invoice.balance_amount or 0.0),
            "payment_status": invoice.payment_status.value if hasattr(invoice.payment_status, "value") else str(invoice.payment_status),
            "qr_code_uri": invoice.qr_code_uri,
        } if invoice else None,
        "discharge_package": {
            "id": package.id if package else None,
            "status": package.status.value if package else None,
            "authorized_at": package.authorized_at.isoformat() if package and package.authorized_at else None,
            "has_pdf": has_pdf,
            "download_url": "/api/patient-portal/pdf" if has_pdf else None,
            "patient_summary": package.patient_summary if package else None,
        } if package else None,
    }


@router.get("/discharge-summary")
def get_patient_discharge_summary(
    patient: Patient = Depends(get_current_patient_entity),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns the plain-language care summary for the authenticated patient.
    """
    package = (
        db.query(DischargePackage)
        .filter(DischargePackage.patient_id == patient.id)
        .order_by(DischargePackage.id.desc())
        .first()
    )

    if not package or not package.patient_summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discharge summary is not yet prepared for your record.",
        )

    return package.patient_summary


@router.get("/pdf")
def download_patient_discharge_pdf(
    patient: Patient = Depends(get_current_patient_entity),
    db: Session = Depends(get_db),
):
    """
    Securely streams the authenticated patient's finalized discharge PDF.
    """
    package = (
        db.query(DischargePackage)
        .filter(DischargePackage.patient_id == patient.id)
        .order_by(DischargePackage.id.desc())
        .first()
    )

    if not package or not package.pdf_path or not os.path.exists(package.pdf_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Your finalized discharge PDF document is not ready yet.",
        )

    filename = Path(package.pdf_path).name or f"discharge_{patient.patient_code}.pdf"
    return FileResponse(
        path=package.pdf_path,
        media_type="application/pdf",
        filename=filename,
    )
