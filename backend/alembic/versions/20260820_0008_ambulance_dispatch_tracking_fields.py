"""Add ambulance dispatch tracking fields.

Revision ID: 20260820_0008
Revises: 20260820_0007
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa


revision = "20260820_0008"
down_revision = "20260820_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("ambulance_dispatches")}

    cols_to_add = [
        ("dispatch_reference", sa.Column("dispatch_reference", sa.String(64), nullable=True)),
        ("pickup_name", sa.Column("pickup_name", sa.String(255), server_default="Origin Hospital", nullable=False)),
        ("pickup_latitude", sa.Column("pickup_latitude", sa.Float(), server_default="37.7749", nullable=False)),
        ("pickup_longitude", sa.Column("pickup_longitude", sa.Float(), server_default="-122.4194", nullable=False)),
        ("destination_name", sa.Column("destination_name", sa.String(255), server_default="Destination Hospital", nullable=False)),
        ("destination_latitude", sa.Column("destination_latitude", sa.Float(), server_default="37.7550", nullable=False)),
        ("destination_longitude", sa.Column("destination_longitude", sa.Float(), server_default="-122.4300", nullable=False)),
        ("distance_km", sa.Column("distance_km", sa.Float(), server_default="0.0", nullable=False)),
        ("estimated_duration_minutes", sa.Column("estimated_duration_minutes", sa.Integer(), server_default="15", nullable=False)),
        ("current_eta_minutes", sa.Column("current_eta_minutes", sa.Integer(), server_default="15", nullable=False)),
        ("vehicle_number", sa.Column("vehicle_number", sa.String(50), nullable=True)),
        ("driver_name", sa.Column("driver_name", sa.String(100), nullable=True)),
        ("driver_phone", sa.Column("driver_phone", sa.String(50), nullable=True)),
        ("cancellation_reason", sa.Column("cancellation_reason", sa.Text(), nullable=True)),
        ("en_route_at", sa.Column("en_route_at", sa.DateTime(timezone=True), nullable=True)),
        ("arrived_pickup_at", sa.Column("arrived_pickup_at", sa.DateTime(timezone=True), nullable=True)),
        ("patient_onboard_at", sa.Column("patient_onboard_at", sa.DateTime(timezone=True), nullable=True)),
        ("departed_pickup_at", sa.Column("departed_pickup_at", sa.DateTime(timezone=True), nullable=True)),
        ("arrived_destination_at", sa.Column("arrived_destination_at", sa.DateTime(timezone=True), nullable=True)),
        ("completed_at", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True)),
        ("created_at", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)),
        ("updated_at", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)),
    ]

    for col_name, col_def in cols_to_add:
        if col_name not in existing_cols:
            op.add_column("ambulance_dispatches", col_def)

    # Add index on dispatch_reference if column was added
    try:
        op.create_index("ix_ambulance_dispatches_dispatch_reference", "ambulance_dispatches", ["dispatch_reference"], unique=True)
    except Exception:
        pass


def downgrade() -> None:
    pass
