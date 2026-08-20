from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.models.user import User, UserRole


@pytest.fixture
def auth_users(db_session):
    doctor = User(
        name="Dr. Auth Test",
        email="doctor.auth@hospital.org",
        role=UserRole.DOCTOR,
        password_hash=hash_password("DoctorPass123!"),
        is_active=True,
    )
    inactive_user = User(
        name="Inactive Staff",
        email="inactive@hospital.org",
        role=UserRole.WARD_ADMIN,
        password_hash=hash_password("InactivePass123!"),
        is_active=False,
    )
    db_session.add_all([doctor, inactive_user])
    db_session.commit()
    return {"doctor": doctor, "inactive": inactive_user}


def test_login_success(client: TestClient, auth_users):
    res = client.post(
        "/api/auth/login",
        json={"email": "doctor.auth@hospital.org", "password": "DoctorPass123!"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "doctor.auth@hospital.org"
    assert data["user"]["role"] == "doctor"


def test_login_invalid_password(client: TestClient, auth_users):
    res = client.post(
        "/api/auth/login",
        json={"email": "doctor.auth@hospital.org", "password": "WrongPassword!"},
    )
    assert res.status_code == 401
    err_msg = res.json().get("error", {}).get("message", "") or res.json().get("detail", "")
    assert "invalid email or password" in err_msg.lower()


def test_login_unknown_email(client: TestClient):
    res = client.post(
        "/api/auth/login",
        json={"email": "nonexistent@hospital.org", "password": "AnyPassword!"},
    )
    assert res.status_code == 401


def test_login_inactive_user(client: TestClient, auth_users):
    res = client.post(
        "/api/auth/login",
        json={"email": "inactive@hospital.org", "password": "InactivePass123!"},
    )
    assert res.status_code == 403
    err_msg = res.json().get("error", {}).get("message", "") or res.json().get("detail", "")
    assert "deactivated" in err_msg.lower()


def test_get_me_with_valid_token(client: TestClient, auth_users):
    token = create_access_token(subject=auth_users["doctor"].id, role="doctor")
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == auth_users["doctor"].id
    assert data["name"] == "Dr. Auth Test"
    assert data["role"] == "doctor"


def test_get_me_with_invalid_token(client: TestClient):
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.garbage.token"})
    assert res.status_code == 401


def test_get_me_with_expired_token(client: TestClient, auth_users):
    expired_token = create_access_token(
        subject=auth_users["doctor"].id,
        role="doctor",
        expires_delta=timedelta(seconds=-10),
    )
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
