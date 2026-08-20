from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.api.dependencies.auth import get_current_user_stub
from app.api.dependencies.llm import get_llm_client
from app.integrations.llm.client import LLMClientInterface
from app.integrations.llm.replicate_client import (
    LLMConfigurationError,
    LLMProviderError,
    LLMTimeoutError,
)
from app.services.discharge_service import DischargeService
from app.schemas.discharge_report import (
    DischargeReportRead,
    DischargeReportCreate,
    DischargeReportEdit,
    DischargeReportApprove,
)
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.user import User, UserRole

router = APIRouter(prefix="/discharge", tags=["Discharge Orchestration"])


@router.get("/reports", response_model=List[DischargeReportRead])
def list_reports(status: DischargeReportStatus = None, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    query = db.query(DischargeReport)
    if status:
        query = query.filter(DischargeReport.status == status)
    return query.offset(skip).limit(limit).all()


@router.get("/reports/{report_id}", response_model=DischargeReportRead)
def get_report(report_id: int, db: Session = Depends(get_db)):
    service = DischargeService(db)
    report = service.repo.get(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge report not found")
    return report


@router.get("/admissions/{admission_id}/report", response_model=DischargeReportRead)
def get_report_for_admission(admission_id: int, db: Session = Depends(get_db)):
    report = DischargeService(db).repo.get_by_admission_id(admission_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge report not found")
    return report


@router.post("/generate/{admission_id}", response_model=DischargeReportRead, status_code=status.HTTP_201_CREATED)
def generate_discharge_draft(
    admission_id: int,
    db: Session = Depends(get_db),
    llm_client: LLMClientInterface = Depends(get_llm_client),
):
    """
    Trigger AI draft generation.
    SAFETY: Generates a DRAFT report (status='generated'). Does NOT approve.
    """
    try:
        return DischargeService(db).generate_report(admission_id, llm_client)
    except LLMConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI generation is not configured",
        ) from error
    except LLMTimeoutError as error:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI generation timed out",
        ) from error
    except LLMProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI generation failed",
        ) from error


@router.put("/reports/{report_id}/edit", response_model=DischargeReportRead)
def edit_discharge_report(
    report_id: int,
    edit_in: DischargeReportEdit,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_stub),
):
    """Doctor reviews and modifies the discharge report."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if current_user.role != UserRole.DOCTOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can edit discharge reports")
    return DischargeService(db).edit_report(report_id, edit_in.edited_content, current_user)


@router.post("/reports/{report_id}/approve", response_model=DischargeReportRead)
def approve_discharge_report(
    report_id: int,
    approval_in: DischargeReportApprove,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_stub),
):
    """
    MANDATORY CLINICAL SAFETY: Explicit physician approval of discharge summary.
    Transitions status to 'approved' and records an internal 'report_approved' event.
    """
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if current_user.role != UserRole.DOCTOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can approve discharge reports")
    return DischargeService(db).approve_report(report_id, current_user, approval_in.clinical_notes)
