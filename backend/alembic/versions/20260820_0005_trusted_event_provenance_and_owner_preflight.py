"""Add trusted workflow-event provenance and ownership preflight.

Revision ID: 20260819_0005
Revises: 20260819_0004
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa


revision = "20260819_0005"
down_revision = "20260819_0004"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_admissions_active_bed"
ACTIVE_OWNER_PREDICATE = (
    "bed_id IS NOT NULL AND status IN ("
    "'ADMITTED', 'DISCHARGING', 'TRANSFER_PENDING', "
    "'admitted', 'discharging', 'transfer_pending'"
    ")"
)
ACTIVE_STATUS_VALUES = (
    "'ADMITTED', 'DISCHARGING', 'TRANSFER_PENDING', "
    "'admitted', 'discharging', 'transfer_pending'"
)


def _fail(message: str) -> None:
    raise RuntimeError(f"Bed ownership preflight failed: {message}")


def _preflight_owner_invariants(bind) -> None:
    missing_bed = bind.execute(sa.text(
        "SELECT a.id AS admission_id, a.bed_id AS bed_id "
        "FROM admissions AS a "
        "LEFT JOIN beds AS b ON b.id = a.bed_id "
        "WHERE a.bed_id IS NOT NULL "
        f"AND a.status IN ({ACTIVE_STATUS_VALUES}) "
        "AND b.id IS NULL "
        "ORDER BY a.id LIMIT 1"
    )).first()
    if missing_bed is not None:
        _fail(
            f"active admission {missing_bed.admission_id} references missing bed "
            f"{missing_bed.bed_id}"
        )

    available_or_cleaning = bind.execute(sa.text(
        "SELECT b.id AS bed_id, b.status AS bed_status, "
        "b.current_patient_id AS current_patient_id, COUNT(a.id) AS owner_count "
        "FROM beds AS b "
        "LEFT JOIN admissions AS a ON a.bed_id = b.id "
        f"AND a.status IN ({ACTIVE_STATUS_VALUES}) "
        "WHERE b.status IN ('AVAILABLE', 'CLEANING', 'available', 'cleaning') "
        "GROUP BY b.id, b.status, b.current_patient_id "
        "HAVING b.current_patient_id IS NOT NULL OR COUNT(a.id) <> 0 "
        "ORDER BY b.id LIMIT 1"
    )).first()
    if available_or_cleaning is not None:
        _fail(
            "available/cleaning bed "
            f"{available_or_cleaning.bed_id} has current_patient_id "
            f"{available_or_cleaning.current_patient_id!r} and "
            f"{available_or_cleaning.owner_count} active admissions"
        )

    occupied_or_vacating = bind.execute(sa.text(
        "SELECT b.id AS bed_id, b.status AS bed_status, "
        "b.current_patient_id AS current_patient_id, COUNT(a.id) AS owner_count, "
        "SUM(CASE WHEN a.patient_id = b.current_patient_id THEN 1 ELSE 0 END) "
        "AS matching_owner_count "
        "FROM beds AS b "
        "LEFT JOIN admissions AS a ON a.bed_id = b.id "
        f"AND a.status IN ({ACTIVE_STATUS_VALUES}) "
        "WHERE b.status IN ('OCCUPIED', 'VACATING', 'occupied', 'vacating') "
        "GROUP BY b.id, b.status, b.current_patient_id "
        "HAVING b.current_patient_id IS NULL OR COUNT(a.id) <> 1 "
        "OR SUM(CASE WHEN a.patient_id = b.current_patient_id THEN 1 ELSE 0 END) <> 1 "
        "ORDER BY b.id LIMIT 1"
    )).first()
    if occupied_or_vacating is not None:
        _fail(
            "occupied/vacating bed "
            f"{occupied_or_vacating.bed_id} has current_patient_id "
            f"{occupied_or_vacating.current_patient_id!r}, "
            f"{occupied_or_vacating.owner_count} active admissions, and "
            f"{occupied_or_vacating.matching_owner_count} matching owners"
        )

    mismatched_active = bind.execute(sa.text(
        "SELECT a.id AS admission_id, a.patient_id AS admission_patient_id, "
        "b.id AS bed_id, b.current_patient_id AS bed_patient_id "
        "FROM admissions AS a "
        "JOIN beds AS b ON b.id = a.bed_id "
        "WHERE a.bed_id IS NOT NULL "
        f"AND a.status IN ({ACTIVE_STATUS_VALUES}) "
        "AND (b.current_patient_id IS NULL OR b.current_patient_id <> a.patient_id) "
        "ORDER BY a.id LIMIT 1"
    )).first()
    if mismatched_active is not None:
        _fail(
            f"active admission {mismatched_active.admission_id} patient "
            f"{mismatched_active.admission_patient_id} does not match bed "
            f"{mismatched_active.bed_id} current patient "
            f"{mismatched_active.bed_patient_id!r}"
        )

    duplicate_active = bind.execute(sa.text(
        "SELECT bed_id, COUNT(*) AS owner_count FROM admissions "
        f"WHERE {ACTIVE_OWNER_PREDICATE} "
        "GROUP BY bed_id HAVING COUNT(*) > 1 ORDER BY bed_id LIMIT 1"
    )).first()
    if duplicate_active is not None:
        _fail(
            f"bed {duplicate_active.bed_id} has "
            f"{duplicate_active.owner_count} active admissions"
        )


def _index_has_expected_contract(bind, index: dict) -> bool:
    if not index.get("unique") or index.get("column_names") != ["bed_id"]:
        return False

    dialect_name = bind.dialect.name
    where_clause = index.get("dialect_options", {}).get(
        f"{dialect_name}_where"
    )
    if where_clause is None:
        return False

    predicate = " ".join(str(where_clause).lower().split())
    if (
        "bed_id is not null" not in predicate
        or "status" not in predicate
        or " and " not in predicate
        or (" in " not in predicate and "any" not in predicate)
    ):
        return False
    return all(
        predicate.count(status_value) >= 2
        for status_value in ("admitted", "discharging", "transfer_pending")
    )


def _ensure_active_owner_index(bind) -> None:
    indexes = {
        index["name"]: index
        for index in sa.inspect(bind).get_indexes("admissions")
    }
    existing = indexes.get(INDEX_NAME)
    if existing is not None:
        if not _index_has_expected_contract(bind, existing):
            raise RuntimeError(
                "Bed ownership preflight failed: active-owner index contract "
                f"for {INDEX_NAME} is invalid"
            )
        return

    predicate = sa.text(ACTIVE_OWNER_PREDICATE)
    op.create_index(
        INDEX_NAME,
        "admissions",
        ["bed_id"],
        unique=True,
        postgresql_where=predicate,
        sqlite_where=predicate,
    )


def upgrade() -> None:
    bind = op.get_bind()
    _preflight_owner_invariants(bind)
    _ensure_active_owner_index(bind)
    columns = {
        column["name"] for column in sa.inspect(bind).get_columns("workflow_events")
    }
    if "trusted_provenance" not in columns:
        op.add_column(
            "workflow_events",
            sa.Column(
                "trusted_provenance",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {
        column["name"] for column in sa.inspect(bind).get_columns("workflow_events")
    }
    if "trusted_provenance" in columns:
        op.drop_column("workflow_events", "trusted_provenance")
