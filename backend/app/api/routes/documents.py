from typing import List, Optional
import os
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, require_roles, require_staff
from app.api.dependencies.database import get_db
from app.models.clinical_document import ClinicalDocument, ClinicalDocumentType, DocumentStatus
from app.models.user import User, UserRole
from app.services.clinical_document_service import ClinicalDocumentService

router = APIRouter(prefix="", tags=["Clinical Documents & OCR"])


@router.post(
    "/admissions/{admission_id}/documents",
    status_code=status.HTTP_201_CREATED,
    summary="Upload clinical source document (handwritten notes, treatment sheet, scan) and auto-trigger OCR",
)
async def upload_clinical_document(
    admission_id: int,
    file: UploadFile = File(...),
    document_type: str = Form(ClinicalDocumentType.DOCTOR_HANDWRITTEN_NOTES.value),
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.RECEPTIONIST, UserRole.WARD_ADMIN, UserRole.MEDICAL_SUPERINTENDENT)),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File name is required")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file cannot be empty")

    svc = ClinicalDocumentService(db)
    doc = svc.upload_document(
        admission_id=admission_id,
        uploader=current_user,
        file_name=file.filename,
        file_bytes=file_bytes,
        mime_type=file.content_type or "application/octet-stream",
        document_type=document_type,
    )
    return {
        "id": doc.id,
        "admission_id": doc.admission_id,
        "patient_id": doc.patient_id,
        "document_type": doc.document_type,
        "file_name": doc.file_name,
        "ocr_status": doc.ocr_status.value if hasattr(doc.ocr_status, "value") else str(doc.ocr_status),
        "ocr_confidence": doc.ocr_confidence,
        "ocr_raw_text": doc.ocr_raw_text,
        "structured_data": doc.structured_data,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.get(
    "/admissions/{admission_id}/documents",
    summary="List all clinical source documents and OCR extractions for an admission",
)
def list_clinical_documents(
    admission_id: int,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    svc = ClinicalDocumentService(db)
    docs = svc.list_documents(admission_id)
    return [
        {
            "id": d.id,
            "admission_id": d.admission_id,
            "patient_id": d.patient_id,
            "document_type": d.document_type,
            "file_name": d.file_name,
            "file_size_bytes": d.file_size_bytes,
            "ocr_status": d.ocr_status.value if hasattr(d.ocr_status, "value") else str(d.ocr_status),
            "ocr_confidence": d.ocr_confidence,
            "ocr_raw_text": d.ocr_raw_text,
            "structured_data": d.structured_data,
            "error_message": d.error_message,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@router.get(
    "/documents/{document_id}/file",
    summary="Download original uploaded source document",
)
def get_document_file(
    document_id: int,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    svc = ClinicalDocumentService(db)
    doc = svc.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File on disk not found")

    return FileResponse(
        path=doc.file_path,
        filename=doc.file_name,
        media_type=doc.mime_type,
    )


@router.post(
    "/documents/{document_id}/retry-ocr",
    summary="Retry OCR processing on a previously failed or uploaded document",
)
def retry_document_ocr(
    document_id: int,
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.RECEPTIONIST, UserRole.WARD_ADMIN)),
    db: Session = Depends(get_db),
):
    svc = ClinicalDocumentService(db)
    doc = svc.process_ocr_and_extract(document_id)
    return {
        "id": doc.id,
        "ocr_status": doc.ocr_status.value if hasattr(doc.ocr_status, "value") else str(doc.ocr_status),
        "ocr_confidence": doc.ocr_confidence,
        "ocr_raw_text": doc.ocr_raw_text,
        "structured_data": doc.structured_data,
        "error_message": doc.error_message,
    }
