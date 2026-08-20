from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.ambulance_dispatch import AmbulanceStatus


class AmbulanceDispatchBase(BaseModel):
    transfer_id: int
    dispatch_reference: str
    status: AmbulanceStatus = AmbulanceStatus.REQUESTED
    pickup_name: str
    pickup_latitude: float
    pickup_longitude: float
    destination_name: str
    destination_latitude: float
    destination_longitude: float
    distance_km: float
    estimated_duration_minutes: int
    current_eta_minutes: int
    vehicle_number: Optional[str] = None
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    cancellation_reason: Optional[str] = None


class AmbulanceDispatchRead(AmbulanceDispatchBase):
    id: int
    requested_at: datetime
    en_route_at: Optional[datetime] = None
    arrived_pickup_at: Optional[datetime] = None
    patient_onboard_at: Optional[datetime] = None
    departed_pickup_at: Optional[datetime] = None
    arrived_destination_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AmbulanceDispatchDetailRead(AmbulanceDispatchRead):
    patient_id: int
    patient_name: str
    patient_code: str
    primary_diagnosis: str
    required_specialty: str
    emergency: bool
    transfer_status: str


class AmbulanceDispatchSummaryRead(BaseModel):
    id: int
    transfer_id: int
    dispatch_reference: str
    status: AmbulanceStatus
    patient_name: str
    patient_code: str
    primary_diagnosis: str
    required_specialty: str
    emergency: bool
    pickup_name: str
    destination_name: str
    distance_km: float
    current_eta_minutes: int
    vehicle_number: Optional[str] = None
    requested_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AmbulanceStatusUpdatePayload(BaseModel):
    status: AmbulanceStatus


# Backwards compatibility aliases
AmbulanceDispatchUpdateStatus = AmbulanceStatusUpdatePayload


class AmbulanceDispatchCreate(BaseModel):
    transfer_id: int
    pickup_name: Optional[str] = None
    destination_name: Optional[str] = None


class AmbulanceCancelPayload(BaseModel):
    reason: str = Field(..., min_length=3, description="Mandatory operational or clinical cancellation reason")


class AmbulanceDashboardCounts(BaseModel):
    requested: int
    en_route: int
    at_pickup: int
    in_transit: int
    completed: int
    total: int
