"""Initial application schema.

Revision ID: 20260819_0001
Revises:
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa

from app.db.base import Base

revision = "20260819_0001"
down_revision = None
branch_labels = None
depends_on = None


def _baseline_tables() -> tuple[sa.MetaData, list]:
    """Copy of Base.metadata's tables, excluding clinical_decisions (created in
    20260819_0002, which does not exist yet at this point in the chain) and,
    on transfers, its FK to clinical_decisions.id -- 20260819_0002 adds that FK
    back once the referenced table exists.
    """
    temp_metadata = sa.MetaData()
    tables = []
    for name, table in Base.metadata.tables.items():
        if name == "clinical_decisions":
            continue
        if name == "transfers":
            # clinical_decisions isn't copied into temp_metadata above, so
            # tometadata() can't resolve this FK's target table. Identify it
            # by target name (string) before copying, then strip it from the
            # copy -- 20260819_0002 adds it back once clinical_decisions exists.
            source_fk_col = table.c.clinical_decision_id
            target_fks = [
                fk for fk in source_fk_col.foreign_keys
                if fk.target_fullname == "clinical_decisions.id"
            ]
            copied = table.tometadata(temp_metadata)
            fk_col = copied.c.clinical_decision_id
            for fk in list(fk_col.foreign_keys):
                if fk.target_fullname == "clinical_decisions.id":
                    fk_col.foreign_keys.discard(fk)
                    copied.foreign_keys.discard(fk)
                    if fk.constraint is not None:
                        copied.constraints.discard(fk.constraint)
            assert target_fks, "expected transfers.clinical_decision_id to reference clinical_decisions.id"
        else:
            copied = table.tometadata(temp_metadata)
        tables.append(copied)
    return temp_metadata, tables


def upgrade() -> None:
    temp_metadata, tables = _baseline_tables()
    temp_metadata.create_all(bind=op.get_bind(), tables=tables)


def downgrade() -> None:
    temp_metadata, tables = _baseline_tables()
    temp_metadata.drop_all(bind=op.get_bind(), tables=tables)
