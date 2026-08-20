from datetime import datetime, timezone
import logging
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.admission import Admission, AdmissionStatus
from app.models.ambulance_dispatch import AmbulanceDispatch, AmbulanceStatus
from app.models.bed import Bed, BedStatus
from app.models.hospital import Hospital
from app.models.patient import Patient
from app.models.transfer import Transfer, TransferStatus
from app.models.user import User
from app.models.workflow_event import WorkflowEvent
from app.schemas.ambulance_dispatch import (
    AmbulanceDashboardCounts,
    AmbulanceDispatchDetailRead,
    AmbulanceDispatchSummaryRead,
)
from app.services.distance_service import DistanceService
from app.services.eta_service import ETAService

logger = logging.getLogger(__name__)

SYNTHETIC_VEHICLES = [
    "TN-DEMO-101 (Synthetic)",
    "TN-DEMO-102 (Synthetic)",
    "TN-DEMO-103 (Synthetic)",
    "TN-DEMO-104 (Synthetic)",
]

SYNTHETIC_DRIVERS = [
    {"name": "Rajesh Sharma", "phone": "+91-98765-00101"},
    {"name": "Manoj Verma", "phone": "+91-98765-00102"},
    {"name": "Suresh Kumar", "phone": "+91-98765-00103"},
    {"name": "Amit Patel", "phone": "+91-98765-00104"},
]

VALID_TRANSITIONS = {
    AmbulanceStatus.REQUESTED: [AmbulanceStatus.EN_ROUTE, AmbulanceStatus.CANCELLED],
    AmbulanceStatus.EN_ROUTE: [AmbulanceStatus.ARRIVED_PICKUP, AmbulanceStatus.CANCELLED],
    AmbulanceStatus.ARRIVED_PICKUP: [AmbulanceStatus.PATIENT_ONBOARD],
    AmbulanceStatus.PATIENT_ONBOARD: [AmbulanceStatus.IN_TRANSIT],
    AmbulanceStatus.IN_TRANSIT: [AmbulanceStatus.ARRIVED_DESTINATION],
    AmbulanceStatus.ARRIVED_DESTINATION: [AmbulanceStatus.COMPLETED],
    AmbulanceStatus.COMPLETED: [],
    AmbulanceStatus.CANCELLED: [],
}


