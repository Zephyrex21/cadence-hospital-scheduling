from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "ok", "service": "cadence-api"}


def test_root_reports_version() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Cadence API"
