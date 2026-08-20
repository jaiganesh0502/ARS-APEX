from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class PatientSummary(BaseModel):
    why_you_were_admitted: str = ""
    what_treatment_you_received: str = ""
    medications_to_take: List[str] = []
    medications_to_stop: List[str] = []
    diet_instructions: str = ""
    activity_instructions: str = ""
    follow_up_plan: str = ""
    warning_signs: List[str] = []
    when_to_seek_urgent_help: str = ""


class DischargePackageBase(BaseModel):
    patient_id: int
    admission_id: int
    discharge_report_id: int
    billing_clearance_id: Optional[int] = None
    status: str
    clinical_snapshot: Dict[str, Any] = {}
    patient_summary: Dict[str, Any] = {}
    pdf_path: Optional[str] = None
    pdf_generated_at: Optional[datetime] = None
    authorized_at: datetime
    authorized_by: Optional[int] = None


class DischargePackageDetail(DischargePackageBase):
    id: int
    created_at: datetime
    updated_at: datetime
    pdf_ready: bool = False
    download_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class FinalizePackageRequest(BaseModel):
    notes: Optional[str] = None
