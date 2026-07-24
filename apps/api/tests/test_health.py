from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz_ok_without_db():
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_db_endpoints_fail_closed_without_database_url():
    # Auth is disabled in tests, so this reaches the DB layer and must get a
    # clear 503 — not a crash — when DATABASE_URL is unset.
    res = client.get("/children")
    assert res.status_code == 503
    assert "DATABASE_URL" in res.json()["detail"]
