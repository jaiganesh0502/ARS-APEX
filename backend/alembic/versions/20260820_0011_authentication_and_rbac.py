"""Add authentication and RBAC fields to users table.

Revision ID: 20260820_0011
Revises: 20260820_0010
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa


revision = "20260820_0011"
down_revision = "20260820_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("users")]

    if "password_hash" not in columns:
        op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))

    if "is_active" not in columns:
        op.add_column("users", sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False))

    if "patient_id" not in columns:
        op.add_column("users", sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True))
        op.create_index("ix_users_patient_id", "users", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_users_patient_id", table_name="users")
    op.drop_column("users", "patient_id")
    op.drop_column("users", "is_active")
    op.drop_column("users", "password_hash")
