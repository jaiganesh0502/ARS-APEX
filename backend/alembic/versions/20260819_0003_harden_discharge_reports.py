"""Harden discharge report provenance and admission uniqueness.

Revision ID: 20260819_0003
Revises: 20260819_0002
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa


revision = "20260819_0003"
down_revision = "20260819_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    column_names = {column["name"] for column in inspector.get_columns("discharge_reports")}

    if "generation_provider" not in column_names:
        op.add_column(
            "discharge_reports",
            sa.Column("generation_provider", sa.String(length=40), nullable=True),
        )
    if "generation_model" not in column_names:
        op.add_column(
            "discharge_reports",
            sa.Column("generation_model", sa.String(length=160), nullable=True),
        )

    op.execute(
        "UPDATE discharge_reports "
        "SET generation_provider = 'legacy', generation_model = 'legacy-placeholder' "
        "WHERE generation_provider IS NULL"
    )

    inspector = sa.inspect(bind)
    columns = {
        column["name"]: column
        for column in inspector.get_columns("discharge_reports")
    }
    nullable_provenance_columns = [
        ("generation_provider", sa.String(length=40)),
        ("generation_model", sa.String(length=160)),
    ]
    nullable_provenance_columns = [
        (name, column_type)
        for name, column_type in nullable_provenance_columns
        if columns[name]["nullable"]
    ]
    if bind.dialect.name == "sqlite" and nullable_provenance_columns:
        with op.batch_alter_table("discharge_reports") as batch_op:
            for name, column_type in nullable_provenance_columns:
                batch_op.alter_column(name, existing_type=column_type, nullable=False)
    else:
        for name, column_type in nullable_provenance_columns:
            op.alter_column(
                "discharge_reports",
                name,
                existing_type=column_type,
                nullable=False,
            )

    inspector = sa.inspect(bind)
    index_names = {index["name"] for index in inspector.get_indexes("discharge_reports")}
    if "uq_discharge_reports_admission" not in index_names:
        op.create_index(
            "uq_discharge_reports_admission",
            "discharge_reports",
            ["admission_id"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index("uq_discharge_reports_admission", table_name="discharge_reports")
    op.drop_column("discharge_reports", "generation_model")
    op.drop_column("discharge_reports", "generation_provider")
