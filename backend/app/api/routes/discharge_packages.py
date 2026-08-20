import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, require_staff, require_superintendent
from app.models.discharge_package import DischargePackage
from app.models.user import User, UserRole
from app.schemas.discharge_package import DischargePackageDetail, FinalizePackageRequest
from app.services.discharge_package_service import DischargePackageService

router = APIRouter(tags=["Discharge Packages"])


def _to_package_detail(package: DischargePackage) -> DischargePackageDetail:
    pdf_ready = bool(package.pdf_path and os.path.exists(package.pdf_path))
    download_url = f"/api/discharge-packages/{package.id}/pdf" if pdf_ready else None
    return DischargePackageDetail(
        id=package.id,
        patient_id=package.patient_id,
        admission_id=package.admission_id,
        discharge_report_id=package.discharge_report_id,
        billing_clearance_id=package.billing_clearance_id,
        status=package.status.value if hasattr(package.status, "value") else str(package.status),
        clinical_snapshot=package.clinical_snapshot or {},
        patient_summary=package.patient_summary or {},
        pdf_path=package.pdf_path,
        pdf_generated_at=package.pdf_generated_at,
        authorized_at=package.authorized_at,
        authorized_by=package.authorized_by,
        created_at=package.created_at,
        updated_at=package.updated_at,
        pdf_ready=pdf_ready,
        download_url=download_url,
    )


@router.post("/admissions/{admission_id}/final-discharge-package", response_model=DischargePackageDetail)
def finalize_discharge_package(
    admission_id: int,
    payload: Optional[FinalizePackageRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """
    Authorizes and creates the final patient discharge package once the clinical report
    is approved and billing clearance is cleared. Restricted to Medical Superintendent.
    """
    service = DischargePackageService(db)
    package = service.finalize_discharge_package(
        admission_id=admission_id,
        authorizing_user=current_user,
        notes=payload.notes if payload else None,
    )
    return _to_package_detail(package)


@router.get("/admissions/{admission_id}/discharge-package", response_model=Optional[DischargePackageDetail])
def get_admission_discharge_package(
    admission_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_staff),
):
    """
    Retrieves the final discharge package for a given admission, if generated.
    """
    service = DischargePackageService(db)
    package = service.get_by_admission_id(admission_id)
    if not package:
        return None
    return _to_package_detail(package)


@router.get("/discharge-packages/{package_id}", response_model=DischargePackageDetail)
def get_discharge_package_by_id(
    package_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves a discharge package by its primary ID with ownership validation.
    """
    service = DischargePackageService(db)
    package = service.get_by_id(package_id)
    if not package:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge package not found")

    if current_user.role == UserRole.PATIENT:
        if package.patient_id != current_user.patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You can only access your own discharge package",
            )

    return _to_package_detail(package)


@router.get("/discharge-packages/{package_id}/pdf")
def download_discharge_package_pdf(
    package_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Downloads or streams the finalized discharge PDF document securely.
    Enforces strict patient identity and ownership verification.
    """
    service = DischargePackageService(db)
    package = service.get_by_id(package_id)
    if not package:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge package not found")

    # Strict Patient Ownership Check
    if current_user.role == UserRole.PATIENT:
        if package.patient_id != current_user.patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You can only download your own discharge PDF",
            )

    if not package.pdf_path or not os.path.exists(package.pdf_path):
        # Attempt self-healing regeneration
        package = service.retry_pdf_generation(package_id)

    if not package.pdf_path or not os.path.exists(package.pdf_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge package PDF is not ready")

    p_code = package.clinical_snapshot.get("patient_code", f"PT-{package.patient_id}")
    filename = Path(package.pdf_path).name or f"discharge_{p_code}.pdf"

    return FileResponse(
        path=package.pdf_path,
        media_type="application/pdf",
        filename=filename,
    )


@router.post("/discharge-packages/{package_id}/generate-pdf", response_model=DischargePackageDetail)
def retry_generate_pdf(
    package_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_superintendent),
):
    """
    Idempotently retries PDF generation for an authorized package.
    """
    service = DischargePackageService(db)
    package = service.retry_pdf_generation(package_id)
    return _to_package_detail(package)
