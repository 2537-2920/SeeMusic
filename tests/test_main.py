from backend.main import health, root


def test_root_and_health_routes_return_expected_status():
    assert root()["status"] == "running"
    assert health()["status"] == "ok"
