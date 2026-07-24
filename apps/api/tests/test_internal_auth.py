"""The HMAC gate on /internal/* must reject before any DB access happens."""

import time

from fastapi.testclient import TestClient

from app.main import app
from app.security import SIGNATURE_HEADER, sign_internal

client = TestClient(app)

VALID_BODY = b'{"s3_key": "uploads/x/y.jpg", "status": "marked", "marking_json": {}}'


def test_missing_signature_is_401():
    res = client.post("/internal/marking-result", content=VALID_BODY)
    assert res.status_code == 401


def test_bad_signature_is_401():
    res = client.post(
        "/internal/marking-result",
        content=VALID_BODY,
        headers={SIGNATURE_HEADER: "t=123,v1=deadbeef", "Content-Type": "application/json"},
    )
    assert res.status_code == 401


def test_stale_signature_is_401():
    stale = sign_internal(VALID_BODY, "test-secret", timestamp=int(time.time()) - 3600)
    res = client.post(
        "/internal/marking-result",
        content=VALID_BODY,
        headers={SIGNATURE_HEADER: stale, "Content-Type": "application/json"},
    )
    assert res.status_code == 401


def test_valid_signature_passes_gate_then_hits_db_config():
    # With no DATABASE_URL, a correctly signed request must get past auth
    # (proving the signature path) and fail on the DB layer with 503.
    header = sign_internal(VALID_BODY, "test-secret")
    res = client.post(
        "/internal/marking-result",
        content=VALID_BODY,
        headers={SIGNATURE_HEADER: header, "Content-Type": "application/json"},
    )
    assert res.status_code == 503
    assert "DATABASE_URL" in res.json()["detail"]
