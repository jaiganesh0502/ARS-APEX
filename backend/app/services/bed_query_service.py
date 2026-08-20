from collections.abc import Mapping
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.admission import Admission, AdmissionStatus
from app.models.bed import Bed, BedStatus
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.patient import Patient
from app.models.workflow_event import WorkflowEvent
from app.schemas.bed import BedDetail, BedSummary, BedTransitionEventRead
from app.services.bed_event_policy import (
    BED_TRANSITION_EVENT_TYPES,
    is_valid_bed_transition_event,
    is_valid_report_approval_event,
)


class BedQueryService:
    """Build the operational views consumed by bed-management read routes."""

    def __init__(self, db: Session):
        self.db = db

    def list_beds(
        self,
        status: Optional[BedStatus] = None,
        ward: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[BedSummary]:
        query = self.db.query(Bed)
        if ward is not None:
            query = query.filter(Bed.ward == ward)
        if status:
            query = query.filter(Bed.status == status)
        beds = query.order_by(Bed.id).offset(skip).limit(limit).all()
        contexts, eligible_bed_ids = self._load_current_contexts(beds)
        return [self._summary_for(bed, contexts, eligible_bed_ids) for bed in beds]

    def get_bed(self, bed_id: int) -> Optional[BedDetail]:
        bed = self.db.get(Bed, bed_id)
        if bed is None:
            return None

        contexts, eligible_bed_ids = self._load_current_contexts([bed])
        historical_admission = None
        if bed.status in (BedStatus.CLEANING, BedStatus.AVAILABLE):
            historical_admission = self._most_recent_discharged_admission(bed)
        summary = self._summary_for(bed, contexts, eligible_bed_ids, historical_admission)
        events = (
            self.db.query(WorkflowEvent)
            .filter(
                WorkflowEvent.entity_type == "bed",
                WorkflowEvent.entity_id == bed.id,
                WorkflowEvent.event_type.in_(BED_TRANSITION_EVENT_TYPES),
            )
            .order_by(WorkflowEvent.created_at.desc(), WorkflowEvent.id.desc())
            .all()
        )
        events = [
            event for event in events
            if is_valid_bed_transition_event(self.db, event)
        ]
        return BedDetail(
            **summary.model_dump(),
            transition_history=[
                BedTransitionEventRead(
                    event_type=event.event_type,
                    previous_status=self._payload_status(event.payload, "previous_status"),
                    new_status=self._payload_status(event.payload, "new_status"),
                    created_at=event.created_at,
                )
                for event in events
            ],
        )

    def _load_current_contexts(
        self, beds: list[Bed],
    ) -> tuple[dict[int, tuple[Admission, Patient]], set[int]]:
        candidates = [
            bed for bed in beds
            if bed.status in (BedStatus.OCCUPIED, BedStatus.VACATING) and bed.current_patient_id is not None
        ]
        if not candidates:
            return {}, set()

        patient_id_by_bed_id = {bed.id: bed.current_patient_id for bed in candidates}
        admissions = (
            self.db.query(Admission)
            .filter(
                Admission.bed_id.in_(patient_id_by_bed_id),
                Admission.patient_id.in_(patient_id_by_bed_id.values()),
                Admission.status.notin_([AdmissionStatus.DISCHARGED, AdmissionStatus.TRANSFERRED]),
            )
            .order_by(Admission.updated_at.desc(), Admission.id.desc())
            .all()
        )
        admission_by_bed_id = {}
        for admission in admissions:
            if (
                patient_id_by_bed_id.get(admission.bed_id) == admission.patient_id
                and admission.bed_id not in admission_by_bed_id
            ):
                admission_by_bed_id[admission.bed_id] = admission

        patients = (
            self.db.query(Patient)
            .filter(Patient.id.in_(patient_id_by_bed_id.values()))
            .all()
        )
        patient_by_id = {patient.id: patient for patient in patients}
        contexts = {
            bed_id: (admission, patient_by_id[admission.patient_id])
            for bed_id, admission in admission_by_bed_id.items()
            if admission.patient_id in patient_by_id
        }

        candidate_by_id = {bed.id: bed for bed in candidates}
        eligible_contexts = [
            (bed_id, admission)
            for bed_id, (admission, _) in contexts.items()
            if candidate_by_id[bed_id].status == BedStatus.OCCUPIED
            and admission.status == AdmissionStatus.DISCHARGING
        ]
        if not eligible_contexts:
            return contexts, set()

        candidate_admission_ids = [admission.id for _, admission in eligible_contexts]
        approval_candidates = (
            self.db.query(DischargeReport, WorkflowEvent)
            .join(
                WorkflowEvent,
                and_(
                    WorkflowEvent.entity_type == "discharge_report",
                    WorkflowEvent.entity_id == DischargeReport.id,
                    WorkflowEvent.event_type == "report_approved",
                    WorkflowEvent.trusted_provenance.is_(True),
                ),
            )
            .filter(
                DischargeReport.admission_id.in_(candidate_admission_ids),
                DischargeReport.status == DischargeReportStatus.APPROVED,
            )
            .all()
        )
        report_event_pairs = {
            (report.admission_id, report.patient_id)
            for report, event in approval_candidates
            if is_valid_report_approval_event(self.db, event, report)
        }
        return contexts, {
            bed_id
            for bed_id, admission in eligible_contexts
            if (admission.id, admission.patient_id) in report_event_pairs
        }

    def _summary_for(
        self,
        bed: Bed,
        contexts: dict[int, tuple[Admission, Patient]],
        eligible_bed_ids: set[int],
        historical_admission: Optional[Admission] = None,
    ) -> BedSummary:
        admission, patient = contexts.get(bed.id, (historical_admission, None))
        return BedSummary(
            id=bed.id,
            ward=bed.ward,
            bed_number=bed.bed_number,
            status=bed.status,
            current_patient_id=patient.id if patient is not None else None,
            patient_name=f"{patient.first_name} {patient.last_name}" if patient is not None else None,
            patient_code=patient.patient_code if patient is not None else None,
            admission_id=admission.id if admission is not None else None,
            admission_status=admission.status if admission is not None else None,
            primary_diagnosis=admission.primary_diagnosis if admission is not None else None,
            release_eligible=bed.id in eligible_bed_ids,
            updated_at=bed.updated_at,
        )

    def _most_recent_discharged_admission(self, bed: Bed) -> Optional[Admission]:
        return (
            self.db.query(Admission)
            .filter(Admission.bed_id == bed.id, Admission.status == AdmissionStatus.DISCHARGED)
            .order_by(Admission.admission_date.desc(), Admission.id.desc())
            .first()
        )

    @staticmethod
    def _payload_status(payload: object, key: str) -> Optional[BedStatus]:
        if not isinstance(payload, Mapping):
            return None
        try:
            return BedStatus(payload.get(key))
        except (TypeError, ValueError):
            return None
