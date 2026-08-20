from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Admission, AdmissionStatus, Bed, BedStatus, Patient, User, UserRole


BACKEND_ROOT = Path(__file__).resolve().parents[1]
INDEX_NAME = "uq_admissions_active_bed"


def _config(database_url):
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option(
        "version_locations", str(BACKEND_ROOT / "alembic" / "versions")
    )
    config.set_main_option("prepend_sys_path", str(BACKEND_ROOT))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _database(tmp_path, monkeypatch, name):
    database_url = f"sqlite:///{tmp_path / f'{name}.sqlite'}"
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)
    config = _config(database_url)
    command.upgrade(config, "20260819_0004")
    return database_url, config, sa.create_engine(database_url)


def _people(session, suffix):
    doctor = User(
        name=f"Dr Migration {suffix}",
        email=f"migration-{suffix}@test.invalid",
        role=UserRole.DOCTOR,
    )
    patients = [
        Patient(
            patient_code=f"MIG-{suffix}-{index}",
            first_name="Migration",
            last_name=str(index),
            date_of_birth=date(1980, 1, index + 1),
            gender="Other",
        )
        for index in range(3)
    ]
    session.add_all([doctor, *patients])
    session.flush()
    return doctor, patients


def _active_admission(session, doctor, patient, bed_id, suffix, status=AdmissionStatus.ADMITTED):
    admission = Admission(
        patient_id=patient.id,
        admission_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        primary_diagnosis=f"Migration {suffix}",
        attending_doctor_id=doctor.id,
        status=status,
        bed_id=bed_id,
    )
    session.add(admission)
    session.flush()
    return admission


def _snapshot(engine):
    with engine.connect() as connection:
        beds = connection.execute(sa.text(
            "SELECT id, status, current_patient_id FROM beds ORDER BY id"
        )).all()
        admissions = connection.execute(sa.text(
            "SELECT id, patient_id, status, bed_id FROM admissions ORDER BY id"
        )).all()
    return [tuple(row) for row in beds], [tuple(row) for row in admissions]


def _insert_mismatch(engine, case):
    if case.endswith("duplicate"):
        with engine.begin() as connection:
            connection.execute(sa.text(f"DROP INDEX {INDEX_NAME}"))

    with Session(engine) as session:
        doctor, patients = _people(session, case)
        if case == "active_missing_bed":
            _active_admission(session, doctor, patients[0], 999999, case)
            session.commit()
            return

        status_name, violation = case.split("_", 1)
        status = {
            "available": BedStatus.AVAILABLE,
            "cleaning": BedStatus.CLEANING,
            "occupied": BedStatus.OCCUPIED,
            "vacating": BedStatus.VACATING,
            "reserved": BedStatus.RESERVED,
        }[status_name]
        current_patient_id = {
            "active": None,
            "assigned": patients[0].id,
            "no_owner": patients[0].id,
            "null_current": None,
            "mismatch": patients[1].id,
            "duplicate": patients[0].id,
        }[violation]
        bed = Bed(
            ward="Migration Preflight",
            bed_number=f"P-{case}",
            status=status,
            current_patient_id=current_patient_id,
        )
        session.add(bed)
        session.flush()

        if violation not in {"assigned", "no_owner"}:
            _active_admission(session, doctor, patients[0], bed.id, case)
        if violation == "duplicate":
            _active_admission(
                session,
                doctor,
                patients[1],
                bed.id,
                f"{case}-second",
                AdmissionStatus.DISCHARGING,
            )
        session.commit()


@pytest.mark.parametrize(
    "case",
    [
        "active_missing_bed",
        "available_active",
        "cleaning_active",
        "available_assigned",
        "cleaning_assigned",
        "occupied_no_owner",
        "vacating_no_owner",
        "occupied_null_current",
        "vacating_null_current",
        "occupied_mismatch",
        "vacating_mismatch",
        "occupied_duplicate",
        "vacating_duplicate",
        "reserved_mismatch",
    ],
)
def test_preflight_fails_closed_for_every_legacy_ownership_mismatch(
    tmp_path, monkeypatch, case,
):
    """Allowing any cross-table mismatch through upgrade risks false bed availability."""
    _database_url, config, engine = _database(tmp_path, monkeypatch, case)
    try:
        _insert_mismatch(engine, case)
        before = _snapshot(engine)

        with pytest.raises(RuntimeError, match="Bed ownership preflight failed"):
            command.upgrade(config, "head")

        with engine.connect() as connection:
            assert connection.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).scalar_one() == "20260819_0004"
        assert _snapshot(engine) == before
    finally:
        engine.dispose()


