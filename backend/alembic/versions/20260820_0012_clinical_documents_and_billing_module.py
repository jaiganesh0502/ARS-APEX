"""Add clinical documents, charge master, invoices, and payments tables.

Revision ID: 20260820_0012
Revises: 20260820_0011
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa


revision = "20260820_0012"
down_revision = "20260820_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Add discharge_ready column to admissions if not exists
    if "admissions" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("admissions")]
        if "discharge_ready" not in columns:
            op.add_column(
                "admissions",
                sa.Column("discharge_ready", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            )

    # 2. Create clinical_documents table if not exists
    if "clinical_documents" not in existing_tables:
        op.create_table(
            "clinical_documents",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("admission_id", sa.Integer(), sa.ForeignKey("admissions.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("uploader_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("document_type", sa.String(50), server_default="doctor_handwritten_notes", nullable=False),
            sa.Column("file_path", sa.String(500), nullable=False),
            sa.Column("file_name", sa.String(255), nullable=False),
            sa.Column("mime_type", sa.String(100), nullable=False),
            sa.Column("file_size_bytes", sa.Integer(), server_default="0", nullable=False),
            sa.Column("ocr_status", sa.String(50), server_default="uploaded", nullable=False, index=True),
            sa.Column("ocr_raw_text", sa.Text(), nullable=True),
            sa.Column("ocr_confidence", sa.Float(), nullable=True),
            sa.Column("structured_data", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # 3. Create charge_master_items table if not exists
    if "charge_master_items" not in existing_tables:
        op.create_table(
            "charge_master_items",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("code", sa.String(50), unique=True, index=True, nullable=False),
            sa.Column("category", sa.String(50), server_default="service", nullable=False, index=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("unit_price", sa.Numeric(10, 2), server_default="0.00", nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # 4. Create invoices table if not exists
    if "invoices" not in existing_tables:
        op.create_table(
            "invoices",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("invoice_number", sa.String(100), unique=True, index=True, nullable=False),
            sa.Column("admission_id", sa.Integer(), sa.ForeignKey("admissions.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("billing_clearance_id", sa.Integer(), sa.ForeignKey("billing_clearances.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("subtotal", sa.Numeric(10, 2), server_default="0.00", nullable=False),
            sa.Column("discount_amount", sa.Numeric(10, 2), server_default="0.00", nullable=False),
            sa.Column("tax_amount", sa.Numeric(10, 2), server_default="0.00", nullable=False),
            sa.Column("total_amount", sa.Numeric(10, 2), server_default="0.00", nullable=False),
            sa.Column("amount_paid", sa.Numeric(10, 2), server_default="0.00", nullable=False),
            sa.Column("balance_amount", sa.Numeric(10, 2), server_default="0.00", nullable=False),
            sa.Column("payment_status", sa.String(50), server_default="pending", nullable=False, index=True),
            sa.Column("qr_code_uri", sa.String(500), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # 5. Create invoice_line_items table if not exists
    if "invoice_line_items" not in existing_tables:
        op.create_table(
            "invoice_line_items",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("charge_item_id", sa.Integer(), sa.ForeignKey("charge_master_items.id", ondelete="SET NULL"), nullable=True),
            sa.Column("category", sa.String(50), nullable=False),
            sa.Column("description", sa.String(255), nullable=False),
            sa.Column("quantity", sa.Numeric(10, 2), server_default="1.00", nullable=False),
            sa.Column("unit_price", sa.Numeric(10, 2), server_default="0.00", nullable=False),
            sa.Column("amount", sa.Numeric(10, 2), server_default="0.00", nullable=False),
            sa.Column("source_reference", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # 6. Create payment_transactions table if not exists
    if "payment_transactions" not in existing_tables:
        op.create_table(
            "payment_transactions",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("amount", sa.Numeric(10, 2), nullable=False),
            sa.Column("payment_method", sa.String(50), nullable=False),
            sa.Column("transaction_reference", sa.String(100), nullable=True, index=True),
            sa.Column("payment_status", sa.String(50), server_default="completed", nullable=False),
            sa.Column("confirmed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("raw_payload", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("payment_transactions")
    op.drop_table("invoice_line_items")
    op.drop_table("invoices")
    op.drop_table("charge_master_items")
    op.drop_table("clinical_documents")
    op.drop_column("admissions", "discharge_ready")
