from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.admission import Admission, AdmissionStatus
from app.models.bed import Bed, BedStatus
from app.schemas.admission import AdmissionCreate, AdmissionRead


ACTIVE_ADMISSION_STATUSES = (
    AdmissionStatus.ADMITTED,
    AdmissionStatus.DISCHARGING,
    AdmissionStatus.TRANSFER_PENDING,
)


class AdmissionAssignmentService:
    """Creates admissions and atomically claims beds for active assignments."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, admission_in: AdmissionCreate) -> AdmissionRead:
        try:
            if (
                admission_in.bed_id is not None
                and admission_in.status in ACTIVE_ADMISSION_STATUSES
            ):
                self._claim_available_bed(admission_in.bed_id, admission_in.patient_id)

            admission = Admission(**admission_in.model_dump())
            self.db.add(admission)
            self.db.flush()
            self.db.refresh(admission)
            response = AdmissionRead.model_validate(admission)
            self.db.commit()
            return response
        except HTTPException:
            raise
        except IntegrityError as error:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bed is unavailable or already has an active admission",
            ) from error
        except Exception:
            self.db.rollback()
            raise

    def _claim_available_bed(self, bed_id: int, patient_id: int) -> None:
        bed = (
            self.db.query(Bed)
            .populate_existing()
            .with_for_update()
            .filter(Bed.id == bed_id)
            .first()
        )
        if bed is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bed not found")

        active_owner = (
            self.db.query(Admission.id)
            .populate_existing()
            .with_for_update()
            .filter(
                Admission.bed_id == bed.id,
                Admission.status.in_(ACTIVE_ADMISSION_STATUSES),
            )
            .first()
        )
        if (
            bed.status != BedStatus.AVAILABLE
            or bed.current_patient_id is not None
            or active_owner is not None
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bed is unavailable or already has an active admission",
            )

        claimed = self.db.execute(
            update(Bed)
            .where(
                Bed.id == bed.id,
                Bed.status == BedStatus.AVAILABLE,
                Bed.current_patient_id.is_(None),
            )
            .values(status=BedStatus.OCCUPIED, current_patient_id=patient_id)
        ).rowcount
        if claimed != 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bed is unavailable or already has an active admission",
            )
