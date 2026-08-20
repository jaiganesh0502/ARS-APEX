from datetime import datetime, timezone
import enum
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from app.db.session import Base


class AmbulanceStatus(str, enum.Enum):
    REQUESTED = "requested"
    EN_ROUTE = "en_route"
    ARRIVED_PICKUP = "arrived_pickup"
    PATIENT_ONBOARD = "patient_onboard"
    IN_TRANSIT = "in_transit"
    ARRIVED_DESTINATION = "arrived_destination"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AmbulanceDispatch(Base):
    __tablename__ = "ambulance_dispatches"

    id = Column(Integer, primary_key=True, index=True)
    transfer_id = Column(Integer, ForeignKey("transfers.id", ondelete="CASCADE"), nullable=False, index=True)
    dispatch_reference = Column(String(64), unique=True, index=True, nullable=False)
    status = Column(
        Enum(AmbulanceStatus, name="ambulance_status_enum", native_enum=False),
        default=AmbulanceStatus.REQUESTED,
        nullable=False,
        index=True
    )
    pickup_name = Column(String(255), nullable=False)
    pickup_latitude = Column(Float, nullable=False)
    pickup_longitude = Column(Float, nullable=False)

    destination_name = Column(String(255), nullable=False)
    destination_latitude = Column(Float, nullable=False)
    destination_longitude = Column(Float, nullable=False)

    distance_km = Column(Float, nullable=False, default=0.0)
    estimated_duration_minutes = Column(Integer, nullable=False, default=15)
    current_eta_minutes = Column(Integer, nullable=False, default=15)

    vehicle_number = Column(String(50), nullable=True)
    driver_name = Column(String(100), nullable=True)
    driver_phone = Column(String(50), nullable=True)
    cancellation_reason = Column(Text, nullable=True)

    requested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    en_route_at = Column(DateTime(timezone=True), nullable=True)
    arrived_pickup_at = Column(DateTime(timezone=True), nullable=True)
    patient_onboard_at = Column(DateTime(timezone=True), nullable=True)
    departed_pickup_at = Column(DateTime(timezone=True), nullable=True)
    arrived_destination_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    transfer = relationship("Transfer", back_populates="ambulance_dispatches")
