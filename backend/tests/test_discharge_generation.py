from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.api.dependencies.llm import get_llm_client
from app.main import app
from app.integrations.llm.client import LLMClientInterface
from app.integrations.llm.replicate_client import (
    LLMConfigurationError,
    LLMProviderError,
    LLMTimeoutError,
)
from app.models import (
    Admission,
    AdmissionStatus,
    Bed,
    BedStatus,
    ClinicalDecision,
    ClinicalDecisionStatus,
    ClinicalDecisionType,
    DischargeReport,
    DischargeReportStatus,
    MedicalRecord,
    Medication,
    Patient,
    User,
    UserRole,
    Vital,
)
from app.services.discharge_context import build_discharge_context
from app.services.discharge_service import DischargeService


DRAFT_OUTPUT = "DRAFT — REQUIRES PHYSICIAN REVIEW AND SIGN-OFF\nPrimary Diagnosis\nPneumonia"


class FakeLLMClient(LLMClientInterface):
    """A deterministic stand-in for the external provider; it never makes a network call."""

    def __init__(self, output: str = DRAFT_OUTPUT):
        self.output = output
        self.context = None

    def generate_discharge_summary(self, patient_context):
        self.context = patient_context
        return self.output


@pytest.fixture
def confirmed_discharge_case(db_session):
    doctor = User(name="Dr. Context", email="context.doctor@example.test", role=UserRole.DOCTOR)
    patient = Patient(
        patient_code="GEN-1001",
        first_name="Rae",
        last_name="Patient",
        date_of_birth=date(1985, 2, 3),
        gender="Female",
        blood_group="O+",
    )
    bed = Bed(ward="General Medicine", bed_number="G-12", status=BedStatus.OCCUPIED)
    db_session.add_all([doctor, patient, bed])
    db_session.flush()
    bed.current_patient_id = patient.id
    admission = Admission(
        patient_id=patient.id,
        admission_date=datetime(2026, 8, 10, tzinfo=timezone.utc),
        primary_diagnosis="Pneumonia",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.DISCHARGING,
        bed_id=bed.id,
    )
    db_session.add(admission)
    db_session.flush()
    decision = ClinicalDecision(
        patient_id=patient.id,
        admission_id=admission.id,
        decision_type=ClinicalDecisionType.DISCHARGE,
        reason="Stable for discharge",
        notes=None,
        decided_by=doctor.id,
        status=ClinicalDecisionStatus.CONFIRMED,
    )
    db_session.add(decision)
    db_session.flush()
    db_session.add_all([
        MedicalRecord(
            patient_id=patient.id,
            admission_id=admission.id,
            diagnosis="Pneumonia",
            treatment_course="IV antibiotics",
            notes=None,
            created_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
        ),
        MedicalRecord(
            patient_id=patient.id,
            admission_id=admission.id,
            diagnosis="Hypoxia",
            treatment_course="Oxygen therapy",
            notes="Improved",
            created_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
        ),
        Medication(
            patient_id=patient.id,
            admission_id=admission.id,
            medication_name="Amoxicillin",
            dosage="500 mg",
            frequency="Three times daily",
            route="oral",
            start_date=date(2026, 8, 11),
            end_date=None,
        ),
    ])
    recorded_at = datetime(2026, 8, 12, tzinfo=timezone.utc)
    for offset in range(6):
        db_session.add(Vital(
            patient_id=patient.id,
            admission_id=admission.id,
            temperature=36.5 + offset,
            heart_rate=70 + offset,
            blood_pressure_systolic=120 + offset,
            blood_pressure_diastolic=80 + offset,
            oxygen_saturation=98.0,
            recorded_at=recorded_at + timedelta(hours=offset),
        ))
    db_session.flush()
    return {
        "doctor": doctor,
        "patient": patient,
        "bed": bed,
        "admission": admission,
        "decision": decision,
    }


