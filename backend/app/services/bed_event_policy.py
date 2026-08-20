from collections.abc import Mapping
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.admission import Admission
from app.models.bed import Bed
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.patient import Patient
from app.models.user import User
from app.models.user import UserRole
from app.models.workflow_event import WorkflowEvent


BED_TRANSITION_STATUS_PAIRS = {
    "bed_release_started": ("occupied", "vacating"),
    "patient_departed_bed": ("vacating", "cleaning"),
    "bed_cleaning_started": ("vacating", "cleaning"),
    "bed_available": ("cleaning", "available"),
}
BED_TRANSITION_EVENT_TYPES = tuple(BED_TRANSITION_STATUS_PAIRS)
EVENT_TIMESTAMP_TOLERANCE = timedelta(seconds=5)


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _timestamps_match(left: datetime | None, right: datetime | None) -> bool:
    normalized_left = _as_utc(left)
    normalized_right = _as_utc(right)
    return (
        normalized_left is not None
        and normalized_right is not None
        and abs(normalized_left - normalized_right) <= EVENT_TIMESTAMP_TOLERANCE
    )


def is_valid_report_approval_event(
    db: Session,
    event: WorkflowEvent,
    report: DischargeReport | None = None,
) -> bool:
    """Require trusted approval evidence tied to persisted clinical records."""
    if (
        not event.trusted_provenance
        or event.event_type != "report_approved"
        or event.entity_type != "discharge_report"
        or event.status != "pending"
        or not isinstance(event.payload, Mapping)
    ):
        return False

    report = report or db.get(DischargeReport, event.entity_id)
    if (
        report is None
        or event.entity_id != report.id
        or report.status != DischargeReportStatus.APPROVED
        or report.approved_by is None
        or report.approved_at is None
    ):
        return False

    admission = db.get(Admission, report.admission_id)
    patient = db.get(Patient, report.patient_id)
    approving_user = db.get(User, report.approved_by)
    if (
        admission is None
        or patient is None
        or approving_user is None
        or admission.patient_id != patient.id
    ):
        return False

    payload = event.payload
    approved_at = _parse_timestamp(payload.get("approved_at"))
    return (
        payload.get("report_id") == report.id
        and payload.get("patient_id") == patient.id
        and payload.get("admission_id") == admission.id
        and payload.get("approved_by") == approving_user.id
        and _timestamps_match(approved_at, report.approved_at)
        and _timestamps_match(approved_at, event.created_at)
    )


def is_valid_bed_transition_event(db: Session, event: WorkflowEvent) -> bool:
    """Require trusted bed-transition shape plus persisted relational correlation."""
    if (
        not event.trusted_provenance
        or event.event_type not in BED_TRANSITION_STATUS_PAIRS
        or event.entity_type != "bed"
        or event.status != "pending"
        or not isinstance(event.payload, Mapping)
    ):
        return False

    payload = event.payload
    required_fields = {
        "bed_id",
        "patient_id",
        "admission_id",
        "previous_status",
        "new_status",
        "timestamp",
        "actor_user_id",
        "actor_name",
        "actor_role",
    }
    if not required_fields.issubset(payload):
        return False

    previous_status, new_status = BED_TRANSITION_STATUS_PAIRS[event.event_type]
    if (
        payload.get("bed_id") != event.entity_id
        or payload.get("previous_status") != previous_status
        or payload.get("new_status") != new_status
        or not isinstance(payload.get("actor_user_id"), int)
        or not isinstance(payload.get("actor_name"), str)
        or payload.get("actor_role") not in {
            UserRole.DOCTOR.value,
            UserRole.WARD_ADMIN.value,
            UserRole.MEDICAL_SUPERINTENDENT.value,
            UserRole.RECEIVING_ADMIN.value,
        }
    ):
        return False

    event_timestamp = _parse_timestamp(payload.get("timestamp"))
    if not _timestamps_match(event_timestamp, event.created_at):
        return False

    bed = db.get(Bed, event.entity_id)
    actor = db.get(User, payload.get("actor_user_id"))
    if (
        bed is None
        or actor is None
        or actor.role not in {
            UserRole.DOCTOR,
            UserRole.WARD_ADMIN,
            UserRole.MEDICAL_SUPERINTENDENT,
            UserRole.RECEIVING_ADMIN,
        }
        or payload.get("actor_name") != actor.name
        or payload.get("actor_role") != actor.role.value
    ):
        return False

    if event.event_type == "bed_release_started":
        if not isinstance(payload.get("report_id"), int):
            return False

    if event.event_type != "bed_available" and (
        not isinstance(payload.get("patient_id"), int)
        or not isinstance(payload.get("admission_id"), int)
    ):
        return False

    patient_id = payload.get("patient_id")
    admission_id = payload.get("admission_id")
    if patient_id is None or admission_id is None:
        if event.event_type != "bed_available" or patient_id is not None or admission_id is not None:
            return False
        admission = None
        patient = None
    else:
        if not isinstance(patient_id, int) or not isinstance(admission_id, int):
            return False
        admission = db.get(Admission, admission_id)
        patient = db.get(Patient, patient_id)
        if (
            admission is None
            or patient is None
            or admission.patient_id != patient.id
            or admission.bed_id != bed.id
        ):
            return False

    if event.event_type == "bed_release_started":
        report = db.get(DischargeReport, payload.get("report_id"))
        if (
            report is None
            or admission is None
            or patient is None
            or report.status != DischargeReportStatus.APPROVED
            or report.admission_id != admission.id
            or report.patient_id != patient.id
        ):
            return False

    return True
