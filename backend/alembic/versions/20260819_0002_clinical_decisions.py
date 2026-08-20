"""Add clinical decisions.

Revision ID: 20260819_0002
Revises: 20260819_0001
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa

revision = "20260819_0002"
down_revision = "20260819_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clinical_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("admission_id", sa.Integer(), nullable=False),
        sa.Column("decision_type", sa.Enum("DISCHARGE", "TRANSFER", name="clinical_decision_type_enum", native_enum=False), nullable=False),
        sa.Column("transfer_urgency", sa.Enum("EMERGENCY", "NON_EMERGENCY", name="transfer_urgency_enum", native_enum=False), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("required_specialty", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.Integer(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Enum("DRAFT", "CONFIRMED", "CANCELLED", name="clinical_decision_status_enum", native_enum=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["admission_id"], ["admissions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "patient_id", "admission_id", "status"):
        op.create_index(f"ix_clinical_decisions_{column}", "clinical_decisions", [column], unique=False)
    op.create_index(
        "uq_clinical_decisions_active_admission", "clinical_decisions", ["admission_id"], unique=True,
        postgresql_where=sa.text("status IN ('draft', 'confirmed', 'DRAFT', 'CONFIRMED')"),
        sqlite_where=sa.text("status IN ('draft', 'confirmed', 'DRAFT', 'CONFIRMED')"),
    )
    # transfers.clinical_decision_id references this table; 20260819_0001
    # deliberately created transfers without that FK since clinical_decisions
    # didn't exist yet. Add it now that the referenced table is in place.
    op.create_foreign_key(
        "fk_transfers_clinical_decision_id_clinical_decisions",
        "transfers",
        "clinical_decisions",
        ["clinical_decision_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_transfers_clinical_decision_id_clinical_decisions", "transfers", type_="foreignkey"
    )
    op.drop_index("uq_clinical_decisions_active_admission", table_name="clinical_decisions")
    for column in ("status", "admission_id", "patient_id", "id"):
        op.drop_index(f"ix_clinical_decisions_{column}", table_name="clinical_decisions")
    op.drop_table("clinical_decisions")
