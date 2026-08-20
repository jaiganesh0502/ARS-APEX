"""Add transfer packets and decisions tables.

Revision ID: 20260820_0007
Revises: 20260820_0006
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa


revision = "20260820_0007"
down_revision = "20260820_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "transfer_packets" not in tables:
        op.create_table(
            "transfer_packets",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("transfer_id", sa.Integer(), sa.ForeignKey("transfers.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("admission_id", sa.Integer(), sa.ForeignKey("admissions.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("packet_content", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(50), server_default="prepared", nullable=False, index=True),
            sa.Column("prepared_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )

    if "transfer_decisions" not in tables:
        op.create_table(
            "transfer_decisions",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("transfer_id", sa.Integer(), sa.ForeignKey("transfers.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("decision", sa.String(50), nullable=False, index=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("decided_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
            sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "transfer_decisions" in tables:
        op.drop_table("transfer_decisions")
    if "transfer_packets" in tables:
        op.drop_table("transfer_packets")
