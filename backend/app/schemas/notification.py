from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class NotificationBase(BaseModel):
    recipient_type: str
    recipient_reference: str
    channel: str
    notification_type: str
    status: str
    subject: str
    message: str
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None


class NotificationDetail(NotificationBase):
    id: int
    created_at: datetime
    sent_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    items: List[NotificationDetail]
    total: int
    unread_count: int
