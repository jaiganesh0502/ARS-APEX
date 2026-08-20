from datetime import datetime, timezone
import enum
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class PaymentStatus(str, enum.Enum):
    NOT_GENERATED = "not_generated"
    PENDING = "pending"
    PROCESSING = "processing"
    PAID_ONLINE = "paid_online"
    PAID_MANUAL = "paid_manual"
    FAILED = "failed"
    REFUNDED = "refunded"
    DEFERRED = "deferred"


class PaymentMethod(str, enum.Enum):
    ONLINE_GATEWAY = "online_gateway"
    CASH = "cash"
    CARD_OFFLINE = "card"
    UPI_OFFLINE = "upi_manual"
    INSURANCE = "insurance"


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(100), unique=True, index=True, nullable=False)
    admission_id = Column(Integer, ForeignKey("admissions.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    billing_clearance_id = Column(Integer, ForeignKey("billing_clearances.id", ondelete="SET NULL"), nullable=True, index=True)

    subtotal = Column(Numeric(10, 2), default=0.00, nullable=False)
    discount_amount = Column(Numeric(10, 2), default=0.00, nullable=False)
    tax_amount = Column(Numeric(10, 2), default=0.00, nullable=False)
    total_amount = Column(Numeric(10, 2), default=0.00, nullable=False)
    amount_paid = Column(Numeric(10, 2), default=0.00, nullable=False)
    balance_amount = Column(Numeric(10, 2), default=0.00, nullable=False)

    payment_status = Column(
        Enum(
            PaymentStatus,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
        ),
        default=PaymentStatus.PENDING,
        nullable=False,
        index=True,
    )
    qr_code_uri = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    admission = relationship("Admission", backref="invoices")
    patient = relationship("Patient", backref="invoices")
    billing_clearance = relationship("BillingClearance", backref="invoices")
    line_items = relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("PaymentTransaction", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    charge_item_id = Column(Integer, ForeignKey("charge_master_items.id", ondelete="SET NULL"), nullable=True)

    category = Column(String(50), nullable=False)
    description = Column(String(255), nullable=False)
    quantity = Column(Numeric(10, 2), default=1.00, nullable=False)
    unit_price = Column(Numeric(10, 2), default=0.00, nullable=False)
    amount = Column(Numeric(10, 2), default=0.00, nullable=False)
    source_reference = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    invoice = relationship("Invoice", back_populates="line_items")
    charge_item = relationship("ChargeMasterItem")
