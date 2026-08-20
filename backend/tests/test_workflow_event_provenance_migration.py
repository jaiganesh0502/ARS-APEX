import json
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.core.config import settings


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _config(database_url):
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option(
        "version_locations", str(BACKEND_ROOT / "alembic" / "versions")
    )
    config.set_main_option("prepend_sys_path", str(BACKEND_ROOT))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_in_place_migration_marks_legacy_workflow_events_untrusted(
    tmp_path, monkeypatch,
):
    """Leaving a pre-existing row trusted after upgrade would revive forged history."""
    database_url = f"sqlite:///{tmp_path / 'workflow-provenance.sqlite'}"
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)
    config = _config(database_url)
    command.upgrade(config, "20260819_0004")
    engine = sa.create_engine(database_url)
    try:
        columns = {column["name"] for column in sa.inspect(engine).get_columns("workflow_events")}
        if "trusted_provenance" in columns:
            with engine.begin() as connection:
                connection.execute(sa.text(
                    "ALTER TABLE workflow_events DROP COLUMN trusted_provenance"
                ))

        with engine.begin() as connection:
            result = connection.execute(
                sa.text(
                    "INSERT INTO workflow_events "
                    "(event_type, entity_type, entity_id, payload, status, created_at) "
                    "VALUES (:event_type, :entity_type, :entity_id, :payload, "
                    ":status, CURRENT_TIMESTAMP)"
                ),
                {
                    "event_type": "bed_release_started",
                    "entity_type": "bed",
                    "entity_id": 404,
                    "payload": json.dumps({"bed_id": 404}),
                    "status": "pending",
                },
            )
            legacy_id = result.lastrowid

        command.upgrade(config, "head")

        columns = {column["name"] for column in sa.inspect(engine).get_columns("workflow_events")}
        assert "trusted_provenance" in columns
        with engine.connect() as connection:
            assert connection.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).scalar_one().startswith("2026")
            row = connection.execute(
                sa.text(
                    "SELECT event_type, entity_id, trusted_provenance "
                    "FROM workflow_events WHERE id = :legacy_id"
                ),
                {"legacy_id": legacy_id},
            ).one()
        assert (row.event_type, row.entity_id) == ("bed_release_started", 404)
        assert row.trusted_provenance in (False, 0)
    finally:
        engine.dispose()
