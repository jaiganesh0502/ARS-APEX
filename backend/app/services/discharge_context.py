from typing import Any

from app.models.admission import Admission
from app.models.clinical_decision import ClinicalDecision


NOT_DOCUMENTED = "Not documented"


def _value_or_missing(value: Any) -> Any:
    return value if value is not None and value != "" else NOT_DOCUMENTED


def build_discharge_context(
    admission: Admission, decision: ClinicalDecision
) -> dict[str, Any]:
    """Build the deterministic, persisted-only context supplied to the LLM client."""
    patient = admission.patient
    doctor = admission.attending_doctor
    medical_records = sorted(
        admission.medical_records,
        key=lambda record: (record.created_at, record.id),
    )
    medications = sorted(
        admission.medications,
        key=lambda medication: (medication.start_date, medication.created_at, medication.id),
    )
    recent_vitals = sorted(
        admission.vitals,
        key=lambda vital: (vital.recorded_at, vital.id),
        reverse=True,
    )[:5]

    return {
        "patient": {
            "patient_code": patient.patient_code,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": patient.date_of_birth,
            "gender": patient.gender,
            "blood_group": _value_or_missing(patient.blood_group),
            "phone": _value_or_missing(patient.phone),
            "emergency_contact": _value_or_missing(patient.emergency_contact),
        },
        "admission": {
            "admission_date": admission.admission_date,
            "primary_diagnosis": admission.primary_diagnosis,
            "attending_doctor": _value_or_missing(doctor.name if doctor else None),
        },
        "bed": (
            {
                "ward": admission.bed.ward,
                "bed_number": admission.bed.bed_number,
            }
            if admission.bed
            else NOT_DOCUMENTED
        ),
        "medical_records": [
            {
                "diagnosis": record.diagnosis,
                "treatment_course": record.treatment_course,
                "notes": _value_or_missing(record.notes),
                "created_at": record.created_at,
            }
            for record in medical_records
        ],
        "medications": [
            {
                "medication_name": medication.medication_name,
                "dosage": medication.dosage,
                "frequency": medication.frequency,
                "route": medication.route,
                "start_date": medication.start_date,
                "end_date": _value_or_missing(medication.end_date),
            }
            for medication in medications
        ],
        "recent_vitals": [
            {
                "temperature": vital.temperature,
                "heart_rate": vital.heart_rate,
                "blood_pressure_systolic": vital.blood_pressure_systolic,
                "blood_pressure_diastolic": vital.blood_pressure_diastolic,
                "oxygen_saturation": vital.oxygen_saturation,
                "recorded_at": vital.recorded_at,
            }
            for vital in recent_vitals
        ],
        "decision": {
            "reason": decision.reason,
            "notes": _value_or_missing(decision.notes),
        },
    }
