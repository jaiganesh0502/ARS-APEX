import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user_stub
from app.api.dependencies.database import get_db
from app.models.user import User
from app.schemas.transfer import TransferDetailRead, TransferSummary
from app.services.receiving_transfer_service import ReceivingTransferService

router = APIRouter(prefix="/receiving", tags=["Receiving Hospital"])
logger = logging.getLogger(__name__)


@router.get("/transfers", response_model=List[TransferSummary])
def get_incoming_transfers(
    hospital_id: Optional[int] = Query(None, description="Receiving hospital ID"),
    status: Optional[str] = Query(None, description="Transfer status filter (e.g. awaiting_acceptance)"),
    emergency: Optional[bool] = Query(None, description="Emergency transfer filter"),
    specialty: Optional[str] = Query(None, description="Specialty filter"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_stub),
):
    """
    Retrieve incoming transfer queue for receiving hospital review.
    """
    return ReceivingTransferService(db).list_incoming_transfers(
        hospital_id=hospital_id,
        status_filter=status,
        emergency=emergency,
        specialty=specialty,
        skip=skip,
        limit=limit,
    )


@router.get("/transfers/{transfer_id}", response_model=TransferDetailRead)
def get_incoming_transfer_detail(
    transfer_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_stub),
):
    """
    Retrieve incoming transfer detail, marking the clinical packet as viewed.
    """
    return ReceivingTransferService(db).get_incoming_transfer_detail(
        transfer_id=transfer_id,
        mark_viewed=True,
    )
