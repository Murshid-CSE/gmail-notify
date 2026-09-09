"""
Tests for GET /health endpoint.
"""


def test_health_returns_200(client):
    """Health endpoint returns 200 with expected fields."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert "environment" in data
    assert "google_oauth_configured" in data
    assert "encryption_configured" in data
    assert "version" in data


def test_health_shows_config_status(client):
    """Health endpoint reflects actual configuration state."""
    response = client.get("/health")
    data = response.json()

    # In test env, we set these env vars, so they should be configured.
    assert data["google_oauth_configured"] is True
    assert data["encryption_configured"] is True
