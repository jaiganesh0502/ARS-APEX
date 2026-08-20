from app.api.dependencies.database import get_db
from app.api.dependencies.auth import (
    get_current_user,
    get_current_user_stub,
    get_current_active_user,
    require_roles,
    require_doctor,
    require_superintendent,
    require_transfer_authority,
    require_staff,
    require_patient,
    get_current_patient_entity,
)

__all__ = [
    "get_db",
    "get_current_user",
    "get_current_user_stub",
    "get_current_active_user",
    "require_roles",
    "require_doctor",
    "require_superintendent",
    "require_transfer_authority",
    "require_patient",
    "get_current_patient_entity",
]
