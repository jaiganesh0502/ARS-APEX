import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_doctor, require_staff, require_superintendent
from app.models.transfer import Transfer, TransferStatus
from app.models.user import User
from app.schemas.transfer import (
    HospitalMatchRead,
    HospitalSelectPayload,
    TransferCreate,
    TransferDetailRead,
    TransferRead,
    TransferSummary,
    TransferUpdateStatus,
)
from app.schemas.transfer_packet import TransferPacketRead
from app.schemas.transfer_decision import TransferAcceptPayload, TransferRejectPayload
from app.schemas.ambulance_dispatch import AmbulanceDispatchRead
from app.services.transfer_service import TransferService
from app.services.transfer_packet_service import TransferPacketService
from app.services.receiving_transfer_service import ReceivingTransferService
from app.services.ambulance_dispatch_service import AmbulanceDispatchService

router = APIRouter(prefix="/transfers", tags=["Transfers"])
logger = logging.getLogger(__name__)


@router.get("", response_model=List[TransferSummary])
def list_transfers(
    status: Optional[TransferStatus] = Query(None, description="Filter by transfer status"),
    emergency: Optional[bool] = Query(None, description="Filter by emergency urgency"),
    patient_id: Optional[int] = Query(None, description="Filter by patient ID"),
    admission_id: Optional[int] = Query(None, description="Filter by admission ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_staff),
):
    """
    List transfers with filtering by status and emergency urgency.
    """
    return TransferService(db).list_transfers(
        status_filter=status,
        emergency_filter=emergency,
        patient_id=patient_id,
        admission_id=admission_id,
        skip=skip,
        limit=limit,
    )


@router.get("/{transfer_id}", response_model=TransferDetailRead)
def get_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_staff),
):
    """
    Retrieve full transfer details including patient, admission, and facility context.
    """
    return ReceivingTransferService(db).get_incoming_transfer_detail(transfer_id=transfer_id, mark_viewed=False)


@router.get("/{transfer_id}/matches", response_model=List[HospitalMatchRead])
def get_transfer_hospital_matches(
    transfer_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_staff),
):
    """
    Compute and return deterministic, explainable ranked partner hospital matches
    for a transfer case based on Required Specialty, Capacity, and Distance.
    """
    return TransferService(db).get_matches_for_transfer(transfer_id)


@router.post("/{transfer_id}/select-hospital", response_model=TransferRead)
def select_receiving_hospital(
    transfer_id: int,
    payload: HospitalSelectPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    """
    Doctor selects a receiving hospital for the transfer case.
    Transitions status to 'awaiting_acceptance' and emits receiving_hospital_selected.
    """
    try:
        return TransferService(db).select_receiving_hospital(
            transfer_id=transfer_id,
            hospital_id=payload.hospital_id,
            selecting_user=current_user,
        )
    except HTTPException:
        raise
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Unable to select receiving hospital for transfer %s", transfer_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to select receiving hospital",
        ) from error


@router.post("/{transfer_id}/packet", response_model=TransferPacketRead)
def prepare_transfer_packet(
    transfer_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_staff),
):
    """
    Assemble and persist a structured clinical transfer packet for the selected receiving facility.
    """
    try:
        return TransferPacketService(db).prepare_packet(transfer_id)
    except HTTPException:
        raise
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Unable to prepare transfer packet for %s", transfer_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to prepare transfer packet",
        ) from error


@router.get("/{transfer_id}/packet", response_model=TransferPacketRead)
def get_transfer_packet(
    transfer_id: int,
    mark_viewed: bool = Query(False, description="Whether to mark sent packet as viewed"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_staff),
):
    """
    Retrieve the structured transfer packet for the transfer case.
    """
    return TransferPacketService(db).get_packet(transfer_id, mark_viewed=mark_viewed)


