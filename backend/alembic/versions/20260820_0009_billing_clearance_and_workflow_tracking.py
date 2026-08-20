"""Add billing clearances table and workflow event tracking fields.

Revision ID: 20260820_0009
Revises: 20260820_0008
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa


revision = "20260820_0009"
down_revision = "20260820_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Create billing_clearances table if not exists
    if "billing_clearances" not in existing_tables:
        op.create_table(
            "billing_clearances",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False, index=True),
            sa.Column("admission_id", sa.Integer(), sa.ForeignKey("admissions.id"), nullable=False, index=True),
            sa.Column("transfer_id", sa.Integer(), sa.ForeignKey("transfers.id"), nullable=True, index=True),
            sa.Column("discharge_report_id", sa.Integer(), sa.ForeignKey("discharge_reports.id"), nullable=True, index=True),
            sa.Column("status", sa.String(50), server_default="pending", nullable=False, index=True),
            sa.Column("total_amount", sa.Numeric(10, 2), nullable=True),
            sa.Column("amount_paid", sa.Numeric(10, 2), nullable=True),
            sa.Column("outstanding_amount", sa.Numeric(10, 2), nullable=True),
            sa.Column("clearance_reference", sa.String(100), nullable=True, index=True),
            sa.Column("confirmed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deferred", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # 2. Add delivery and orchestration columns to workflow_events
    if "workflow_events" in existing_tables:
        wf_cols = {col["name"] for col in inspector.get_columns("workflow_events")}
        cols_to_add = [
            ("delivery_status", sa.Column("delivery_status", sa.String(30), server_default="pending", nullable=False)),
            ("orchestration_status", sa.Column("orchestration_status", sa.String(30), server_default="pending", nullable=False)),
            ("attempt_count", sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False)),
            ("last_attempt_at", sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True)),
            ("delivered_at", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True)),
            ("last_error", sa.Column("last_error", sa.String(1000), nullable=True)),
        ]
        for col_name, col_obj in cols_to_add:
            if col_name not in wf_cols:
                op.add_column("workflow_events", col_obj)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "workflow_events" in existing_tables:
        wf_cols = {col["name"] for col in inspector.get_columns("workflow_events")}
        cols_to_drop = [
            "delivery_status",
            "orchestration_status",
            "attempt_count",
            "last_attempt_at",
            "delivered_at",
            "last_error",
        ]
        for col_name in cols_to_drop:
            if col_name in wf_cols:
                op.drop_column("workflow_events", col_name)

    if "billing_clearances" in existing_tables:
        op.drop_table("billing_clearances")
