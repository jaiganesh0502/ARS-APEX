from datetime import datetime, timezone
import enum
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Integer,
    Numeric,
    String,
    Text,
)

from app.db.session import Base


class ChargeCategory(str, enum.Enum):
    ROOM = "room"
    PROCEDURE = "procedure"
    INVESTIGATION = "investigation"
    MEDICATION = "medication"
    CONSULTATION = "consultation"
    SERVICE = "service"


class ChargeMasterItem(Base):
    __tablename__ = "charge_master_items"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    category = Column(
        Enum(
            ChargeCategory,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
        ),
        default=ChargeCategory.SERVICE,
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False, default=0.00)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