def test_context_uses_persisted_values_missing_markers_and_deterministic_order(confirmed_discharge_case):
    """Replacing missing clinical fields or changing ordered context must fail this test."""
    case = confirmed_discharge_case

    context = build_discharge_context(case["admission"], case["decision"])

    assert context["patient"]["patient_code"] == "GEN-1001"
    assert context["admission"]["primary_diagnosis"] == "Pneumonia"
    assert context["bed"] == {"ward": "General Medicine", "bed_number": "G-12"}
    assert [record["diagnosis"] for record in context["medical_records"]] == ["Hypoxia", "Pneumonia"]
    assert context["medical_records"][1]["notes"] == "Not documented"
    assert context["medications"][0]["end_date"] == "Not documented"
    assert len(context["recent_vitals"]) == 5
    assert context["recent_vitals"][0]["heart_rate"] == 75
    assert context["decision"] == {"reason": "Stable for discharge", "notes": "Not documented"}


def test_generate_report_uses_persisted_context_and_never_approves(db_session, confirmed_discharge_case):
    """Skipping context, approval defaults, or state preservation must fail this test."""
    case = confirmed_discharge_case
    fake = FakeLLMClient()

    report = DischargeService(db_session).generate_report(case["admission"].id, fake)

    assert fake.context["patient"]["patient_code"] == case["patient"].patient_code
    assert fake.context["decision"]["reason"] == "Stable for discharge"
    assert report.status == DischargeReportStatus.GENERATED
    assert report.approved_by is None
    assert report.approved_at is None
    assert report.generation_provider == "replicate"
    assert report.admission.status == AdmissionStatus.DISCHARGING
    assert report.admission.bed.status == BedStatus.OCCUPIED


def test_generation_rejects_unknown_admission_before_calling_provider(db_session):
    """Removing the existence check must fail this test."""
    fake = FakeLLMClient()

    with pytest.raises(HTTPException, match="Admission not found") as error:
        DischargeService(db_session).generate_report(999999, fake)

    assert error.value.status_code == 404
    assert fake.context is None


def test_generation_requires_discharging_admission_before_calling_provider(db_session, confirmed_discharge_case):
    """Allowing an admitted patient to generate a discharge draft must fail this test."""
    case = confirmed_discharge_case
    case["admission"].status = AdmissionStatus.ADMITTED
    fake = FakeLLMClient()

    with pytest.raises(HTTPException, match="discharging") as error:
        DischargeService(db_session).generate_report(case["admission"].id, fake)

    assert error.value.status_code == 409
    assert fake.context is None


@pytest.mark.parametrize(
    ("decision_type", "decision_status"),
    [
        (ClinicalDecisionType.TRANSFER, ClinicalDecisionStatus.CONFIRMED),
        (ClinicalDecisionType.DISCHARGE, ClinicalDecisionStatus.DRAFT),
    ],
)
def test_generation_requires_confirmed_discharge_decision(
    db_session, confirmed_discharge_case, decision_type, decision_status
):
    """Accepting a transfer or unconfirmed decision must fail this test."""
    case = confirmed_discharge_case
    case["decision"].decision_type = decision_type
    case["decision"].status = decision_status
    fake = FakeLLMClient()

    with pytest.raises(HTTPException) as error:
        DischargeService(db_session).generate_report(case["admission"].id, fake)

    assert error.value.status_code == 409
    assert fake.context is None


def test_generation_rejects_duplicate_report_before_calling_provider(db_session, confirmed_discharge_case):
    """Removing duplicate prevention must fail this test."""
    case = confirmed_discharge_case
    db_session.add(DischargeReport(
        patient_id=case["patient"].id,
        admission_id=case["admission"].id,
        generated_content="Existing draft",
        generation_provider="replicate",
        generation_model="openai/gpt-5.6-luna",
        status=DischargeReportStatus.GENERATED,
    ))
    db_session.flush()
    fake = FakeLLMClient()

    with pytest.raises(HTTPException, match="already exists") as error:
        DischargeService(db_session).generate_report(case["admission"].id, fake)

    assert error.value.status_code == 409
    assert fake.context is None


