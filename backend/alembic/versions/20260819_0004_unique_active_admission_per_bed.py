"""Enforce one active admission owner per bed.

Revision ID: 20260819_0004
Revises: 20260819_0003
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa


revision = "20260819_0004"
down_revision = "20260819_0003"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_admissions_active_bed"
ACTIVE_OWNER_PREDICATE = (
    "bed_id IS NOT NULL AND status IN ("
    "'ADMITTED', 'DISCHARGING', 'TRANSFER_PENDING', "
    "'admitted', 'discharging', 'transfer_pending'"
    ")"
)


def upgrade() -> None:
    bind = op.get_bind()
    index_names = {
        index["name"] for index in sa.inspect(bind).get_indexes("admissions")
    }
    if INDEX_NAME in index_names:
        return

    duplicate = bind.execute(sa.text(
        "SELECT bed_id, COUNT(*) AS owner_count "
        "FROM admissions "
        f"WHERE {ACTIVE_OWNER_PREDICATE} "
        "GROUP BY bed_id HAVING COUNT(*) > 1 "
        "ORDER BY bed_id LIMIT 1"
    )).first()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot enforce one active admission per bed: "
            f"duplicate active admissions reference bed {duplicate.bed_id}"
        )

    predicate = sa.text(ACTIVE_OWNER_PREDICATE)
    op.create_index(
        INDEX_NAME,
        "admissions",
        ["bed_id"],
        unique=True,
        postgresql_where=predicate,
        sqlite_where=predicate,
    )


def downgrade() -> None:
    bind = op.get_bind()
    index_names = {
        index["name"] for index in sa.inspect(bind).get_indexes("admissions")
    }
    if INDEX_NAME in index_names:
        op.drop_index(INDEX_NAME, table_name="admissions")
