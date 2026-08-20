import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Integer,
    String,
    Text,
)

from app.db.session import Base


class NotificationChannel(str, enum.Enum):
    IN_APP = "in_app"
    SIMULATED_EMAIL = "simulated_email"
    SIMULATED_SMS = "simulated_sms"


class NotificationType(str, enum.Enum):
    DISCHARGE_PACKAGE_READY = "discharge_package_ready"
    TRANSFER_UPDATE = "transfer_update"
    AMBULANCE_DISPATCHED = "ambulance_dispatched"
    TRANSFER_COMPLETED = "transfer_completed"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    recipient_type = Column(String(50), nullable=False, default="patient", index=True)
    recipient_reference = Column(String(100), nullable=False, index=True)

    channel = Column(
        Enum(
            NotificationChannel,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
            name="notification_channel_enum",
        ),
        default=NotificationChannel.IN_APP,
        nullable=False,
        index=True,
    )

    notification_type = Column(
        Enum(
            NotificationType,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
            name="notification_type_enum",
        ),
        default=NotificationType.DISCHARGE_PACKAGE_READY,
        nullable=False,
        index=True,
    )

    status = Column(
        Enum(
            NotificationStatus,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
            name="notification_status_enum",
        ),
        default=NotificationStatus.DELIVERED,
        nullable=False,
        index=True,
    )

    subject = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)

    related_entity_type = Column(String(50), nullable=True, index=True)
    related_entity_id = Column(Integer, nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    sent_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
