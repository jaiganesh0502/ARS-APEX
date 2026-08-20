from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.billing_clearance import BillingStatus


class BillingClearanceBase(BaseModel):
    patient_id: int
    admission_id: int
    transfer_id: Optional[int] = None
    discharge_report_id: Optional[int] = None
    status: BillingStatus = BillingStatus.PENDING
    total_amount: Optional[float] = None
    amount_paid: Optional[float] = None
    outstanding_amount: Optional[float] = None
    clearance_reference: Optional[str] = None
    deferred: bool = False
    notes: Optional[str] = None


class BillingClearanceCreatePayload(BaseModel):
    patient_id: int
    admission_id: int
    transfer_id: Optional[int] = None
    discharge_report_id: Optional[int] = None
    total_amount: Optional[float] = None
    amount_paid: Optional[float] = None
    outstanding_amount: Optional[float] = None
    notes: Optional[str] = None


class BillingClearanceConfirmPayload(BaseModel):
    clearance_reference: str
    notes: Optional[str] = None


class BillingFinalizePayload(BaseModel):
    event_id: Optional[int] = None
    notes: Optional[str] = None


class BillingClearanceRead(BillingClearanceBase):
    id: int
    confirmed_by: Optional[int] = None
    confirmed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BillingClearanceDetailRead(BillingClearanceRead):
    patient_name: Optional[str] = None
    patient_code: Optional[str] = None
    primary_diagnosis: Optional[str] = None
    bed_number: Optional[str] = None
    ward: Optional[str] = None
    confirmed_by_name: Optional[str] = None
    report_status: Optional[str] = None
    transfer_status: Optional[str] = None
