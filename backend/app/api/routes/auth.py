from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserProfileRead

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticates hospital staff and patients with email and password.
    Returns signed JWT access token and user profile.
    """
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Please contact hospital administrator.",
        )

    role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
    token = create_access_token(
        subject=user.id,
        role=role_str,
        claims={"email": user.email, "name": user.name, "patient_id": user.patient_id},
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserProfileRead(
            id=user.id,
            name=user.name,
            email=user.email,
            role=role_str,
            is_active=user.is_active,
            patient_id=user.patient_id,
        ),
    )


@router.get("/me", response_model=UserProfileRead)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves the currently authenticated user's profile and permissions.
    Used for session restoration on page reload.
    """
    role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    return UserProfileRead(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        role=role_str,
        is_active=current_user.is_active,
        patient_id=current_user.patient_id,
    )
