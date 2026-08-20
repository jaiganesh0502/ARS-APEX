from datetime import datetime, timezone
import logging
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.admission import Admission
from app.models.ambulance_dispatch import AmbulanceDispatch
from app.models.hospital import Hospital
from app.models.hospital_capacity import HospitalCapacity
from app.models.patient import Patient
from app.models.transfer import Transfer, TransferStatus
from app.models.transfer_decision import TransferDecision, TransferDecisionType
from app.models.transfer_packet import TransferPacket, TransferPacketStatus
from app.models.user import User
from app.models.workflow_event import WorkflowEvent
from app.schemas.transfer import TransferDetailRead, TransferSummary
from app.services.transfer_packet_service import TransferPacketService

logger = logging.getLogger(__name__)


class ReceivingTransferService:
    """
    Manages receiving hospital queues, packet reviews, bed reservations,
    and acceptance / rejection decisions.
    """

    def __init__(self, db: Session):
        self.db = db
        self.packet_service = TransferPacketService(db)

    def list_incoming_transfers(
        self,
        hospital_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        emergency: Optional[bool] = None,
        specialty: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[TransferSummary]:
        """
        List transfer requests directed to receiving hospitals.
        """
        query = self.db.query(Transfer).filter(Transfer.receiving_hospital_id.isnot(None))

        if hospital_id is not None:
            query = query.filter(Transfer.receiving_hospital_id == hospital_id)

        if status_filter:
            try:
                target_status = TransferStatus(status_filter)
                query = query.filter(Transfer.status == target_status)
            except ValueError:
                pass

        if emergency is not None:
            query = query.filter(Transfer.emergency == emergency)

        if specialty:
            query = query.filter(Transfer.required_specialty == specialty)

        transfers = (
            query.order_by(Transfer.emergency.desc(), Transfer.requested_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        results = []
        for t in transfers:
            patient = self.db.get(Patient, t.patient_id)
            admission = self.db.get(Admission, t.admission_id)
            sending_hospital = self.db.get(Hospital, t.sending_hospital_id)
            receiving_hospital = self.db.get(Hospital, t.receiving_hospital_id) if t.receiving_hospital_id else None

            results.append(
                TransferSummary(
                    id=t.id,
                    patient_id=t.patient_id,
                    patient_name=f"{patient.first_name} {patient.last_name}" if patient else "Unknown Patient",
                    patient_code=patient.patient_code if patient else "UNKNOWN",
                    admission_id=t.admission_id,
                    primary_diagnosis=admission.primary_diagnosis if admission else "Under Review",
                    required_specialty=t.required_specialty,
                    emergency=t.emergency,
                    status=t.status,
                    sending_hospital_id=t.sending_hospital_id,
                    sending_hospital_name=sending_hospital.name if sending_hospital else "Unknown Hospital",
                    receiving_hospital_id=t.receiving_hospital_id,
                    receiving_hospital_name=receiving_hospital.name if receiving_hospital else None,
                    requested_at=t.requested_at,
                    selected_hospital_at=t.selected_hospital_at,
                )
            )

        return results

    def get_incoming_transfer_detail(self, transfer_id: int, mark_viewed: bool = True) -> TransferDetailRead:
        """
        Get full receiving transfer detail, marking transfer packet as viewed.
        """
        transfer = self.db.get(Transfer, transfer_id)
        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer not found",
            )

        # Mark packet viewed if it was sent
        packet = None
        if transfer.receiving_hospital_id:
            try:
                packet = self.packet_service.get_packet(transfer.id, mark_viewed=mark_viewed)
            except Exception as e:
                logger.warning("Could not load packet for transfer %s: %s", transfer.id, e)

        # Load latest decision
        latest_decision = (
            self.db.query(TransferDecision)
            .filter(TransferDecision.transfer_id == transfer.id)
            .order_by(TransferDecision.id.desc())
            .first()
        )

        patient = self.db.get(Patient, transfer.patient_id)
        admission = self.db.get(Admission, transfer.admission_id)
        sending_hospital = self.db.get(Hospital, transfer.sending_hospital_id)
        receiving_hospital = self.db.get(Hospital, transfer.receiving_hospital_id) if transfer.receiving_hospital_id else None
        requester = self.db.get(User, transfer.requested_by) if transfer.requested_by else None

        bed = admission.bed if admission else None

        # Check capacity at receiving hospital
        available_beds = None
        if receiving_hospital:
            cap = (
                self.db.query(HospitalCapacity)
                .filter(
                    HospitalCapacity.hospital_id == receiving_hospital.id,
                    HospitalCapacity.specialty == transfer.required_specialty,
                )
                .first()
            )
            if cap:
                available_beds = cap.available_beds

        # Check latest ambulance dispatch
        dispatch = (
            self.db.query(AmbulanceDispatch)
            .filter(AmbulanceDispatch.transfer_id == transfer.id)
            .order_by(AmbulanceDispatch.id.desc())
            .first()
        )

        return TransferDetailRead(
            id=transfer.id,
            patient_id=transfer.patient_id,
            admission_id=transfer.admission_id,
            clinical_decision_id=transfer.clinical_decision_id,
            sending_hospital_id=transfer.sending_hospital_id,
            receiving_hospital_id=transfer.receiving_hospital_id,
            required_specialty=transfer.required_specialty,
            emergency=transfer.emergency,
            status=transfer.status,
            requested_by=transfer.requested_by,
            requested_at=transfer.requested_at,
            selected_hospital_at=transfer.selected_hospital_at,
            accepted_at=transfer.accepted_at,
            rejected_at=transfer.rejected_at,
            completed_at=transfer.completed_at,
            created_at=transfer.created_at,
            updated_at=transfer.updated_at,
            patient_name=f"{patient.first_name} {patient.last_name}" if patient else "Unknown",
            patient_code=patient.patient_code if patient else "UNKNOWN",
            date_of_birth=patient.date_of_birth.isoformat() if patient and patient.date_of_birth else None,
            gender=patient.gender if patient else None,
            primary_diagnosis=admission.primary_diagnosis if admission else "Under Review",
            ward=bed.ward if bed else None,
            bed_number=bed.bed_number if bed else None,
            clinical_reason=transfer.clinical_decision.reason if transfer.clinical_decision else None,
            clinical_notes=transfer.clinical_decision.notes if transfer.clinical_decision else None,
            sending_hospital_name=sending_hospital.name if sending_hospital else "Unknown Hospital",
            sending_hospital_contact=sending_hospital.contact_number if sending_hospital else None,
            receiving_hospital_name=receiving_hospital.name if receiving_hospital else None,
            receiving_hospital_contact=receiving_hospital.contact_number if receiving_hospital else None,
            receiving_hospital_available_beds=available_beds,
            requested_by_name=requester.name if requester else None,
            packet_id=packet.id if packet else None,
            packet_status=packet.status.value if packet else None,
            rejection_reason=latest_decision.reason if latest_decision and latest_decision.decision == TransferDecisionType.REJECTED else None,
            acceptance_notes=latest_decision.reason if latest_decision and latest_decision.decision == TransferDecisionType.ACCEPTED else None,
            latest_decision=latest_decision.decision.value if latest_decision else None,
            ambulance_dispatch_id=dispatch.id if dispatch else None,
            ambulance_status=dispatch.status.value if dispatch else None,
            ambulance_reference=dispatch.dispatch_reference if dispatch else None,
            ambulance_vehicle=dispatch.vehicle_number if dispatch else None,
            ambulance_eta_minutes=dispatch.current_eta_minutes if dispatch else None,
        )

    def accept_transfer(
        self,
        transfer_id: int,
        notes: Optional[str] = None,
        decided_by_user: Optional[User] = None,
    ) -> Transfer:
        """
        Atomically accept transfer, reserve bed capacity at receiving facility,
        and update transfer status to accepted.
        Guarantees idempotency (double acceptance does not decrement capacity twice).
        """
        transfer = self.db.get(Transfer, transfer_id)
        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer not found",
            )

        # Idempotency check: if already accepted, return without re-decrementing
        if transfer.status == TransferStatus.ACCEPTED:
            logger.info("Transfer %s is already accepted; returning existing state.", transfer_id)
            return transfer

        if transfer.status not in (TransferStatus.AWAITING_ACCEPTANCE, TransferStatus.HOSPITAL_SELECTED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transfer cannot be accepted from status: {transfer.status.value}",
            )

        if not transfer.receiving_hospital_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No receiving hospital has been selected for this transfer.",
            )

        # Fetch and lock capacity row in database transaction
        capacity = (
            self.db.query(HospitalCapacity)
            .filter(
                HospitalCapacity.hospital_id == transfer.receiving_hospital_id,
                HospitalCapacity.specialty == transfer.required_specialty,
            )
            .with_for_update()
            .first()
        )

        if not capacity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Receiving hospital does not have configured capacity for {transfer.required_specialty}.",
            )

        if capacity.available_beds <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No capacity remains for the required specialty.",
            )

        # Decrement capacity exactly once
        capacity.available_beds = capacity.available_beds - 1

        # Update Transfer
        transfer.status = TransferStatus.ACCEPTED
        transfer.accepted_at = datetime.now(timezone.utc)

        # Create TransferDecision record
        decision = TransferDecision(
            transfer_id=transfer.id,
            hospital_id=transfer.receiving_hospital_id,
            decision=TransferDecisionType.ACCEPTED,
            reason=notes,
            decided_by=decided_by_user.id if decided_by_user else None,
            decided_at=datetime.now(timezone.utc),
        )
        self.db.add(decision)

        # Emit audit event
        event = WorkflowEvent(
            event_type="receiving_hospital_accepted",
            entity_type="transfer",
            entity_id=transfer.id,
            status="pending",
            trusted_provenance=True,
            payload={
                "transfer_id": transfer.id,
                "patient_id": transfer.patient_id,
                "hospital_id": transfer.receiving_hospital_id,
                "required_specialty": transfer.required_specialty,
                "remaining_available_beds": capacity.available_beds,
                "notes": notes,
                "decided_by": decided_by_user.id if decided_by_user else None,
                "accepted_at": transfer.accepted_at.isoformat(),
            },
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(transfer)

        logger.info(
            "Transfer %s accepted by hospital %s. Remaining beds for %s: %s",
            transfer.id,
            transfer.receiving_hospital_id,
            transfer.required_specialty,
            capacity.available_beds,
        )
        return transfer

    def reject_transfer(
        self,
        transfer_id: int,
        reason: str,
        decided_by_user: Optional[User] = None,
    ) -> Transfer:
        """
        Reject transfer request. Does not alter bed capacity.
        """
        transfer = self.db.get(Transfer, transfer_id)
        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer not found",
            )

        if transfer.status not in (TransferStatus.AWAITING_ACCEPTANCE, TransferStatus.HOSPITAL_SELECTED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transfer cannot be rejected from status: {transfer.status.value}",
            )

        if not reason or not reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid rejection reason is required.",
            )

        transfer.status = TransferStatus.REJECTED
        transfer.rejected_at = datetime.now(timezone.utc)

        decision = TransferDecision(
            transfer_id=transfer.id,
            hospital_id=transfer.receiving_hospital_id or transfer.sending_hospital_id,
            decision=TransferDecisionType.REJECTED,
            reason=reason.strip(),
            decided_by=decided_by_user.id if decided_by_user else None,
            decided_at=datetime.now(timezone.utc),
        )
        self.db.add(decision)

        event = WorkflowEvent(
            event_type="receiving_hospital_rejected",
            entity_type="transfer",
            entity_id=transfer.id,
            status="pending",
            trusted_provenance=True,
            payload={
                "transfer_id": transfer.id,
                "patient_id": transfer.patient_id,
                "hospital_id": transfer.receiving_hospital_id,
                "reason": reason.strip(),
                "decided_by": decided_by_user.id if decided_by_user else None,
                "rejected_at": transfer.rejected_at.isoformat(),
            },
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(transfer)

        logger.info("Transfer %s rejected by receiving hospital: %s", transfer.id, reason)
        return transfer

    def rematch_transfer(self, transfer_id: int, user: Optional[User] = None) -> Transfer:
        """
        Re-open a rejected transfer case for hospital matching.
        Preserves historical rejection decisions for auditability.
        """
        transfer = self.db.get(Transfer, transfer_id)
        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer not found",
            )

        if transfer.status != TransferStatus.REJECTED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only rejected transfer cases can be returned to matching.",
            )

        transfer.status = TransferStatus.MATCHING
        transfer.receiving_hospital_id = None
        transfer.selected_hospital_at = None

        event = WorkflowEvent(
            event_type="transfer_matching_started",
            entity_type="transfer",
            entity_id=transfer.id,
            status="pending",
            trusted_provenance=True,
            payload={
                "transfer_id": transfer.id,
                "patient_id": transfer.patient_id,
                "required_specialty": transfer.required_specialty,
                "rematch": True,
                "reopened_by": user.id if user else None,
            },
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(transfer)

        logger.info("Transfer %s returned to matching status", transfer.id)
        return transfer