@router.post("/{transfer_id}/packet/send", response_model=TransferPacketRead)
def send_transfer_packet(
    transfer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """
    Simulate secure delivery into the receiving hospital's application queue.
    Transitions packet status to 'sent' and emits 'transfer_packet_sent'.
    """
    try:
        return TransferPacketService(db).send_packet(transfer_id, sender_user=current_user)
    except HTTPException:
        raise
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Unable to send transfer packet for %s", transfer_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to send transfer packet",
        ) from error


@router.post("/{transfer_id}/accept", response_model=TransferRead)
def accept_transfer(
    transfer_id: int,
    payload: Optional[TransferAcceptPayload] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superintendent),
):
    """
    Receiving hospital accepts the transfer request, reserves one bed slot transactionally,
    and updates transfer status to 'accepted'. Idempotent (does not double decrement).
    """
    try:
        return ReceivingTransferService(db).accept_transfer(
            transfer_id=transfer_id,
            notes=payload.notes if payload else None,
            decided_by_user=current_user,
        )
    except HTTPException:
        raise
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Unable to accept transfer %s", transfer_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to accept transfer",
        ) from error


@router.post("/{transfer_id}/reject", response_model=TransferRead)
def reject_transfer(
    transfer_id: int,
    payload: TransferRejectPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superintendent),
):
    """
    Receiving hospital rejects the transfer request with mandatory justification.
    Does not decrement bed capacity.
    """
    try:
        return ReceivingTransferService(db).reject_transfer(
            transfer_id=transfer_id,
            reason=payload.reason,
            decided_by_user=current_user,
        )
    except HTTPException:
        raise
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Unable to reject transfer %s", transfer_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to reject transfer",
        ) from error


@router.post("/{transfer_id}/rematch", response_model=TransferRead)
def rematch_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """
    Re-open a rejected transfer case for sending-physician hospital re-matching.
    Preserves audit history.
    """
    try:
        return ReceivingTransferService(db).rematch_transfer(
            transfer_id=transfer_id,
            user=current_user,
        )
    except HTTPException:
        raise
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Unable to rematch transfer %s", transfer_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to rematch transfer",
        ) from error


@router.post("", response_model=TransferRead, status_code=status.HTTP_201_CREATED)
def create_transfer_direct(
    transfer_in: TransferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    """
    Direct creation of a transfer case. Restricted to Doctors.
    """
    try:
        return TransferService(db).create_or_get_transfer_for_admission(
            admission_id=transfer_in.admission_id,
            requesting_user=current_user,
        )
    except HTTPException:
        raise
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Unable to create transfer")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create transfer",
        ) from error


@router.post("/{transfer_id}/ambulance/dispatch", response_model=AmbulanceDispatchRead)
def dispatch_ambulance_for_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superintendent),
):
    """
    Dispatch an ambulance for an accepted transfer case.
    Restricted to Medical Superintendent / Operational Admins.
    """
    try:
        return AmbulanceDispatchService(db).dispatch_ambulance(
            transfer_id=transfer_id,
            requesting_user=current_user,
        )
    except HTTPException:
        raise
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Unable to dispatch ambulance for transfer %s", transfer_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to dispatch ambulance",
        ) from error


@router.get("/{transfer_id}/ambulance", response_model=Optional[AmbulanceDispatchRead])
def get_transfer_ambulance_dispatch(
    transfer_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_staff),
):
    """
    Retrieve current ambulance dispatch tracking data for a transfer case.
    """
    return AmbulanceDispatchService(db).get_dispatch_for_transfer(transfer_id)


@router.patch("/{transfer_id}/status", response_model=TransferRead)
def update_transfer_status(
    transfer_id: int,
    update_in: TransferUpdateStatus,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_superintendent),
):
    transfer = db.query(Transfer).filter(Transfer.id == transfer_id).first()
    if not transfer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer not found")

    transfer.status = update_in.status
    if update_in.receiving_hospital_id:
        transfer.receiving_hospital_id = update_in.receiving_hospital_id

    db.commit()
    db.refresh(transfer)
    return transfer
