"""Add discharge packages and notifications tables.

Revision ID: 20260820_0010
Revises: 20260820_0009
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa


revision = "20260820_0010"
down_revision = "20260820_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Create discharge_packages table if not exists
    if "discharge_packages" not in existing_tables:
        op.create_table(
            "discharge_packages",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("admission_id", sa.Integer(), sa.ForeignKey("admissions.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("discharge_report_id", sa.Integer(), sa.ForeignKey("discharge_reports.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("billing_clearance_id", sa.Integer(), sa.ForeignKey("billing_clearances.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("status", sa.String(50), server_default="authorized", nullable=False, index=True),
            sa.Column("clinical_snapshot", sa.JSON(), nullable=False),
            sa.Column("patient_summary", sa.JSON(), nullable=False),
            sa.Column("pdf_path", sa.String(500), nullable=True),
            sa.Column("pdf_generated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("authorized_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("authorized_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("uq_discharge_packages_admission", "discharge_packages", ["admission_id"], unique=True)

    # 2. Create notifications table if not exists
    if "notifications" not in existing_tables:
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("recipient_type", sa.String(50), server_default="patient", nullable=False, index=True),
            sa.Column("recipient_reference", sa.String(100), nullable=False, index=True),
            sa.Column("channel", sa.String(50), server_default="in_app", nullable=False, index=True),
            sa.Column("notification_type", sa.String(50), server_default="discharge_package_ready", nullable=False, index=True),
            sa.Column("status", sa.String(50), server_default="delivered", nullable=False, index=True),
            sa.Column("subject", sa.String(255), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("related_entity_type", sa.String(50), nullable=True, index=True),
            sa.Column("related_entity_id", sa.Integer(), nullable=True, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("discharge_packages")
