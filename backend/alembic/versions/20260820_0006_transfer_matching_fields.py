"""Add transfer matching fields.

Revision ID: 20260820_0006
Revises: 20260819_0005
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa


revision = "20260820_0006"
down_revision = "20260819_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("transfers")}

    if "clinical_decision_id" not in columns:
        op.add_column(
            "transfers",
            sa.Column(
                "clinical_decision_id",
                sa.Integer(),
                sa.ForeignKey("clinical_decisions.id", ondelete="RESTRICT"),
                nullable=True,
            ),
        )
        op.create_index("ix_transfers_clinical_decision_id", "transfers", ["clinical_decision_id"])

    if "requested_by" not in columns:
        op.add_column(
            "transfers",
            sa.Column(
                "requested_by",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="RESTRICT"),
                nullable=True,
            ),
        )

    if "selected_hospital_at" not in columns:
        op.add_column(
            "transfers",
            sa.Column("selected_hospital_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "rejected_at" not in columns:
        op.add_column(
            "transfers",
            sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "created_at" not in columns:
        op.add_column(
            "transfers",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )

    if "updated_at" not in columns:
        op.add_column(
            "transfers",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("transfers")}

    if "clinical_decision_id" in columns:
        op.drop_index("ix_transfers_clinical_decision_id", table_name="transfers")
        op.drop_column("transfers", "clinical_decision_id")
    if "requested_by" in columns:
        op.drop_column("transfers", "requested_by")
    if "selected_hospital_at" in columns:
        op.drop_column("transfers", "selected_hospital_at")
    if "rejected_at" in columns:
        op.drop_column("transfers", "rejected_at")
    if "created_at" in columns:
        op.drop_column("transfers", "created_at")
    if "updated_at" in columns:
        op.drop_column("transfers", "updated_at")