def _insert_valid_legacy_state(engine):
    with Session(engine) as session:
        doctor, patients = _people(session, "valid")
        available = Bed(
            ward="Migration Preflight", bed_number="V-AVAILABLE",
            status=BedStatus.AVAILABLE, current_patient_id=None,
        )
        cleaning = Bed(
            ward="Migration Preflight", bed_number="V-CLEANING",
            status=BedStatus.CLEANING, current_patient_id=None,
        )
        occupied = Bed(
            ward="Migration Preflight", bed_number="V-OCCUPIED",
            status=BedStatus.OCCUPIED, current_patient_id=patients[0].id,
        )
        vacating = Bed(
            ward="Migration Preflight", bed_number="V-VACATING",
            status=BedStatus.VACATING, current_patient_id=patients[1].id,
        )
        reserved = Bed(
            ward="Migration Preflight", bed_number="V-RESERVED",
            status=BedStatus.RESERVED, current_patient_id=None,
        )
        session.add_all([available, cleaning, occupied, vacating, reserved])
        session.flush()
        _active_admission(session, doctor, patients[0], occupied.id, "valid-occupied")
        _active_admission(
            session,
            doctor,
            patients[1],
            vacating.id,
            "valid-vacating",
            AdmissionStatus.DISCHARGING,
        )
        session.add(Admission(
            patient_id=patients[2].id,
            admission_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
            primary_diagnosis="Preserved historical discharge",
            attending_doctor_id=doctor.id,
            status=AdmissionStatus.DISCHARGED,
            bed_id=available.id,
        ))
        session.commit()


def _assert_expected_index(engine):
    index = {
        item["name"]: item for item in sa.inspect(engine).get_indexes("admissions")
    }[INDEX_NAME]
    assert index["unique"] == 1
    assert index["column_names"] == ["bed_id"]
    predicate = str(index["dialect_options"]["sqlite_where"]).lower()
    assert "bed_id is not null" in predicate
    assert "status in" in predicate
    for status_value in (
        "admitted", "discharging", "transfer_pending",
    ):
        assert status_value in predicate


def test_valid_legacy_database_upgrades_in_place_without_rewriting_history(
    tmp_path, monkeypatch,
):
    """A valid upgrade must preserve every clinical row and assignment verbatim."""
    _database_url, config, engine = _database(tmp_path, monkeypatch, "valid")
    try:
        _insert_valid_legacy_state(engine)
        before = _snapshot(engine)

        command.upgrade(config, "head")

        assert _snapshot(engine) == before
        with engine.connect() as connection:
            assert connection.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).scalar_one().startswith("2026")
        _assert_expected_index(engine)
    finally:
        engine.dispose()


def test_preflight_recreates_a_missing_active_owner_index_correctly(
    tmp_path, monkeypatch,
):
    """Silently completing without the partial uniqueness guard must fail."""
    _database_url, config, engine = _database(tmp_path, monkeypatch, "missing-index")
    try:
        _insert_valid_legacy_state(engine)
        with engine.begin() as connection:
            connection.execute(sa.text(f"DROP INDEX {INDEX_NAME}"))

        command.upgrade(config, "head")

        _assert_expected_index(engine)
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "index_sql",
    [
        f"CREATE INDEX {INDEX_NAME} ON admissions (patient_id)",
        f"CREATE UNIQUE INDEX {INDEX_NAME} ON admissions (bed_id)",
        (
            f"CREATE UNIQUE INDEX {INDEX_NAME} ON admissions (bed_id) "
            "WHERE bed_id IS NOT NULL AND status = 'DISCHARGED'"
        ),
    ],
)
def test_preflight_rejects_a_named_index_with_wrong_contract(
    tmp_path, monkeypatch, index_sql,
):
    """Name-only index checks must not accept wrong uniqueness, column, or predicate."""
    suffix = str(abs(hash(index_sql)))
    _database_url, config, engine = _database(tmp_path, monkeypatch, f"wrong-index-{suffix}")
    try:
        _insert_valid_legacy_state(engine)
        with engine.begin() as connection:
            connection.execute(sa.text(f"DROP INDEX {INDEX_NAME}"))
            connection.execute(sa.text(index_sql))

        with pytest.raises(RuntimeError, match="active-owner index contract"):
            command.upgrade(config, "head")

        with engine.connect() as connection:
            assert connection.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).scalar_one() == "20260819_0004"
    finally:
        engine.dispose()
