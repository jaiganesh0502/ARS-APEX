def test_health_check(client):
    """Verify that the health check endpoint returns 200 OK with expected payload."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "discharge-orchestration-api"


def test_root_endpoint(client):
    """Verify root discovery endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "health" in data
    assert "docs" in data
