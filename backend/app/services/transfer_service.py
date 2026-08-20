from datetime import datetime, timezone
import logging
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.admission import Admission, AdmissionStatus
from app.models.bed import Bed
from app.models.clinical_decision import (
    ClinicalDecision,
    ClinicalDecisionStatus,
    ClinicalDecisionType,
    TransferUrgency,
)
from app.models.hospital import Hospital
from app.models.hospital_capacity import HospitalCapacity
from app.models.patient import Patient
from app.models.transfer import Transfer, TransferStatus
from app.models.user import User
from app.models.workflow_event import WorkflowEvent
from app.schemas.transfer import (
    HospitalMatchRead,
    TransferDetailRead,
    TransferSummary,
)
from app.services.distance_service import DistanceService
from app.services.hospital_matching_service import HospitalMatchingService

logger = logging.getLogger(__name__)


class TransferService:
    """
    Orchestration service for transfer case creation, hospital matching,
    and doctor receiving-hospital selection.
    """

    def __init__(self, db: Session):
        self.db = db
        self.matching_service = HospitalMatchingService(db)
        self.distance_service = DistanceService(mode="local")

    def _get_default_sending_hospital(self) -> Hospital:
        """Resolve the host sending hospital facility."""
        hospital = self.db.query(Hospital).order_by(Hospital.id.asc()).first()
        if not hospital:
            # Fallback if unseeded
            hospital = Hospital(
                name="Metro Multispeciality Medical Center",
                latitude=37.7749,
                longitude=-122.4194,
                specialties=["Cardiology", "Neurology", "Critical Care", "General Surgery"],
                contact_number="+1-415-555-0100",
            )
            self.db.add(hospital)
            self.db.flush()
        return hospital

    def create_or_get_transfer_for_admission(
        self, admission_id: int, requesting_user: Optional[User] = None
    ) -> Transfer:
        """
        Create a new transfer case or return the existing active transfer for an admission.
        Validates clinical eligibility against confirmed clinical decisions.
        """
        admission = self.db.get(Admission, admission_id)
        if not admission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admission not found",
            )

        if admission.status == AdmissionStatus.DISCHARGING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create transfer for a patient whose clinical decision is normal discharge.",
            )

        if admission.status not in (AdmissionStatus.TRANSFER_PENDING, AdmissionStatus.ADMITTED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Admission status '{admission.status.value}' is not eligible for transfer.",
            )

        # Validate confirmed clinical transfer decision
        decision = (
            self.db.query(ClinicalDecision)
            .filter(
                ClinicalDecision.admission_id == admission.id,
                ClinicalDecision.status == ClinicalDecisionStatus.CONFIRMED,
            )
            .order_by(ClinicalDecision.decided_at.desc(), ClinicalDecision.id.desc())
            .first()
        )

        if not decision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A confirmed clinical transfer decision is required before creating a transfer case.",
            )

        if decision.decision_type != ClinicalDecisionType.TRANSFER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Clinical decision is for normal discharge, not transfer.",
            )

        # Check for existing active transfer
        existing_transfer = (
            self.db.query(Transfer)
            .filter(
                Transfer.admission_id == admission.id,
                Transfer.status.notin_([TransferStatus.CANCELLED, TransferStatus.COMPLETED]),
            )
            .order_by(Transfer.id.desc())
            .first()
        )

        if existing_transfer:
            logger.info("Returning existing active transfer %s for admission %s", existing_transfer.id, admission.id)
            return existing_transfer

        # Extract requirements from confirmed clinical decision
        required_specialty = decision.required_specialty or "General Medicine"
        emergency = (decision.transfer_urgency == TransferUrgency.EMERGENCY)
        sending_hospital = self._get_default_sending_hospital()

        # Ensure admission status reflects transfer_pending
        if admission.status != AdmissionStatus.TRANSFER_PENDING:
            admission.status = AdmissionStatus.TRANSFER_PENDING

        transfer = Transfer(
            patient_id=admission.patient_id,
            admission_id=admission.id,
            clinical_decision_id=decision.id,
            sending_hospital_id=sending_hospital.id,
            receiving_hospital_id=None,
            required_specialty=required_specialty,
            emergency=emergency,
            status=TransferStatus.MATCHING,
            requested_by=requesting_user.id if requesting_user else None,
            requested_at=datetime.now(timezone.utc),
        )
        self.db.add(transfer)
        self.db.flush()

        # Emit transfer_matching_started domain event
        event = WorkflowEvent(
            event_type="transfer_matching_started",
            entity_type="transfer",
            entity_id=transfer.id,
            status="pending",
            trusted_provenance=True,
            payload={
                "transfer_id": transfer.id,
                "patient_id": transfer.patient_id,
                "admission_id": transfer.admission_id,
                "clinical_decision_id": decision.id,
                "required_specialty": transfer.required_specialty,
                "emergency": transfer.emergency,
                "status": TransferStatus.MATCHING.value,
            },
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(transfer)

        logger.info("Created transfer %s with matching status for admission %s", transfer.id, admission.id)
        return transfer

    def get_transfer(self, transfer_id: int) -> Transfer:
        transfer = self.db.get(Transfer, transfer_id)
        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer not found",
            )
        return transfer

    def get_matches_for_transfer(self, transfer_id: int) -> List[HospitalMatchRead]:
        """
        Rank suitable receiving hospitals for a transfer case.
        """
        transfer = self.get_transfer(transfer_id)
        return self.matching_service.find_matches_for_transfer(transfer)

    def select_receiving_hospital(
        self, transfer_id: int, hospital_id: int, selecting_user: Optional[User] = None
    ) -> Transfer:
        """
        Doctor selects a receiving facility from the ranked matches.
        Validates facility specialty and capacity, updates status to awaiting_acceptance,
        and emits receiving_hospital_selected event without prematurely decrementing capacity.
        """
        transfer = self.get_transfer(transfer_id)

        if transfer.status not in (TransferStatus.MATCHING, TransferStatus.HOSPITAL_SELECTED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Transfer in status '{transfer.status.value}' cannot select a receiving hospital.",
            )

        hospital = self.db.get(Hospital, hospital_id)
        if not hospital:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected hospital not found",
            )

        if hospital.id == transfer.sending_hospital_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sending hospital cannot be selected as receiving facility.",
            )

        # Validate specialty support
        normalized_specialty = transfer.required_specialty.strip().lower()
        supported_specialties = [s.strip().lower() for s in (hospital.specialties or [])]

        capacity_records = (
            self.db.query(HospitalCapacity)
            .filter(HospitalCapacity.hospital_id == hospital.id)
            .all()
        )
        matching_capacity = next(
            (c for c in capacity_records if c.specialty.strip().lower() == normalized_specialty),
            None
        )

        is_specialty_supported = (
            normalized_specialty in supported_specialties
            or matching_capacity is not None
        )

        if not is_specialty_supported:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Selected hospital does not support the required specialty '{transfer.required_specialty}'.",
            )

        # Validate capacity > 0
        available_beds = matching_capacity.available_beds if matching_capacity else 0
        if available_beds <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Selected hospital currently has 0 available beds for the required specialty.",
            )

        # Update transfer state
        transfer.receiving_hospital_id = hospital.id
        transfer.status = TransferStatus.AWAITING_ACCEPTANCE
        transfer.selected_hospital_at = datetime.now(timezone.utc)

        # Emit receiving_hospital_selected event
        event = WorkflowEvent(
            event_type="receiving_hospital_selected",
            entity_type="transfer",
            entity_id=transfer.id,
            status="pending",
            trusted_provenance=True,
            payload={
                "transfer_id": transfer.id,
                "patient_id": transfer.patient_id,
                "admission_id": transfer.admission_id,
                "hospital_id": hospital.id,
                "hospital_name": hospital.name,
                "required_specialty": transfer.required_specialty,
                "emergency": transfer.emergency,
                "selected_by": selecting_user.id if selecting_user else None,
                "status": TransferStatus.AWAITING_ACCEPTANCE.value,
            },
        )
        self.db.add(event)
        self.db.commit()
        # Auto-prepare and deliver Clinical Transfer Packet immediately
        try:
            from app.services.transfer_packet_service import TransferPacketService
            pkt_svc = TransferPacketService(self.db)
            pkt_svc.prepare_packet(transfer.id)
            pkt_svc.send_packet(transfer.id, sender_user=selecting_user)
        except Exception as e:
            logger.warning("Auto packet preparation encountered: %s", e)

        logger.info(
            "Selected hospital %s for transfer %s. Status updated to awaiting_acceptance and packet dispatched.",
            hospital.name,
            transfer.id,
        )
        return transfer

    def list_transfers(
        self,
        status_filter: Optional[TransferStatus] = None,
        emergency_filter: Optional[bool] = None,
        patient_id: Optional[int] = None,
        admission_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[TransferSummary]:
        """
        List transfer summaries with filters.
        """
        query = self.db.query(Transfer)

        if status_filter:
            query = query.filter(Transfer.status == status_filter)
        if emergency_filter is not None:
            query = query.filter(Transfer.emergency == emergency_filter)
        if patient_id:
            query = query.filter(Transfer.patient_id == patient_id)
        if admission_id:
            query = query.filter(Transfer.admission_id == admission_id)

        transfers = (
            query.order_by(Transfer.requested_at.desc(), Transfer.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        summaries = []
        for t in transfers:
            patient = t.patient or self.db.get(Patient, t.patient_id)
            admission = t.admission or self.db.get(Admission, t.admission_id)
            sending = t.sending_hospital or self.db.get(Hospital, t.sending_hospital_id)
            receiving = (
                (t.receiving_hospital or self.db.get(Hospital, t.receiving_hospital_id))
                if t.receiving_hospital_id
                else None
            )

            summaries.append(
                TransferSummary(
                    id=t.id,
                    patient_id=t.patient_id,
                    patient_name=f"{patient.first_name} {patient.last_name}" if patient else f"Patient #{t.patient_id}",
                    patient_code=patient.patient_code if patient else f"PT-{t.patient_id}",
                    admission_id=t.admission_id,
                    primary_diagnosis=admission.primary_diagnosis if admission else "Unknown",
                    required_specialty=t.required_specialty,
                    emergency=t.emergency,
                    status=t.status,
                    sending_hospital_id=t.sending_hospital_id,
                    sending_hospital_name=sending.name if sending else "Host Hospital",
                    receiving_hospital_id=t.receiving_hospital_id,
                    receiving_hospital_name=receiving.name if receiving else None,
                    requested_at=t.requested_at,
                    selected_hospital_at=t.selected_hospital_at,
                )
            )

        return summaries

    def get_transfer_detail(self, transfer_id: int) -> TransferDetailRead:
        """
        Get full transfer detail with contextual patient and hospital information.
        """
        transfer = self.get_transfer(transfer_id)
        patient = transfer.patient or self.db.get(Patient, transfer.patient_id)
        admission = transfer.admission or self.db.get(Admission, transfer.admission_id)
        decision = transfer.clinical_decision or (
            self.db.get(ClinicalDecision, transfer.clinical_decision_id)
            if transfer.clinical_decision_id
            else None
        )
        sending = transfer.sending_hospital or self.db.get(Hospital, transfer.sending_hospital_id)
        receiving = (
            (transfer.receiving_hospital or self.db.get(Hospital, transfer.receiving_hospital_id))
            if transfer.receiving_hospital_id
            else None
        )
        requester = (
            (transfer.requester or self.db.get(User, transfer.requested_by))
            if transfer.requested_by
            else None
        )

        bed = self.db.get(Bed, admission.bed_id) if admission and admission.bed_id else None

        # Calculate receiving hospital capacity & distance if selected
        receiving_beds = None
        receiving_distance = None
        if receiving and sending:
            receiving_distance = self.distance_service.calculate_distance_km(
                (sending.latitude, sending.longitude),
                (receiving.latitude, receiving.longitude),
            )
            cap = (
                self.db.query(HospitalCapacity)
                .filter(
                    HospitalCapacity.hospital_id == receiving.id,
                )
                .all()
            )
            matching_cap = next(
                (c for c in cap if c.specialty.strip().lower() == transfer.required_specialty.strip().lower()),
                None
            )
            receiving_beds = matching_cap.available_beds if matching_cap else None

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
            patient_name=f"{patient.first_name} {patient.last_name}" if patient else f"Patient #{transfer.patient_id}",
            patient_code=patient.patient_code if patient else f"PT-{transfer.patient_id}",
            date_of_birth=patient.date_of_birth.isoformat() if patient and patient.date_of_birth else None,
            gender=patient.gender if patient else None,
            primary_diagnosis=admission.primary_diagnosis if admission else "Unknown",
            ward=bed.ward if bed else None,
            bed_number=bed.bed_number if bed else None,
            clinical_reason=decision.reason if decision else None,
            clinical_notes=decision.notes if decision else None,
            sending_hospital_name=sending.name if sending else "Host Hospital",
            sending_hospital_contact=sending.contact_number if sending else None,
            receiving_hospital_name=receiving.name if receiving else None,
            receiving_hospital_contact=receiving.contact_number if receiving else None,
            receiving_hospital_available_beds=receiving_beds,
            receiving_hospital_distance_km=receiving_distance,
            requested_by_name=requester.name if requester else None,
        )