def test_generation_rolls_back_unique_admission_race_and_returns_duplicate_conflict(
    db_session, confirmed_discharge_case, monkeypatch
):
    """Letting a concurrent report insert escape as a 500 must fail this test."""
    case = confirmed_discharge_case
    rollback_called = False
    real_rollback = db_session.rollback

    def track_rollback():
        nonlocal rollback_called
        rollback_called = True
        real_rollback()

    class RaceLLMClient(LLMClientInterface):
        def generate_discharge_summary(self, patient_context):
            db_session.add(DischargeReport(
                patient_id=case["patient"].id,
                admission_id=case["admission"].id,
                generated_content="Concurrent draft",
                generation_provider="replicate",
                generation_model="openai/gpt-5.6-luna",
                status=DischargeReportStatus.GENERATED,
            ))
            db_session.flush()
            return DRAFT_OUTPUT

    monkeypatch.setattr(db_session, "rollback", track_rollback)

    with pytest.raises(HTTPException, match="already exists") as error:
        DischargeService(db_session).generate_report(case["admission"].id, RaceLLMClient())

    assert error.value.status_code == 409
    assert rollback_called is True
    assert db_session.query(DischargeReport).count() == 0


def test_generation_propagates_non_duplicate_integrity_errors(
    db_session, confirmed_discharge_case, monkeypatch
):
    """Mapping every database integrity error to a duplicate report conflict must fail this test."""
    service = DischargeService(db_session)
    original_error = IntegrityError(
        "INSERT INTO discharge_reports",
        {},
        Exception("foreign key constraint failed"),
    )

    def fail_with_unrelated_integrity_error(report):
        raise original_error

    monkeypatch.setattr(service.repo, "create", fail_with_unrelated_integrity_error)

    with pytest.raises(IntegrityError) as error:
        service.generate_report(confirmed_discharge_case["admission"].id, FakeLLMClient())

    assert error.value is original_error


def test_generation_rejects_blank_provider_output_without_persisting(db_session, confirmed_discharge_case):
    """Persisting a blank provider response must fail this test."""
    case = confirmed_discharge_case

    with pytest.raises(HTTPException, match="no content") as error:
        DischargeService(db_session).generate_report(case["admission"].id, FakeLLMClient("  \n"))

    assert error.value.status_code == 502
    assert db_session.query(DischargeReport).filter_by(admission_id=case["admission"].id).count() == 0


def test_generate_route_uses_injected_provider_and_returns_generated_report(client, confirmed_discharge_case):
    """Restoring a local template instead of the injected provider must fail this test."""
    fake = FakeLLMClient()
    app.dependency_overrides[get_llm_client] = lambda: fake

    response = client.post(f"/api/discharge/generate/{confirmed_discharge_case['admission'].id}")

    assert response.status_code == 201
    assert response.json()["generated_content"] == DRAFT_OUTPUT
    assert response.json()["generation_provider"] == "replicate"
    assert fake.context["decision"]["reason"] == "Stable for discharge"


@pytest.mark.parametrize(
    ("provider_error", "expected_status", "expected_message"),
    [
        (LLMConfigurationError("missing token"), 503, "AI generation is not configured"),
        (LLMTimeoutError("timeout"), 504, "AI generation timed out"),
        (LLMProviderError("provider rejected request"), 502, "AI generation failed"),
    ],
)
def test_generate_route_maps_provider_errors_without_exposing_provider_details(
    client, confirmed_discharge_case, provider_error, expected_status, expected_message
):
    """Leaking provider details or returning the wrong gateway error must fail this test."""
    class FailingLLMClient(LLMClientInterface):
        def generate_discharge_summary(self, patient_context):
            raise provider_error

    app.dependency_overrides[get_llm_client] = FailingLLMClient

    response = client.post(f"/api/discharge/generate/{confirmed_discharge_case['admission'].id}")

    assert response.status_code == expected_status
    assert response.json()["error"]["message"] == expected_message
    assert "token" not in response.text
    assert "provider rejected request" not in response.text


def test_get_report_by_admission_returns_current_report(client, db_session, confirmed_discharge_case):
    """Returning a different admission's report or treating a missing report as success must fail."""
    case = confirmed_discharge_case
    report = DischargeService(db_session).generate_report(case["admission"].id, FakeLLMClient())

    found = client.get(f"/api/discharge/admissions/{case['admission'].id}/report")
    missing = client.get("/api/discharge/admissions/999999/report")

    assert found.status_code == 200
    assert found.json()["id"] == report.id
    assert missing.status_code == 404
