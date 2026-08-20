from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Admission, AdmissionStatus, Bed, BedStatus, Patient, User, UserRole


BACKEND_ROOT = Path(__file__).resolve().parents[1]
INDEX_NAME = "uq_admissions_active_bed"


def _config(database_url):
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("version_locations", str(BACKEND_ROOT / "alembic" / "versions"))
    config.set_main_option("prepend_sys_path", str(BACKEND_ROOT))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _revision(connection):
    return connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()


def _migration_fixture_rows(engine, duplicate_active=False):
    with Session(engine) as session:
        doctor = User(name="Migration Doctor", email="migration-owner@test.invalid", role=UserRole.DOCTOR)
        patients = [
            Patient(
                patient_code=f"MIG-{index}",
                first_name="Migration",
                last_name=str(index),
                date_of_birth=date(1980, 1, index),
                gender="Other",
            )
            for index in range(1, 6)
        ]
        bed = Bed(ward="Migration Ward", bed_number="M-01", status=BedStatus.OCCUPIED)
        session.add_all([doctor, bed, *patients])
        session.flush()
        bed.current_patient_id = patients[2].id
        admissions = [
            Admission(
                patient_id=patients[0].id,
                admission_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
                primary_diagnosis="Historical discharge",
                attending_doctor_id=doctor.id,
                status=AdmissionStatus.DISCHARGED,
                bed_id=bed.id,
            ),
            Admission(
                patient_id=patients[1].id,
                admission_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
                primary_diagnosis="Historical transfer",
                attending_doctor_id=doctor.id,
                status=AdmissionStatus.TRANSFERRED,
                bed_id=bed.id,
            ),
            Admission(
                patient_id=patients[2].id,
                admission_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
                primary_diagnosis="Active owner",
                attending_doctor_id=doctor.id,
                status=AdmissionStatus.ADMITTED,
                bed_id=bed.id,
            ),
        ]
        if duplicate_active:
            admissions.append(Admission(
                patient_id=patients[3].id,
                admission_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
                primary_diagnosis="Duplicate active owner",
                attending_doctor_id=doctor.id,
                status=AdmissionStatus.DISCHARGING,
                bed_id=bed.id,
            ))
        session.add_all(admissions)
        session.commit()
        return bed.id, patients[4].id, doctor.id


def test_in_place_migration_preserves_history_and_enforces_one_active_owner(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'active-owner.sqlite'}"
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)
    config = _config(database_url)
    command.upgrade(config, "20260819_0003")
    engine = sa.create_engine(database_url)
    try:
        assert INDEX_NAME not in {item["name"] for item in sa.inspect(engine).get_indexes("admissions")}
        bed_id, unused_patient_id, doctor_id = _migration_fixture_rows(engine)

        command.upgrade(config, "head")

        with engine.connect() as connection:
            assert _revision(connection).startswith("2026")
        indexes = {item["name"]: item for item in sa.inspect(engine).get_indexes("admissions")}
        assert indexes[INDEX_NAME]["unique"] == 1

        with Session(engine) as session:
            assert session.query(Admission).filter(Admission.bed_id == bed_id).count() == 3
            session.add(Admission(
                patient_id=unused_patient_id,
                admission_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
                primary_diagnosis="Losing active owner",
                attending_doctor_id=doctor_id,
                status=AdmissionStatus.TRANSFER_PENDING,
                bed_id=bed_id,
            ))
            with pytest.raises(IntegrityError):
                session.commit()
    finally:
        engine.dispose()


def test_migration_fails_closed_without_deleting_legacy_duplicate_active_owners(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'duplicate-owner.sqlite'}"
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)
    config = _config(database_url)
    command.upgrade(config, "20260819_0003")
    engine = sa.create_engine(database_url)
    try:
        bed_id, _unused_patient_id, _doctor_id = _migration_fixture_rows(engine, duplicate_active=True)

        with pytest.raises(RuntimeError, match="duplicate active admissions"):
            command.upgrade(config, "head")

        with engine.connect() as connection:
            assert _revision(connection) == "20260819_0003"
        with Session(engine) as session:
            owners = session.query(Admission).filter(
                Admission.bed_id == bed_id,
                Admission.status.in_([
                    AdmissionStatus.ADMITTED,
                    AdmissionStatus.DISCHARGING,
                    AdmissionStatus.TRANSFER_PENDING,
                ]),
            ).all()
            assert len(owners) == 2
        assert INDEX_NAME not in {item["name"] for item in sa.inspect(engine).get_indexes("admissions")}
    finally:
        engine.dispose()
