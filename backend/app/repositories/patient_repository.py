from typing import Optional, List
from sqlalchemy.orm import Session, joinedload, selectinload
from app.models.patient import Patient
from app.models.admission import Admission, AdmissionStatus
from app.repositories.base import BaseRepository


class PatientRepository(BaseRepository[Patient]):
    def __init__(self, db: Session):
        super().__init__(Patient, db)

    def get_by_patient_code(self, patient_code: str) -> Optional[Patient]:
        return self.db.query(Patient).filter(Patient.patient_code == patient_code).first()

    def search_by_name(self, query: str, limit: int = 20) -> List[Patient]:
        search_pattern = f"%{query}%"
        return self.db.query(Patient).filter(
            (Patient.first_name.ilike(search_pattern)) | 
            (Patient.last_name.ilike(search_pattern)) | 
            (Patient.patient_code.ilike(search_pattern))
        ).limit(limit).all()

    def list_page(
        self,
        page: int,
        page_size: int,
        search: Optional[str] = None,
        status: Optional[AdmissionStatus] = None,
    ) -> tuple[List[Patient], int]:
        query = self.db.query(Patient)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                Patient.patient_code.ilike(pattern)
                | Patient.first_name.ilike(pattern)
                | Patient.last_name.ilike(pattern)
            )
        if status:
            query = query.filter(Patient.admissions.any(Admission.status == status))

        total = query.count()
        patients = (
            query.options(
                selectinload(Patient.admissions).joinedload(Admission.bed),
                selectinload(Patient.admissions).joinedload(Admission.attending_doctor),
            )
            .order_by(Patient.patient_code.asc(), Patient.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return patients, total

    def get_detail(self, patient_id: int) -> Optional[Patient]:
        return (
            self.db.query(Patient)
            .options(
                selectinload(Patient.admissions).joinedload(Admission.bed),
                selectinload(Patient.admissions).joinedload(Admission.attending_doctor),
                selectinload(Patient.admissions).selectinload(Admission.medical_records),
                selectinload(Patient.admissions).selectinload(Admission.medications),
                selectinload(Patient.admissions).selectinload(Admission.vitals),
            )
            .filter(Patient.id == patient_id)
            .first()
        )
