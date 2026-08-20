from datetime import date, datetime, timedelta, timezone

import pytest

from app.models import (
    Admission,
    AdmissionStatus,
    Bed,
    BedStatus,
    MedicalRecord,
    Medication,
    Patient,
    User,
    UserRole,
    Vital,
)


@pytest.fixture
def patient_records(db_session):
    doctor = User(name="Dr. Synthetic Demo", email="demo.doctor@example.test", role=UserRole.DOCTOR)
    beds = [
        Bed(ward="General Medicine", bed_number="GM-12", status=BedStatus.OCCUPIED),
        Bed(ward="Neurology", bed_number="NEU-04", status=BedStatus.OCCUPIED),
    ]
    db_session.add_all([doctor, *beds])
    db_session.flush()

    patients = [
        Patient(
            patient_code="PT-1001",
            first_name="Arun",
            last_name="Kumar",
            date_of_birth=date(1974, 4, 18),
            gender="Male",
            blood_group="O+",
            phone="+91-90000-01001",
            emergency_contact="Synthetic Contact 1",
        ),
        Patient(
            patient_code="PT-1004",
            first_name="Meera",
            last_name="Nair",
            date_of_birth=date(1968, 9, 7),
            gender="Female",
            blood_group="A+",
            phone="+91-90000-01004",
            emergency_contact="Synthetic Contact 4",
        ),
    ]
    db_session.add_all(patients)
    db_session.flush()

    admissions = [
        Admission(
            patient_id=patients[0].id,
            admission_date=datetime(2026, 8, 15, tzinfo=timezone.utc),
            primary_diagnosis="Community Acquired Pneumonia",
            attending_doctor_id=doctor.id,
            status=AdmissionStatus.ADMITTED,
            bed_id=beds[0].id,
        ),
        Admission(
            patient_id=patients[1].id,
            admission_date=datetime(2026, 8, 18, tzinfo=timezone.utc),
            primary_diagnosis="Acute Ischemic Stroke",
            attending_doctor_id=doctor.id,
            status=AdmissionStatus.TRANSFER_PENDING,
            bed_id=beds[1].id,
        ),
    ]
    db_session.add_all(admissions)
    db_session.flush()

    beds[0].current_patient_id = patients[0].id
    beds[1].current_patient_id = patients[1].id
    db_session.add(
        MedicalRecord(
            patient_id=patients[0].id,
            admission_id=admissions[0].id,
            diagnosis="Community Acquired Pneumonia",
            treatment_course="IV antibiotics and respiratory monitoring.",
            notes="Synthetic patient improving clinically.",
        )
    )
    db_session.add(
        Medication(
            patient_id=patients[0].id,
            admission_id=admissions[0].id,
            medication_name="Ceftriaxone",
            dosage="1 g",
            frequency="Twice daily",
            route="IV",
            start_date=date(2026, 8, 15),
        )
    )
    base_time = datetime(2026, 8, 19, 8, tzinfo=timezone.utc)
    for offset in range(6):
        db_session.add(
            Vital(
                patient_id=patients[0].id,
                admission_id=admissions[0].id,
                temperature=37.8 - offset * 0.1,
                heart_rate=92 - offset,
                blood_pressure_systolic=122,
                blood_pressure_diastolic=78,
                oxygen_saturation=95 + min(offset, 3),
                recorded_at=base_time - timedelta(hours=offset),
            )
        )
    db_session.commit()
    return patients


def test_list_patients_is_paginated(client, patient_records):
    response = client.get("/api/patients?page=1&page_size=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 1
    assert payload["total"] == 2
    assert len(payload["items"]) == 1
    assert payload["items"][0]["patient_code"] == "PT-1001"
    assert payload["items"][0]["primary_diagnosis"] == "Community Acquired Pneumonia"
    assert payload["items"][0]["ward"] == "General Medicine"


@pytest.mark.parametrize("search", ["pt-1001", "ARUN", "kUmAr"])
def test_patient_search_is_case_insensitive(client, patient_records, search):
    response = client.get("/api/patients", params={"search": search})

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["patient_code"] == "PT-1001"


def test_patient_status_filter(client, patient_records):
    response = client.get("/api/patients", params={"status": "transfer_pending"})

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["patient_code"] == "PT-1004"


def test_patient_detail_contains_clinical_profile(client, patient_records):
    patient = patient_records[0]
    response = client.get(f"/api/patients/{patient.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["patient_code"] == "PT-1001"
    assert payload["demographics"]["first_name"] == "Arun"
    assert payload["admission"]["attending_doctor"] == "Dr. Synthetic Demo"
    assert payload["bed"] == {"ward": "General Medicine", "bed_number": "GM-12", "status": "occupied"}
    assert payload["medical_record"]["treatment_course"].startswith("IV antibiotics")
    assert payload["medications"][0]["medication_name"] == "Ceftriaxone"
    assert len(payload["vitals"]) == 5
    assert payload["vitals"][0]["recorded_at"] > payload["vitals"][1]["recorded_at"]


def test_unknown_patient_returns_404(client):
    response = client.get("/api/patients/999999")

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Patient not found"


@pytest.mark.parametrize("query", ["page=0", "page_size=0", "page_size=101"])
def test_invalid_patient_pagination_returns_422(client, query):
    response = client.get(f"/api/patients?{query}")

    assert response.status_code == 422
