from fastapi.testclient import TestClient

from backend.main import app, health, root


def test_root_and_health_routes_return_expected_status():
    assert root()["status"] == "running"
    assert health()["status"] == "ok"

    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/api/v1/health").json()["status"] == "ok"
