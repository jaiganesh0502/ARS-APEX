from datetime import date
from typing import Optional

from fastapi import HTTPException, status as http_status
from sqlalchemy.orm import Session

from app.models.admission import Admission, AdmissionStatus
from app.models.patient import Patient
from app.repositories.patient_repository import PatientRepository
from app.schemas.patient import (
    PatientAdmissionDetail,
    PatientBedDetail,
    PatientDemographics,
    PatientDetail,
    PatientListResponse,
    PatientMedicalRecordDetail,
    PatientMedicationDetail,
    PatientSummary,
    PatientVitalDetail,
)


def calculate_age(date_of_birth: date, today: Optional[date] = None) -> int:
    reference = today or date.today()
    return reference.year - date_of_birth.year - (
        (reference.month, reference.day) < (date_of_birth.month, date_of_birth.day)
    )


def latest_admission(patient: Patient) -> Optional[Admission]:
    if not patient.admissions:
        return None
    return max(patient.admissions, key=lambda admission: (admission.admission_date, admission.id))


class PatientService:
    def __init__(self, db: Session):
        self.repo = PatientRepository(db)

    def list_patients(
        self,
        page: int,
        page_size: int,
        search: Optional[str] = None,
        admission_status: Optional[AdmissionStatus] = None,
    ) -> PatientListResponse:
        patients, total = self.repo.list_page(page, page_size, search, admission_status)
        items = []
        for patient in patients:
            admission = latest_admission(patient)
            items.append(
                PatientSummary(
                    id=patient.id,
                    patient_code=patient.patient_code,
                    first_name=patient.first_name,
                    last_name=patient.last_name,
                    age=calculate_age(patient.date_of_birth),
                    gender=patient.gender,
                    primary_diagnosis=admission.primary_diagnosis if admission else None,
                    admission_status=admission.status if admission else None,
                    ward=admission.bed.ward if admission and admission.bed else None,
                    bed_number=admission.bed.bed_number if admission and admission.bed else None,
                )
            )
        return PatientListResponse(items=items, page=page, page_size=page_size, total=total)

    def get_patient(self, patient_id: int) -> PatientDetail:
        patient = self.repo.get_detail(patient_id)
        if not patient:
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Patient not found")

        admission = latest_admission(patient)
        admission_detail = None
        bed_detail = None
        medical_record = None
        medications = []
        vitals = []

        if admission:
            admission_detail = PatientAdmissionDetail(
                id=admission.id,
                admission_date=admission.admission_date,
                primary_diagnosis=admission.primary_diagnosis,
                status=admission.status,
                attending_doctor_id=admission.attending_doctor_id,
                attending_doctor=admission.attending_doctor.name,
            )
            if admission.bed:
                bed_detail = PatientBedDetail(
                    ward=admission.bed.ward,
                    bed_number=admission.bed.bed_number,
                    status=admission.bed.status,
                )
            if admission.medical_records:
                record = max(admission.medical_records, key=lambda item: (item.created_at, item.id))
                medical_record = PatientMedicalRecordDetail(
                    id=record.id,
                    diagnosis=record.diagnosis,
                    treatment_course=record.treatment_course,
                    notes=record.notes,
                    created_at=record.created_at,
                )
            medications = [
                PatientMedicationDetail(
                    id=item.id,
                    medication_name=item.medication_name,
                    dosage=item.dosage,
                    frequency=item.frequency,
                    route=item.route,
                    start_date=item.start_date,
                    end_date=item.end_date,
                )
                for item in sorted(admission.medications, key=lambda med: (med.start_date, med.id))
            ]
            vitals = [
                PatientVitalDetail(
                    id=item.id,
                    temperature=item.temperature,
                    heart_rate=item.heart_rate,
                    blood_pressure_systolic=item.blood_pressure_systolic,
                    blood_pressure_diastolic=item.blood_pressure_diastolic,
                    oxygen_saturation=item.oxygen_saturation,
                    recorded_at=item.recorded_at,
                )
                for item in sorted(
                    admission.vitals,
                    key=lambda vital: (vital.recorded_at, vital.id),
                    reverse=True,
                )[:5]
            ]

        return PatientDetail(
            id=patient.id,
            patient_code=patient.patient_code,
            demographics=PatientDemographics(
                first_name=patient.first_name,
                last_name=patient.last_name,
                date_of_birth=patient.date_of_birth,
                age=calculate_age(patient.date_of_birth),
                gender=patient.gender,
                blood_group=patient.blood_group,
                phone=patient.phone,
                emergency_contact=patient.emergency_contact,
            ),
            admission=admission_detail,
            bed=bed_detail,
            medical_record=medical_record,
            medications=medications,
            vitals=vitals,
        )