class AmbulanceDispatchService:
    """
    Manages ambulance dispatch lifecycle, state machine transitions,
    ETA calculations, sending bed releases, and transfer synchronizations.
    """

    def __init__(self, db: Session):
        self.db = db
        self.distance_service = DistanceService(mode="local")
        self.eta_service = ETAService(mode="simulation")

    def dispatch_ambulance(self, transfer_id: int, requesting_user: Optional[User] = None) -> AmbulanceDispatch:
        """
        Request ambulance transport for an accepted transfer case.
        Guarantees idempotency (returns existing active dispatch).
        """
        transfer = self.db.get(Transfer, transfer_id)
        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer not found",
            )

        if transfer.status not in (
            TransferStatus.ACCEPTED,
            TransferStatus.AMBULANCE_REQUESTED,
            TransferStatus.IN_TRANSIT,
            TransferStatus.COMPLETED,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ambulance can only be dispatched for accepted transfers. Current status: '{transfer.status.value}'",
            )

        if not transfer.receiving_hospital_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transfer does not have a confirmed receiving hospital.",
            )

        # Return existing active dispatch if one already exists (Idempotency)
        existing_dispatch = (
            self.db.query(AmbulanceDispatch)
            .filter(
                AmbulanceDispatch.transfer_id == transfer.id,
                AmbulanceDispatch.status != AmbulanceStatus.CANCELLED,
            )
            .order_by(AmbulanceDispatch.id.desc())
            .first()
        )
        if existing_dispatch:
            logger.info("Transfer %s already has active dispatch %s", transfer.id, existing_dispatch.id)
            return existing_dispatch

        sending_hosp = self.db.get(Hospital, transfer.sending_hospital_id)
        receiving_hosp = self.db.get(Hospital, transfer.receiving_hospital_id)
        if not sending_hosp or not receiving_hosp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sending or receiving hospital coordinates unavailable.",
            )

        # Calculate distance and simulated ETA
        distance_km = self.distance_service.calculate_distance_km(
            (sending_hosp.latitude, sending_hosp.longitude),
            (receiving_hosp.latitude, receiving_hosp.longitude),
        )
        eta_data = self.eta_service.calculate_initial_eta(
            distance_km=distance_km,
            emergency=transfer.emergency,
        )

        # Assign synthetic vehicle and driver deterministically
        existing_count = (
            self.db.query(AmbulanceDispatch)
            .filter(AmbulanceDispatch.transfer_id == transfer.id)
            .count()
        )
        idx = (transfer.id + existing_count) % len(SYNTHETIC_VEHICLES)
        vehicle = SYNTHETIC_VEHICLES[idx]
        driver = SYNTHETIC_DRIVERS[idx]

        now = datetime.now(timezone.utc)
        seq_suffix = f"-{existing_count + 1}" if existing_count > 0 else ""
        dispatch_ref = f"AMB-{now.strftime('%Y%m%d')}-{transfer.id:04d}{seq_suffix}"

        dispatch = AmbulanceDispatch(
            transfer_id=transfer.id,
            dispatch_reference=dispatch_ref,
            status=AmbulanceStatus.REQUESTED,
            pickup_name=sending_hosp.name,
            pickup_latitude=sending_hosp.latitude,
            pickup_longitude=sending_hosp.longitude,
            destination_name=receiving_hosp.name,
            destination_latitude=receiving_hosp.latitude,
            destination_longitude=receiving_hosp.longitude,
            distance_km=distance_km,
            estimated_duration_minutes=eta_data["estimated_duration_minutes"],
            current_eta_minutes=eta_data["current_eta_minutes"],
            vehicle_number=vehicle,
            driver_name=driver["name"],
            driver_phone=driver["phone"],
            requested_at=now,
        )
        self.db.add(dispatch)

        # Update Transfer status to ambulance_requested
        transfer.status = TransferStatus.AMBULANCE_REQUESTED

        # Emit audit event
        event = WorkflowEvent(
            event_type="ambulance_dispatch_requested",
            entity_type="ambulance_dispatch",
            entity_id=transfer.id,
            status="pending",
            trusted_provenance=True,
            payload={
                "transfer_id": transfer.id,
                "dispatch_reference": dispatch_ref,
                "sending_hospital_id": transfer.sending_hospital_id,
                "receiving_hospital_id": transfer.receiving_hospital_id,
                "distance_km": distance_km,
                "estimated_duration_minutes": eta_data["estimated_duration_minutes"],
                "emergency": transfer.emergency,
                "requested_by": requesting_user.id if requesting_user else None,
                "requested_at": now.isoformat(),
            },
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(dispatch)

        logger.info("Dispatched ambulance %s for transfer %s", dispatch.dispatch_reference, transfer.id)
        return dispatch

    def update_dispatch_status(
        self,
        dispatch_id: int,
        target_status: AmbulanceStatus,
        actor: Optional[User] = None,
    ) -> AmbulanceDispatch:
        """
        Transition ambulance through the strict operational state machine.
        Synchronizes transfer status and triggers sending-bed release on patient departure.
        """
        dispatch = (
            self.db.query(AmbulanceDispatch)
            .populate_existing()
            .with_for_update()
            .filter(AmbulanceDispatch.id == dispatch_id)
            .first()
        )
        if not dispatch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ambulance dispatch not found",
            )

        # Idempotency check: if already at target status, return cleanly
        if dispatch.status == target_status:
            return dispatch

        # Validate allowed state transitions
        allowed = VALID_TRANSITIONS.get(dispatch.status, [])
        if target_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot transition ambulance from '{dispatch.status.value}' to '{target_status.value}'.",
            )

        now = datetime.now(timezone.utc)
        transfer = self.db.get(Transfer, dispatch.transfer_id)
        admission = self.db.get(Admission, transfer.admission_id) if transfer else None

        # Set transition timestamp and update status
        dispatch.status = target_status

        event_name = ""
        if target_status == AmbulanceStatus.EN_ROUTE:
            dispatch.en_route_at = now
            event_name = "ambulance_en_route"
        elif target_status == AmbulanceStatus.ARRIVED_PICKUP:
            dispatch.arrived_pickup_at = now
            event_name = "ambulance_arrived_pickup"
        elif target_status == AmbulanceStatus.PATIENT_ONBOARD:
            dispatch.patient_onboard_at = now
            event_name = "patient_onboarded"
            if transfer:
                transfer.status = TransferStatus.IN_TRANSIT
        elif target_status == AmbulanceStatus.IN_TRANSIT:
            dispatch.departed_pickup_at = now
            event_name = "patient_transfer_started"
            if transfer:
                transfer.status = TransferStatus.IN_TRANSIT

            # PHYSICAL PATIENT DEPARTURE: Trigger sending hospital bed turnover
            if admission and admission.bed_id:
                bed = (
                    self.db.query(Bed)
                    .populate_existing()
                    .with_for_update()
                    .filter(Bed.id == admission.bed_id)
                    .first()
                )
                if bed and bed.status in (BedStatus.OCCUPIED, BedStatus.VACATING):
                    prev_status = bed.status
                    bed.status = BedStatus.CLEANING
                    bed.current_patient_id = None

                    # Emit bed release & turnover events
                    self.db.add(WorkflowEvent(
                        event_type="patient_departed_bed",
                        entity_type="bed",
                        entity_id=bed.id,
                        status="pending",
                        trusted_provenance=True,
                        payload={
                            "bed_id": bed.id,
                            "patient_id": admission.patient_id,
                            "admission_id": admission.id,
                            "transfer_id": transfer.id,
                            "previous_status": prev_status.value,
                            "new_status": BedStatus.CLEANING.value,
                            "timestamp": now.isoformat(),
                        },
                    ))
                    self.db.add(WorkflowEvent(
                        event_type="bed_cleaning_started",
                        entity_type="bed",
                        entity_id=bed.id,
                        status="pending",
                        trusted_provenance=True,
                        payload={
                            "bed_id": bed.id,
                            "previous_status": prev_status.value,
                            "new_status": BedStatus.CLEANING.value,
                            "timestamp": now.isoformat(),
                        },
                    ))

        elif target_status == AmbulanceStatus.ARRIVED_DESTINATION:
            dispatch.arrived_destination_at = now
            event_name = "ambulance_arrived_destination"
        elif target_status == AmbulanceStatus.COMPLETED:
            dispatch.completed_at = now
            event_name = "transfer_completed"
            if transfer:
                transfer.status = TransferStatus.COMPLETED
                transfer.completed_at = now
            if admission:
                admission.status = AdmissionStatus.TRANSFERRED

        # Recalculate remaining simulated ETA
        dispatch.current_eta_minutes = self.eta_service.compute_current_eta(
            status=target_status,
            distance_km=dispatch.distance_km,
            emergency=transfer.emergency if transfer else False,
        )

        if event_name:
            self.db.add(WorkflowEvent(
                event_type=event_name,
                entity_type="ambulance_dispatch",
                entity_id=dispatch.id,
                status="pending",
                trusted_provenance=True,
                payload={
                    "dispatch_id": dispatch.id,
                    "dispatch_reference": dispatch.dispatch_reference,
                    "transfer_id": dispatch.transfer_id,
                    "patient_id": transfer.patient_id if transfer else None,
                    "new_status": target_status.value,
                    "actor_id": actor.id if actor else None,
                    "timestamp": now.isoformat(),
                },
            ))

        self.db.commit()
        self.db.refresh(dispatch)

        logger.info(
            "Ambulance %s transitioned to '%s'. Current ETA: %s mins",
            dispatch.dispatch_reference,
            target_status.value,
            dispatch.current_eta_minutes,
        )
        return dispatch

    def cancel_dispatch(
        self,
        dispatch_id: int,
        reason: str,
        actor: Optional[User] = None,
    ) -> AmbulanceDispatch:
        """
        Cancel an ambulance dispatch before patient boarding.
        Reverts transfer status back to accepted.
        """
        dispatch = self.db.get(AmbulanceDispatch, dispatch_id)
        if not dispatch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ambulance dispatch not found",
            )

        if dispatch.status not in (AmbulanceStatus.REQUESTED, AmbulanceStatus.EN_ROUTE):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot cancel dispatch from status: '{dispatch.status.value}'. Transport is already in progress.",
            )

        if not reason or len(reason.strip()) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid cancellation reason is required (at least 3 characters).",
            )

        now = datetime.now(timezone.utc)
        dispatch.status = AmbulanceStatus.CANCELLED
        dispatch.cancellation_reason = reason.strip()
        dispatch.current_eta_minutes = 0

        transfer = self.db.get(Transfer, dispatch.transfer_id)
        if transfer and transfer.status == TransferStatus.AMBULANCE_REQUESTED:
            transfer.status = TransferStatus.ACCEPTED

        self.db.add(WorkflowEvent(
            event_type="ambulance_dispatch_cancelled",
            entity_type="ambulance_dispatch",
            entity_id=dispatch.id,
            status="pending",
            trusted_provenance=True,
            payload={
                "dispatch_id": dispatch.id,
                "dispatch_reference": dispatch.dispatch_reference,
                "transfer_id": dispatch.transfer_id,
                "reason": reason.strip(),
                "cancelled_by": actor.id if actor else None,
                "timestamp": now.isoformat(),
            },
        ))

        self.db.commit()
        self.db.refresh(dispatch)
        logger.info("Cancelled dispatch %s: %s", dispatch.dispatch_reference, reason)
        return dispatch

    def get_dispatch_for_transfer(self, transfer_id: int) -> Optional[AmbulanceDispatch]:
        """
        Get the latest active or completed dispatch for a transfer case.
        """
        return (
            self.db.query(AmbulanceDispatch)
            .filter(AmbulanceDispatch.transfer_id == transfer_id)
            .order_by(AmbulanceDispatch.id.desc())
            .first()
        )

    def get_dispatch_detail(self, dispatch_id: int) -> AmbulanceDispatchDetailRead:
        """
        Get comprehensive details for a specific dispatch.
        """
        dispatch = self.db.get(AmbulanceDispatch, dispatch_id)
        if not dispatch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ambulance dispatch not found",
            )

        transfer = self.db.get(Transfer, dispatch.transfer_id)
        patient = self.db.get(Patient, transfer.patient_id) if transfer else None
        admission = self.db.get(Admission, transfer.admission_id) if transfer else None

        return AmbulanceDispatchDetailRead(
            id=dispatch.id,
            transfer_id=dispatch.transfer_id,
            dispatch_reference=dispatch.dispatch_reference,
            status=dispatch.status,
            pickup_name=dispatch.pickup_name,
            pickup_latitude=dispatch.pickup_latitude,
            pickup_longitude=dispatch.pickup_longitude,
            destination_name=dispatch.destination_name,
            destination_latitude=dispatch.destination_latitude,
            destination_longitude=dispatch.destination_longitude,
            distance_km=dispatch.distance_km,
            estimated_duration_minutes=dispatch.estimated_duration_minutes,
            current_eta_minutes=dispatch.current_eta_minutes,
            vehicle_number=dispatch.vehicle_number,
            driver_name=dispatch.driver_name,
            driver_phone=dispatch.driver_phone,
            cancellation_reason=dispatch.cancellation_reason,
            requested_at=dispatch.requested_at,
            en_route_at=dispatch.en_route_at,
            arrived_pickup_at=dispatch.arrived_pickup_at,
            patient_onboard_at=dispatch.patient_onboard_at,
            departed_pickup_at=dispatch.departed_pickup_at,
            arrived_destination_at=dispatch.arrived_destination_at,
            completed_at=dispatch.completed_at,
            created_at=dispatch.created_at,
            updated_at=dispatch.updated_at,
            patient_id=patient.id if patient else 0,
            patient_name=f"{patient.first_name} {patient.last_name}" if patient else "Unknown",
            patient_code=patient.patient_code if patient else "UNKNOWN",
            primary_diagnosis=admission.primary_diagnosis if admission else "Under Review",
            required_specialty=transfer.required_specialty if transfer else "General",
            emergency=transfer.emergency if transfer else False,
            transfer_status=transfer.status.value if transfer else "unknown",
        )

    def list_dispatches(
        self,
        status_filter: Optional[str] = None,
        emergency_filter: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[AmbulanceDispatchSummaryRead]:
        """
        List ambulance dispatches with optional status and urgency filters.
        """
        query = self.db.query(AmbulanceDispatch)

        if status_filter:
            try:
                target_status = AmbulanceStatus(status_filter)
                query = query.filter(AmbulanceDispatch.status == target_status)
            except ValueError:
                pass

        dispatches = (
            query.order_by(AmbulanceDispatch.requested_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        results = []
        for d in dispatches:
            transfer = self.db.get(Transfer, d.transfer_id)
            if emergency_filter is not None and transfer and transfer.emergency != emergency_filter:
                continue

            patient = self.db.get(Patient, transfer.patient_id) if transfer else None
            admission = self.db.get(Admission, transfer.admission_id) if transfer else None

            results.append(
                AmbulanceDispatchSummaryRead(
                    id=d.id,
                    transfer_id=d.transfer_id,
                    dispatch_reference=d.dispatch_reference,
                    status=d.status,
                    patient_name=f"{patient.first_name} {patient.last_name}" if patient else "Unknown",
                    patient_code=patient.patient_code if patient else "UNKNOWN",
                    primary_diagnosis=admission.primary_diagnosis if admission else "Under Review",
                    required_specialty=transfer.required_specialty if transfer else "General",
                    emergency=transfer.emergency if transfer else False,
                    pickup_name=d.pickup_name,
                    destination_name=d.destination_name,
                    distance_km=d.distance_km,
                    current_eta_minutes=d.current_eta_minutes,
                    vehicle_number=d.vehicle_number,
                    requested_at=d.requested_at,
                )
            )

        return results

    def get_dashboard_counts(self) -> AmbulanceDashboardCounts:
        """
        Get aggregated operational counts for the ambulance dispatch dashboard.
        """
        requested = self.db.query(AmbulanceDispatch).filter(AmbulanceDispatch.status == AmbulanceStatus.REQUESTED).count()
        en_route = self.db.query(AmbulanceDispatch).filter(AmbulanceDispatch.status == AmbulanceStatus.EN_ROUTE).count()
        at_pickup = (
            self.db.query(AmbulanceDispatch)
            .filter(AmbulanceDispatch.status.in_([AmbulanceStatus.ARRIVED_PICKUP, AmbulanceStatus.PATIENT_ONBOARD]))
            .count()
        )
        in_transit = self.db.query(AmbulanceDispatch).filter(AmbulanceDispatch.status == AmbulanceStatus.IN_TRANSIT).count()
        completed = self.db.query(AmbulanceDispatch).filter(AmbulanceDispatch.status == AmbulanceStatus.COMPLETED).count()
        total = self.db.query(AmbulanceDispatch).filter(AmbulanceDispatch.status != AmbulanceStatus.CANCELLED).count()

        return AmbulanceDashboardCounts(
            requested=requested,
            en_route=en_route,
            at_pickup=at_pickup,
            in_transit=in_transit,
            completed=completed,
            total=total,
        )
