from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.models.notification import Notification, NotificationStatus
from app.schemas.notification import NotificationDetail, NotificationListResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    recipient_reference: Optional[str] = Query(None, description="Filter by recipient code/reference"),
    recipient_type: Optional[str] = Query(None, description="Filter by recipient type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """
    Lists in-app notifications and unread counts for patient/staff communication simulation.
    """
    query = db.query(Notification)

    if recipient_reference:
        query = query.filter(Notification.recipient_reference == recipient_reference)
    if recipient_type:
        query = query.filter(Notification.recipient_type == recipient_type)
    if status:
        query = query.filter(Notification.status == status)

    total = query.count()
    unread_count = (
        db.query(Notification)
        .filter(Notification.status != NotificationStatus.READ)
        .count()
    )

    items = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()

    return NotificationListResponse(
        items=items,
        total=total,
        unread_count=unread_count,
    )


@router.post("/{notification_id}/read", response_model=NotificationDetail)
def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
):
    """
    Marks a notification as read by the recipient.
    """
    notif = db.get(Notification, notification_id)
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notif.status = NotificationStatus.READ
    db.commit()
    db.refresh(notif)
    return notif
