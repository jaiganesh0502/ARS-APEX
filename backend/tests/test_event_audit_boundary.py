from datetime import datetime, timezone

import pytest

from app.api.dependencies.auth import get_current_user_stub
from app.events.publisher import EventPublisher
from app.main import app
from app.models import User, UserRole, WorkflowEvent


def _user(db, role, suffix):
    user = User(
        name=f"Audit {suffix}",
        email=f"audit-{suffix}@test.invalid",
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def _sensitive_event(db):
    event = WorkflowEvent(
        event_type="clinical_decision_confirmed",
        entity_type="admission",
        entity_id=42,
        status="pending",
        created_at=datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc),
        payload={
            "patient_id": 991,
            "actor_name": "Sensitive Doctor Name",
            "clinical_notes": "Do not expose",
            "arbitrary_secret": "redact-me",
        },
    )
    db.add(event)
    db.commit()
    return event


def test_direct_workflow_event_rows_default_to_untrusted(db_session):
    """Making the ORM default trusted would let non-domain writes drive workflows."""
    event = _sensitive_event(db_session)

    assert getattr(event, "trusted_provenance", None) is False


def test_internal_event_publisher_marks_domain_events_trusted(db_session):
    """Forgetting provenance in the still-used internal publisher must fail."""
    event = EventPublisher(db_session).publish_event(
        event_type="transfer_requested",
        entity_type="transfer",
        entity_id=17,
        payload={"transfer_id": 17},
    )

    assert getattr(event, "trusted_provenance", None) is True


def test_external_clients_cannot_forge_workflow_events(client, db_session):
    before = db_session.query(WorkflowEvent).count()

    response = client.post("/api/events", json={
        "event_type": "bed_release_started",
        "entity_type": "bed",
        "entity_id": 1,
        "status": "pending",
        "payload": {"actor_role": "ward_admin", "patient_id": 999},
    })

    assert response.status_code == 405
    assert db_session.query(WorkflowEvent).count() == before


def test_event_audit_read_requires_authenticated_server_derived_user(client, db_session):
    _sensitive_event(db_session)
    app.dependency_overrides[get_current_user_stub] = lambda: None
    try:
        response = client.get("/api/events")
    finally:
        app.dependency_overrides.pop(get_current_user_stub, None)

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Authentication required"


def test_event_audit_read_rejects_non_operational_role(client, db_session):
    receiving_admin = _user(db_session, UserRole.RECEIVING_ADMIN, "receiving")
    _sensitive_event(db_session)
    app.dependency_overrides[get_current_user_stub] = lambda: receiving_admin
    try:
        response = client.get("/api/events")
    finally:
        app.dependency_overrides.pop(get_current_user_stub, None)

    assert response.status_code == 403


@pytest.mark.parametrize("role", [UserRole.DOCTOR, UserRole.WARD_ADMIN])
def test_authorized_event_audit_read_returns_only_operational_metadata(
    client, db_session, role,
):
    actor = _user(db_session, role, role.value)
    event = _sensitive_event(db_session)
    app.dependency_overrides[get_current_user_stub] = lambda: actor
    try:
        response = client.get("/api/events")
    finally:
        app.dependency_overrides.pop(get_current_user_stub, None)

    assert response.status_code == 200
    item = next(row for row in response.json() if row["id"] == event.id)
    assert set(item) == {
        "id", "event_type", "entity_type", "entity_id", "status", "created_at",
    }
    serialized = response.text
    for sensitive_value in (
        "payload", "patient_id", "actor_name", "Sensitive Doctor Name",
        "clinical_notes", "arbitrary_secret", "redact-me",
    ):
        assert sensitive_value not in serialized
