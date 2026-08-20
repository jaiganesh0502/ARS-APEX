"""Initial application schema.

Revision ID: 20260819_0001
Revises:
Create Date: 2026-08-19
"""

from alembic import op

from app.db.base import Base

revision = "20260819_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    baseline_tables = [table for name, table in Base.metadata.tables.items() if name != "clinical_decisions"]
    Base.metadata.create_all(bind=op.get_bind(), tables=baseline_tables)


def downgrade() -> None:
    baseline_tables = [table for name, table in Base.metadata.tables.items() if name != "clinical_decisions"]
    Base.metadata.drop_all(bind=op.get_bind(), tables=baseline_tables)
