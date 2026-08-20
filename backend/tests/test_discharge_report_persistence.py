from datetime import date, datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.models.admission import Admission, AdmissionStatus
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.repositories.discharge_repository import DischargeRepository
from app.services.discharge_service import DischargeService
from app.schemas.discharge_report import (
    DischargeReportCreate,
    DischargeReportEdit,
    DischargeReportRead,
)


def _load_harden_discharge_reports_migration():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "20260819_0003_harden_discharge_reports.py"
    )
    spec = spec_from_file_location("harden_discharge_reports", migration_path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _historical_discharge_reports_schema(metadata):
    return Table(
        "discharge_reports",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("patient_id", Integer, nullable=False),
        Column("admission_id", Integer, nullable=False),
        Column("generated_content", Text, nullable=False),
        Column("edited_content", Text, nullable=True),
        Column("status", String(20), nullable=False),
        Column("approved_by", Integer, nullable=True),
        Column("approved_at", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
    )


class _SQLiteSafeMigrationOperations:
    """Fails the test if the migration uses SQLite's unsupported direct ALTER path."""

    def __init__(self, operations):
        self._operations = operations

    def alter_column(self, *args, **kwargs):
        raise AssertionError("SQLite migrations must use batch_alter_table for nullable changes")

    def __getattr__(self, name):
        return getattr(self._operations, name)


def test_effective_content_prefers_doctor_edit_and_records_provenance():
    """Removing the doctor override or either provenance field must fail this test."""
    report = DischargeReport(
        patient_id=1,
        admission_id=1,
        generated_content="AI draft",
        edited_content="Doctor revision",
        generation_provider="replicate",
        generation_model="openai/gpt-5.6-luna",
    )

    assert report.generation_provider == "replicate"
    assert report.generation_model == "openai/gpt-5.6-luna"
    assert report.effective_content == "Doctor revision"


def test_effective_content_preserves_an_intentionally_empty_doctor_edit():
    report = DischargeReport(
        patient_id=1,
        admission_id=1,
        generated_content="AI draft",
        edited_content="",
        generation_provider="replicate",
        generation_model="openai/gpt-5.6-luna",
    )

    assert report.effective_content == ""


@pytest.fixture
def discharge_report(db_session):
    doctor = User(name="Dr. Ada", email="ada@example.test", role=UserRole.DOCTOR)
    patient = Patient(
        patient_code="PERSIST-001",
        first_name="Pat",
        last_name="Ient",
        date_of_birth=date(1990, 1, 1),
        gender="other",
    )
    db_session.add_all([doctor, patient])
    db_session.flush()

    admission = Admission(
        patient_id=patient.id,
        primary_diagnosis="Observation",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.DISCHARGING,
    )
    db_session.add(admission)
    db_session.flush()

    report = DischargeReport(
        patient_id=patient.id,
        admission_id=admission.id,
        generated_content="AI draft",
        generation_provider="replicate",
        generation_model="openai/gpt-5.6-luna",
        status=DischargeReportStatus.GENERATED,
    )
    db_session.add(report)
    db_session.flush()
    return report


def test_one_report_per_admission(db_session, discharge_report):
    """Dropping the admission-level unique constraint must fail this test."""
    duplicate = DischargeReport(
        patient_id=discharge_report.patient_id,
        admission_id=discharge_report.admission_id,
        generated_content="second",
        generation_provider="replicate",
        generation_model="openai/gpt-5.6-luna",
        status=DischargeReportStatus.GENERATED,
    )
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(duplicate)
            db_session.flush()


def test_generation_provider_defaults_to_replicate(db_session, discharge_report):
    """Changing the default provider must fail this test."""
    second_admission = Admission(
        patient_id=discharge_report.patient_id,
        primary_diagnosis="Follow-up observation",
        attending_doctor_id=discharge_report.admission.attending_doctor_id,
        status=AdmissionStatus.DISCHARGING,
    )
    db_session.add(second_admission)
    db_session.flush()

    report = DischargeReport(
        patient_id=discharge_report.patient_id,
        admission_id=second_admission.id,
        generated_content="AI draft",
        generation_model="openai/gpt-5.6-luna",
        status=DischargeReportStatus.GENERATED,
    )
    db_session.add(report)
    db_session.flush()

    assert report.generation_provider == "replicate"


def test_read_schema_exposes_effective_content_and_report_audit_fields(discharge_report):
    """Removing a clinician-facing provenance or audit field must fail this test."""
    discharge_report.edited_content = "Doctor revision"
    report = DischargeReportRead.model_validate(discharge_report)

    assert report.generation_provider == "replicate"
    assert report.generation_model == "openai/gpt-5.6-luna"
    assert report.effective_content == "Doctor revision"
    assert report.approving_doctor_name is None
    assert report.approved_by is None
    assert report.approved_at is None
    assert report.created_at is not None
    assert report.updated_at is not None


def test_create_and_edit_schemas_reject_status_and_approval_fields():
    """Accepting client-controlled workflow or approval state must fail this test."""
    with pytest.raises(ValidationError):
        DischargeReportCreate(
            patient_id=1,
            admission_id=2,
            generated_content="Draft",
            status="approved",
            approved_by=7,
        )

    with pytest.raises(ValidationError):
        DischargeReportEdit(
            edited_content="Doctor revision",
            status="approved",
            approved_by=7,
        )


def test_edit_schema_rejects_whitespace_only_content():
    with pytest.raises(ValidationError):
        DischargeReportEdit(edited_content=" \n\t ")


def test_repository_gets_the_report_for_an_admission(db_session, discharge_report):
    """Changing admission lookup to return a different report must fail this test."""
    found = DischargeRepository(db_session).get_by_admission_id(discharge_report.admission_id)

    assert found is not None
    assert found.id == discharge_report.id


def test_legacy_generation_persists_legacy_provenance(db_session):
    """Omitting legacy provenance from the live generation path must fail this test."""
    doctor = User(name="Dr. Legacy", email="legacy@example.test", role=UserRole.DOCTOR)
    patient = Patient(
        patient_code="LEGACY-001",
        first_name="Legacy",
        last_name="Patient",
        date_of_birth=date(1990, 1, 1),
        gender="other",
    )
    db_session.add_all([doctor, patient])
    db_session.flush()
    admission = Admission(
        patient_id=patient.id,
        primary_diagnosis="Observation",
        attending_doctor_id=doctor.id,
        status=AdmissionStatus.DISCHARGING,
    )
    db_session.add(admission)
    db_session.flush()

    report = DischargeService(db_session).create_ai_draft_report(
        patient_id=patient.id,
        admission_id=admission.id,
        generated_content="Legacy draft",
    )

    assert report.generation_provider == "legacy"
    assert report.generation_model == "legacy-placeholder"


def test_historical_sqlite_migration_backfills_and_enforces_report_contracts():
    """Removing SQLite batch alteration or the backfill/unique steps must fail this test."""
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    historical_reports = _historical_discharge_reports_schema(metadata)
    metadata.create_all(engine)
    migration = _load_harden_discharge_reports_migration()

    with engine.begin() as connection:
        connection.execute(
            historical_reports.insert().values(
                patient_id=1,
                admission_id=1,
                generated_content="Legacy draft",
                status="generated",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        migration_context = MigrationContext.configure(connection)
        migration_operations = Operations(migration_context)
        sqlite_safe_operations = _SQLiteSafeMigrationOperations(migration_operations)
        original_op = migration.op
        migration.op = sqlite_safe_operations
        try:
            migration.upgrade()
        finally:
            migration.op = original_op

        upgraded_reports = Table("discharge_reports", MetaData(), autoload_with=connection)
        legacy_row = connection.execute(select(upgraded_reports)).one()
        assert legacy_row.generation_provider == "legacy"
        assert legacy_row.generation_model == "legacy-placeholder"

        column_nullability = {
            column["name"]: column["nullable"]
            for column in inspect(connection).get_columns("discharge_reports")
        }
        assert column_nullability["generation_provider"] is False
        assert column_nullability["generation_model"] is False

        with pytest.raises(IntegrityError):
            connection.execute(
                upgraded_reports.insert().values(
                    patient_id=2,
                    admission_id=1,
                    generated_content="Duplicate draft",
                    generation_provider="legacy",
                    generation_model="legacy-placeholder",
                    status="generated",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )

        migration.op = sqlite_safe_operations
        try:
            migration.downgrade()
        finally:
            migration.op = original_op

        downgraded_columns = {
            column["name"] for column in inspect(connection).get_columns("discharge_reports")
        }
        assert "generation_provider" not in downgraded_columns
        assert "generation_model" not in downgraded_columns
        downgraded_indexes = {
            index["name"] for index in inspect(connection).get_indexes("discharge_reports")
        }
        assert "uq_discharge_reports_admission" not in downgraded_indexes
        downgraded_reports = Table("discharge_reports", MetaData(), autoload_with=connection)
        assert connection.execute(select(downgraded_reports.c.generated_content)).scalar_one() == "Legacy draft"
