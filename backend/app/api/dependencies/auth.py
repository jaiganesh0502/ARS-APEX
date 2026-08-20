from typing import Optional, List
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.models.user import User, UserRole


async def get_current_user_stub(
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id")
) -> Optional[User]:
    """
    Placeholder dependency for authentication.
    In development, allows passing an X-User-Id header or defaults to the first doctor in the DB.
    Will be upgraded to full JWT verification in upcoming auth milestone.
    """
    if x_user_id:
        try:
            user = db.query(User).filter(User.id == int(x_user_id)).first()
            if user:
                return user
        except ValueError:
            pass

    # Default fallback for development without auth enforcement
    return db.query(User).first()


def require_role(allowed_roles: List[UserRole]):
    """Role-based access control dependency factory for future auth enforcement."""
    def role_checker(current_user: Optional[User] = Depends(get_current_user_stub)) -> User:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role: {current_user.role}"
            )
        return current_user

    return role_checker
