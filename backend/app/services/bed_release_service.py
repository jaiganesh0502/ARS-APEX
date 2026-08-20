from datetime import datetime, timezone
from collections.abc import Callable
from typing import TypeVar

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.admission import Admission, AdmissionStatus
from app.models.bed import Bed, BedStatus
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.user import User, UserRole
from app.models.workflow_event import WorkflowEvent
from app.schemas.bed import BedDetail
from app.services.bed_event_policy import (
    is_valid_bed_transition_event,
    is_valid_report_approval_event,
)
from app.services.bed_query_service import BedQueryService


ResultT = TypeVar("ResultT")


class BedReleaseService:
    """Own the guarded start of the operational bed-turnover workflow."""

    _ALLOWED_ROLES = {
        UserRole.DOCTOR,
        UserRole.WARD_ADMIN,
        UserRole.MEDICAL_SUPERINTENDENT,
    }
    _ACTIVE_ADMISSION_STATUSES = (
        AdmissionStatus.ADMITTED,
        AdmissionStatus.DISCHARGING,
        AdmissionStatus.TRANSFER_PENDING,
    )

    def __init__(self, db: Session):
        self.db = db

    def start_release(self, bed_id: int, actor: User) -> Bed:
        return self._start_release(bed_id, actor, self._detach_bed)

    def start_release_detail(self, bed_id: int, actor: User) -> BedDetail:
        return self._start_release(bed_id, actor, self._bed_detail)

    def patient_departed(self, bed_id: int, actor: User) -> Bed:
        return self._patient_departed(bed_id, actor, self._detach_bed)

    def patient_departed_detail(self, bed_id: int, actor: User) -> BedDetail:
        return self._patient_departed(bed_id, actor, self._bed_detail)

    def cleaning_complete(self, bed_id: int, actor: User) -> Bed:
        return self._cleaning_complete(bed_id, actor, self._detach_bed)

    def cleaning_complete_detail(self, bed_id: int, actor: User) -> BedDetail:
        return self._cleaning_complete(bed_id, actor, self._bed_detail)

    def _start_release(
        self,
        bed_id: int,
        actor: User,
        build_result: Callable[[Bed], ResultT],
    ) -> ResultT:
        mutated = False
        try:
            if not actor or actor.role not in self._ALLOWED_ROLES:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only doctors and ward administrators can start bed release",
                )

            bed = (
                self.db.query(Bed)
                .populate_existing()
                .with_for_update()
                .filter(Bed.id == bed_id)
                .first()
            )
            if bed is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bed not found")
            if bed.status not in {BedStatus.OCCUPIED, BedStatus.VACATING}:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Bed must be occupied before release can start",
                )
            if bed.current_patient_id is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Bed has no current patient assignment",
                )

            admission = self._single_active_owner(bed)
            if admission.status != AdmissionStatus.DISCHARGING:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Admission must be discharging before bed release can start",
                )

            report = (
                self.db.query(DischargeReport)
                .populate_existing()
                .with_for_update()
                .filter(
                    DischargeReport.admission_id == admission.id,
                    DischargeReport.patient_id == bed.current_patient_id,
                )
                .order_by(DischargeReport.id.desc())
                .first()
            )
            if report is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Matching discharge report is required before bed release can start",
                )
            if report.status != DischargeReportStatus.APPROVED:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Discharge report must be approved before bed release can start",
                )

            approval_events = (
                self.db.query(WorkflowEvent)
                .populate_existing()
                .with_for_update()
                .filter(
                    WorkflowEvent.event_type == "report_approved",
                    WorkflowEvent.entity_type == "discharge_report",
                    WorkflowEvent.entity_id == report.id,
                )
                .all()
            )
            if not any(
                is_valid_report_approval_event(self.db, event, report)
                for event in approval_events
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Matching discharge report approval event is required",
                )

            if bed.status == BedStatus.VACATING:
                if not self._has_single_matching_release_event(bed, admission, report):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Vacating bed has inconsistent or ambiguous release history",
                    )
                result = build_result(bed)
                self.db.commit()
                return result

            transitioned = self.db.execute(
                update(Bed)
                .where(
                    Bed.id == bed.id,
                    Bed.status == BedStatus.OCCUPIED,
                    Bed.current_patient_id == bed.current_patient_id,
                )
                .values(status=BedStatus.VACATING)
            ).rowcount
            if transitioned != 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Bed release state changed; refresh and try again",
                )
            mutated = True

            now = datetime.now(timezone.utc)
            self.db.add(WorkflowEvent(
                event_type="bed_release_started",
                entity_type="bed",
                entity_id=bed.id,
                status="pending",
                trusted_provenance=True,
                payload={
                    "bed_id": bed.id,
                    "patient_id": bed.current_patient_id,
                    "admission_id": admission.id,
                    "report_id": report.id,
                    "previous_status": BedStatus.OCCUPIED.value,
                    "new_status": BedStatus.VACATING.value,
                    "timestamp": now.isoformat(),
                    "actor_user_id": actor.id,
                    "actor_name": actor.name,
                    "actor_role": actor.role.value,
                },
            ))
            self.db.flush()
            self.db.refresh(bed)
            result = build_result(bed)
            self.db.commit()
        except HTTPException:
            if mutated:
                self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

        return result

    def _patient_departed(
        self,
        bed_id: int,
        actor: User,
        build_result: Callable[[Bed], ResultT],
    ) -> ResultT:
        mutated = False
        try:
            self._authorize_actor(actor, "confirm patient departure")
            bed = self._locked_bed(bed_id)
            if bed.status != BedStatus.VACATING:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Bed must be vacating before patient departure can be confirmed",
                )
            patient_id = bed.current_patient_id
            if patient_id is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Vacating bed has no current patient assignment",
                )

            admission = self._single_active_owner(bed)
            if admission.status != AdmissionStatus.DISCHARGING:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Admission must be discharging before patient departure",
                )

            transitioned_bed = self.db.execute(
                update(Bed)
                .where(
                    Bed.id == bed.id,
                    Bed.status == BedStatus.VACATING,
                    Bed.current_patient_id == patient_id,
                )
                .values(status=BedStatus.CLEANING, current_patient_id=None)
            ).rowcount
            if transitioned_bed != 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Bed departure state changed; refresh and try again",
                )
            mutated = True

            transitioned_admission = self.db.execute(
                update(Admission)
                .where(
                    Admission.id == admission.id,
                    Admission.bed_id == bed.id,
                    Admission.patient_id == patient_id,
                    Admission.status == AdmissionStatus.DISCHARGING,
                )
                .values(status=AdmissionStatus.DISCHARGED)
            ).rowcount
            if transitioned_admission != 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Admission departure state changed; refresh and try again",
                )

            now = datetime.now(timezone.utc)
            payload = self._event_payload(
                bed=bed,
                patient_id=patient_id,
                admission_id=admission.id,
                previous_status=BedStatus.VACATING,
                new_status=BedStatus.CLEANING,
                actor=actor,
                now=now,
            )
            self._add_event("patient_departed_bed", bed.id, payload)
            self._add_event("bed_cleaning_started", bed.id, payload.copy())
            self.db.flush()
            self.db.refresh(bed)
            result = build_result(bed)
            self.db.commit()
        except HTTPException:
            if mutated:
                self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

        return result

    def _cleaning_complete(
        self,
        bed_id: int,
        actor: User,
        build_result: Callable[[Bed], ResultT],
    ) -> ResultT:
        mutated = False
        try:
            self._authorize_actor(actor, "complete bed cleaning")
            bed = self._locked_bed(bed_id)
            if bed.status != BedStatus.CLEANING:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Bed must be cleaning before it can become available",
                )
            if bed.current_patient_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cleaning bed still has a current patient assignment",
                )
            if self._locked_active_owners(bed.id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Bed cannot become available while an active admission references it",
                )

            admission = (
                self.db.query(Admission)
                .populate_existing()
                .with_for_update()
                .filter(
                    Admission.bed_id == bed.id,
                    Admission.status == AdmissionStatus.DISCHARGED,
                )
                .order_by(Admission.updated_at.desc(), Admission.id.desc())
                .first()
            )
            transitioned = self.db.execute(
                update(Bed)
                .where(
                    Bed.id == bed.id,
                    Bed.status == BedStatus.CLEANING,
                    Bed.current_patient_id.is_(None),
                )
                .values(status=BedStatus.AVAILABLE, current_patient_id=None)
            ).rowcount
            if transitioned != 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Bed cleaning state changed; refresh and try again",
                )
            mutated = True

            now = datetime.now(timezone.utc)
            payload = self._event_payload(
                bed=bed,
                patient_id=admission.patient_id if admission is not None else None,
                admission_id=admission.id if admission is not None else None,
                previous_status=BedStatus.CLEANING,
                new_status=BedStatus.AVAILABLE,
                actor=actor,
                now=now,
            )
            self._add_event("bed_available", bed.id, payload)
            self.db.flush()
            self.db.refresh(bed)
            result = build_result(bed)
            self.db.commit()
        except HTTPException:
            if mutated:
                self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

        return result

    def _authorize_actor(self, actor: User, action: str) -> None:
        if not actor or actor.role not in self._ALLOWED_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Only doctors and ward administrators can {action}",
            )

    def _locked_bed(self, bed_id: int) -> Bed:
        bed = (
            self.db.query(Bed)
            .populate_existing()
            .with_for_update()
            .filter(Bed.id == bed_id)
            .first()
        )
        if bed is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bed not found")
        return bed

    def _locked_active_owners(self, bed_id: int) -> list[Admission]:
        return (
            self.db.query(Admission)
            .populate_existing()
            .with_for_update()
            .filter(
                Admission.bed_id == bed_id,
                Admission.status.in_(self._ACTIVE_ADMISSION_STATUSES),
            )
            .order_by(Admission.id)
            .all()
        )

    def _single_active_owner(self, bed: Bed) -> Admission:
        owners = self._locked_active_owners(bed.id)
        if len(owners) > 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bed must have exactly one matching active admission owner",
            )
        if (
            len(owners) != 1
            or bed.current_patient_id is None
            or owners[0].patient_id != bed.current_patient_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bed and admission ownership are inconsistent",
            )
        return owners[0]

    @staticmethod
    def _event_payload(
        *,
        bed: Bed,
        patient_id: int | None,
        admission_id: int | None,
        previous_status: BedStatus,
        new_status: BedStatus,
        actor: User,
        now: datetime,
    ) -> dict:
        return {
            "bed_id": bed.id,
            "patient_id": patient_id,
            "admission_id": admission_id,
            "previous_status": previous_status.value,
            "new_status": new_status.value,
            "timestamp": now.isoformat(),
            "actor_user_id": actor.id,
            "actor_name": actor.name,
            "actor_role": actor.role.value,
        }

    def _add_event(self, event_type: str, bed_id: int, payload: dict) -> None:
        self.db.add(WorkflowEvent(
            event_type=event_type,
            entity_type="bed",
            entity_id=bed_id,
            status="pending",
            trusted_provenance=True,
            payload=payload,
        ))

    def _has_single_matching_release_event(
        self, bed: Bed, admission: Admission, report: DischargeReport,
    ) -> bool:
        events = (
            self.db.query(WorkflowEvent)
            .populate_existing()
            .with_for_update()
            .filter(
                WorkflowEvent.event_type == "bed_release_started",
                WorkflowEvent.entity_type == "bed",
                WorkflowEvent.entity_id == bed.id,
            )
            .order_by(WorkflowEvent.id.desc())
            .all()
        )
        current_events = []
        for event in events:
            payload = event.payload if isinstance(event.payload, dict) else {}
            if (
                is_valid_bed_transition_event(self.db, event)
                and payload.get("bed_id") == bed.id
                and payload.get("patient_id") == bed.current_patient_id
                and payload.get("admission_id") == admission.id
                and payload.get("report_id") == report.id
                and payload.get("previous_status") == BedStatus.OCCUPIED.value
                and payload.get("new_status") == BedStatus.VACATING.value
            ):
                current_events.append(event)

        if len(current_events) != 1:
            return False

        event = current_events[0]
        payload = event.payload if isinstance(event.payload, dict) else {}
        return is_valid_bed_transition_event(self.db, event)

    def _detach_bed(self, bed: Bed) -> Bed:
        self.db.expunge(bed)
        return bed

    def _bed_detail(self, bed: Bed) -> BedDetail:
        detail = BedQueryService(self.db).get_bed(bed.id)
        if detail is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bed not found")
        return detail
