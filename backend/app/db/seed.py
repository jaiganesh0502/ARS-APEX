import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    Admission,
    AdmissionStatus,
    Bed,
    BedStatus,
    ClinicalDecision,
    ClinicalDecisionStatus,
    ClinicalDecisionType,
    Hospital,
    HospitalCapacity,
    MedicalRecord,
    Medication,
    Patient,
    TransferUrgency,
    User,
    UserRole,
    Vital,
    WorkflowEvent,
)
from app.services.bed_event_policy import is_valid_bed_transition_event

from app.core.security import hash_password

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _find_dataset_path() -> Path:
    candidates = [
        Path(__file__).resolve().parents[3] / "data" / "synthetic" / "patients.json",
        Path(__file__).resolve().parents[2] / "data" / "synthetic" / "patients.json",
        Path(__file__).resolve().parents[1] / "data" / "synthetic" / "patients.json",
        Path("/app/data/synthetic/patients.json"),
        Path("/data/synthetic/patients.json"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]

DATASET_PATH = _find_dataset_path()


def _seed_demo_users(db: Session, primary_patient: Optional[Patient] = None) -> User:
    # 1. Primary Attending Doctor
    doc_email = "doctor@demo.local"
    doctor = db.query(User).filter(User.email == doc_email).first()
    if not doctor:
        doctor = User(
            name="Dr. Aris Thorne",
            email=doc_email,
            role=UserRole.DOCTOR,
            password_hash=hash_password("DoctorDemo123!"),
            is_active=True,
        )
        db.add(doctor)
        db.flush()
    else:
        doctor.password_hash = hash_password("DoctorDemo123!")

    # 2. Medical Superintendent
    super_email = "superintendent@demo.local"
    superintendent = db.query(User).filter(User.email == super_email).first()
    if not superintendent:
        superintendent = User(
            name="Dr. Marcus Vance (Superintendent)",
            email=super_email,
            role=UserRole.MEDICAL_SUPERINTENDENT,
            password_hash=hash_password("SuperDemo123!"),
            is_active=True,
        )
        db.add(superintendent)
        db.flush()
    else:
        superintendent.password_hash = hash_password("SuperDemo123!")

    # 3. Patient Demo User
    pat_email = "patient@demo.local"
    patient_user = db.query(User).filter(User.email == pat_email).first()
    target_patient_id = primary_patient.id if primary_patient else None
    if not patient_user:
        patient_user = User(
            name=f"{primary_patient.first_name} {primary_patient.last_name}" if primary_patient else "Eleanor Vance",
            email=pat_email,
            role=UserRole.PATIENT,
            password_hash=hash_password("PatientDemo123!"),
            is_active=True,
            patient_id=target_patient_id,
        )
        db.add(patient_user)
        db.flush()
    else:
        patient_user.password_hash = hash_password("PatientDemo123!")
        if target_patient_id:
            patient_user.patient_id = target_patient_id

    # 4. Receptionist Demo User
    rec_email = "receptionist@demo.local"
    receptionist = db.query(User).filter(User.email == rec_email).first()
    if not receptionist:
        receptionist = User(
            name="Priya Sharma (Reception)",
            email=rec_email,
            role=UserRole.RECEPTIONIST,
            password_hash=hash_password("ReceptionDemo123!"),
            is_active=True,
        )
        db.add(receptionist)
        db.flush()
    else:
        receptionist.password_hash = hash_password("ReceptionDemo123!")

    # Legacy Asha Rao user for test backward-compatibility
    asha_email = "asha.rao@synthetic-hospital.test"
    asha = db.query(User).filter(User.email == asha_email).first()
    if not asha:
        asha = User(
            name="Dr. Asha Rao",
            email=asha_email,
            role=UserRole.DOCTOR,
            password_hash=hash_password("DoctorDemo123!"),
            is_active=True,
        )
        db.add(asha)
        db.flush()

    return asha


def _doctor(db: Session) -> User:
    return _seed_demo_users(db)


SYNTHETIC_HOSPITALS = [
    {
        "name": "Metro Multispeciality Medical Center",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "specialties": ["Cardiology", "Neurology", "Critical Care", "General Surgery"],
        "contact_number": "+1-415-555-0100",
        "capacities": [
            {"specialty": "Cardiology", "total_beds": 15, "available_beds": 0},
            {"specialty": "Neurology", "total_beds": 10, "available_beds": 0},
            {"specialty": "Critical Care", "total_beds": 8, "available_beds": 1},
            {"specialty": "General Surgery", "total_beds": 12, "available_beds": 3},
        ],
    },
    {
        "name": "Green Valley Specialty Hospital",
        "latitude": 37.7885,
        "longitude": -122.4075,
        "specialties": ["Orthopedics", "General Surgery", "Gastroenterology"],
        "contact_number": "+1-415-555-0201",
        "capacities": [
            {"specialty": "Orthopedics", "total_beds": 15, "available_beds": 4},
            {"specialty": "General Surgery", "total_beds": 12, "available_beds": 2},
            {"specialty": "Gastroenterology", "total_beds": 8, "available_beds": 0},
        ],
    },
    {
        "name": "City Heart & Neuro Institute",
        "latitude": 37.7550,
        "longitude": -122.4300,
        "specialties": ["Cardiology", "Neurology", "Critical Care"],
        "contact_number": "+1-415-555-0302",
        "capacities": [
            {"specialty": "Cardiology", "total_beds": 12, "available_beds": 3},
            {"specialty": "Neurology", "total_beds": 10, "available_beds": 2},
            {"specialty": "Critical Care", "total_beds": 8, "available_beds": 1},
        ],
    },
    {
        "name": "Central Regional Hospital",
        "latitude": 37.7150,
        "longitude": -122.4600,
        "specialties": ["General Medicine", "Pulmonology", "Nephrology", "General Surgery"],
        "contact_number": "+1-415-555-0403",
        "capacities": [
            {"specialty": "General Medicine", "total_beds": 20, "available_beds": 5},
            {"specialty": "Pulmonology", "total_beds": 10, "available_beds": 3},
            {"specialty": "Nephrology", "total_beds": 8, "available_beds": 0},
            {"specialty": "General Surgery", "total_beds": 15, "available_beds": 4},
        ],
    },
]


ACTIVE_ADMISSION_STATUSES = (
    AdmissionStatus.ADMITTED,
    AdmissionStatus.DISCHARGING,
    AdmissionStatus.TRANSFER_PENDING,
)


def _bed_for_new_assignment(db: Session, ward: str, number: str) -> Bed:
    bed = db.query(Bed).filter(Bed.ward == ward, Bed.bed_number == number).first()
    if not bed:
        bed = Bed(ward=ward, bed_number=number, status=BedStatus.OCCUPIED)
        db.add(bed)
        db.flush()
        return bed

    active_owner = db.query(Admission.id).filter(
        Admission.bed_id == bed.id,
        Admission.status.in_(ACTIVE_ADMISSION_STATUSES),
    ).first()
    if bed.status != BedStatus.AVAILABLE or bed.current_patient_id is not None or active_owner:
        raise RuntimeError(
            f"Seed bed {ward}/{number} is not available for a new active assignment"
        )
    return bed


def _has_valid_release_lineage(db: Session, bed: Bed, admission: Admission) -> bool:
    events = db.query(WorkflowEvent).filter(
        WorkflowEvent.event_type == "bed_release_started",
        WorkflowEvent.entity_type == "bed",
        WorkflowEvent.entity_id == bed.id,
    ).all()
    matches = []
    for event in events:
        payload = event.payload if isinstance(event.payload, dict) else {}
        if (
            is_valid_bed_transition_event(db, event)
            and payload.get("bed_id") == bed.id
            and payload.get("patient_id") == admission.patient_id
            and payload.get("admission_id") == admission.id
        ):
            matches.append(event)
    return len(matches) == 1


def _validate_existing_turnover(db: Session, admission: Admission) -> None:
    if admission.bed_id is None:
        return
    bed = db.get(Bed, admission.bed_id)
    if bed is None or bed.status != BedStatus.VACATING:
        return
    if (
        admission.status != AdmissionStatus.DISCHARGING
        or bed.current_patient_id != admission.patient_id
        or not _has_valid_release_lineage(db, bed, admission)
    ):
        raise RuntimeError(
            "Seeded vacating bed requires valid bed_release_started lineage"
        )


def _seed_hospitals(db: Session) -> None:
    """Idempotently seed fictional partner hospitals and specialty capacities."""
    for h_data in SYNTHETIC_HOSPITALS:
        hospital = db.query(Hospital).filter(Hospital.name == h_data["name"]).first()
        if not hospital:
            hospital = Hospital(
                name=h_data["name"],
                latitude=h_data["latitude"],
                longitude=h_data["longitude"],
                specialties=h_data["specialties"],
                contact_number=h_data["contact_number"],
            )
            db.add(hospital)
            db.flush()
        else:
            hospital.latitude = h_data["latitude"]
            hospital.longitude = h_data["longitude"]
            hospital.specialties = h_data["specialties"]
            hospital.contact_number = h_data["contact_number"]
            db.flush()

        for cap_data in h_data["capacities"]:
            capacity = db.query(HospitalCapacity).filter(
                HospitalCapacity.hospital_id == hospital.id,
                HospitalCapacity.specialty == cap_data["specialty"],
            ).first()
            if not capacity:
                capacity = HospitalCapacity(
                    hospital_id=hospital.id,
                    specialty=cap_data["specialty"],
                    total_beds=cap_data["total_beds"],
                    available_beds=cap_data["available_beds"],
                )
                db.add(capacity)
            else:
                capacity.total_beds = cap_data["total_beds"]
                capacity.available_beds = cap_data["available_beds"]
    db.flush()


def _seed_patient(db: Session, data: dict, doctor: User) -> None:
    patient = db.query(Patient).filter(Patient.patient_code == data["patient_code"]).first()
    if not patient:
        patient = Patient(
            patient_code=data["patient_code"], first_name=data["first_name"], last_name=data["last_name"],
            date_of_birth=date.fromisoformat(data["date_of_birth"]), gender=data["gender"],
            blood_group=data.get("blood_group"), phone=data.get("phone"), emergency_contact=data.get("emergency_contact"),
        )
        db.add(patient)
        db.flush()

    source = data["active_admission"]
    admission = db.query(Admission).filter(
        Admission.patient_id == patient.id, Admission.primary_diagnosis == source["primary_diagnosis"]
    ).first()
    if not admission:
        bed = _bed_for_new_assignment(db, source["ward"], source["bed_number"])
        admission = Admission(
            patient_id=patient.id,
            admission_date=datetime.fromisoformat(source["admission_date"].replace("Z", "+00:00")),
            primary_diagnosis=source["primary_diagnosis"], attending_doctor_id=doctor.id,
            status=AdmissionStatus(source["status"]), bed_id=bed.id,
        )
        db.add(admission)
        db.flush()
        bed.status = BedStatus.OCCUPIED
        bed.current_patient_id = patient.id
    else:
        _validate_existing_turnover(db, admission)

    for record in source["medical_records"]:
        if not db.query(MedicalRecord).filter(MedicalRecord.admission_id == admission.id, MedicalRecord.diagnosis == record["diagnosis"]).first():
            db.add(MedicalRecord(patient_id=patient.id, admission_id=admission.id, **record))
    for medication in source["medications"]:
        started = date.fromisoformat(medication["start_date"])
        if not db.query(Medication).filter(Medication.admission_id == admission.id, Medication.medication_name == medication["medication_name"], Medication.start_date == started).first():
            db.add(Medication(
                patient_id=patient.id, admission_id=admission.id, medication_name=medication["medication_name"],
                dosage=medication["dosage"], frequency=medication["frequency"], route=medication["route"],
                start_date=started, end_date=date.fromisoformat(medication["end_date"]) if medication.get("end_date") else None,
            ))
    for vital in source["vitals"]:
        recorded = datetime.fromisoformat(vital["recorded_at"].replace("Z", "+00:00"))
        if not db.query(Vital).filter(Vital.admission_id == admission.id, Vital.recorded_at == recorded).first():
            db.add(Vital(
                patient_id=patient.id, admission_id=admission.id, temperature=vital["temperature"],
                heart_rate=vital["heart_rate"], blood_pressure_systolic=vital["blood_pressure_systolic"],
                blood_pressure_diastolic=vital["blood_pressure_diastolic"], oxygen_saturation=vital["oxygen_saturation"],
                recorded_at=recorded,
            ))

    # Seed confirmed transfer decision for transfer_pending synthetic patients
    if admission.status == AdmissionStatus.TRANSFER_PENDING:
        decision = db.query(ClinicalDecision).filter(
            ClinicalDecision.admission_id == admission.id,
            ClinicalDecision.status == ClinicalDecisionStatus.CONFIRMED,
        ).first()
        if not decision:
            is_cardio = "Coronary" in admission.primary_diagnosis or "Heart" in admission.primary_diagnosis
            req_spec = "Cardiology" if is_cardio else "Neurology"
            urgency = TransferUrgency.EMERGENCY if is_cardio else TransferUrgency.NON_EMERGENCY
            reason = (
                "Acute coronary syndrome requiring urgent catheterization and cardiac monitoring."
                if is_cardio
                else "Requires tertiary neurology stroke care and specialized neurovascular monitoring."
            )
            decision = ClinicalDecision(
                patient_id=patient.id,
                admission_id=admission.id,
                decision_type=ClinicalDecisionType.TRANSFER,
                transfer_urgency=urgency,
                reason=reason,
                required_specialty=req_spec,
                notes="Synthetic transfer case confirmed by attending physician.",
                decided_by=doctor.id,
                decided_at=datetime.now(timezone.utc),
                status=ClinicalDecisionStatus.CONFIRMED,
            )
            db.add(decision)
            db.flush()


def seed_database(db: Optional[Session] = None) -> None:
    """Idempotently seed fictional patient and hospital records into an already migrated database."""
    owns_session = db is None
    session = db or SessionLocal()
    savepoint = session.begin_nested() if not owns_session else None
    try:
        doctor = _doctor(session)
        _seed_hospitals(session)
        first_patient = None
        with DATASET_PATH.open("r", encoding="utf-8") as dataset:
            for patient_data in json.load(dataset):
                p = _seed_patient(session, patient_data, doctor)
                if not first_patient:
                    first_patient = p
        
        # Seed ChargeMaster catalog
        from app.services.charge_master_service import ChargeMasterService
        ChargeMasterService(session).seed_defaults_if_empty()

        # Link patient demo user to the primary demo patient
        if first_patient:
            _seed_demo_users(session, primary_patient=first_patient)
        if savepoint is not None:
            savepoint.commit()
        session.commit()
        logger.info("Synthetic patient and partner hospital seed data is ready.")
    except Exception:
        if savepoint is not None and savepoint.is_active:
            savepoint.rollback()
        elif owns_session:
            session.rollback()
        logger.exception("Unable to seed synthetic database data")
        raise
    finally:
        if owns_session:
            session.close()


if __name__ == "__main__":
    seed_database()
