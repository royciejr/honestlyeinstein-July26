import time

from app.security import sign_internal, verify_internal

SECRET = "s3cret"


def test_roundtrip():
    body = b'{"hello": "world"}'
    header = sign_internal(body, SECRET)
    assert verify_internal(header, body, SECRET)


def test_tampered_body_rejected():
    header = sign_internal(b"original", SECRET)
    assert not verify_internal(header, b"tampered", SECRET)


def test_wrong_secret_rejected():
    body = b"payload"
    header = sign_internal(body, SECRET)
    assert not verify_internal(header, body, "other-secret")


def test_stale_timestamp_rejected():
    body = b"payload"
    header = sign_internal(body, SECRET, timestamp=int(time.time()) - 3600)
    assert not verify_internal(header, body, SECRET, max_skew_seconds=300)


def test_garbage_header_rejected():
    assert not verify_internal("not-a-signature", b"x", SECRET)
    assert not verify_internal("t=abc,v1=zzz", b"x", SECRET)
    assert not verify_internal("", b"x", SECRET)
