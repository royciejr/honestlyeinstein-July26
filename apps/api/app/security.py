"""HMAC signing for internal (service-to-service) endpoints.

Header format:  X-Internal-Signature: t=<unix-seconds>,v1=<hex hmac-sha256>
Signed string:  "<t>.<raw request body>"

The reference project used a plaintext shared-secret equality check; this is
the hardened replacement — constant-time compare plus a timestamp window so a
captured request can't be replayed later.
"""

import hmac
import time
from hashlib import sha256

SIGNATURE_HEADER = "X-Internal-Signature"


def sign_internal(body: bytes, secret: str, timestamp: int | None = None) -> str:
    t = int(time.time()) if timestamp is None else timestamp
    mac = hmac.new(secret.encode(), f"{t}.".encode() + body, sha256).hexdigest()
    return f"t={t},v1={mac}"


def verify_internal(
    header_value: str, body: bytes, secret: str, max_skew_seconds: int = 300
) -> bool:
    try:
        parts = dict(p.split("=", 1) for p in header_value.split(","))
        t = int(parts["t"])
        candidate = parts["v1"]
    except (ValueError, KeyError):
        return False
    if abs(int(time.time()) - t) > max_skew_seconds:
        return False
    expected = hmac.new(secret.encode(), f"{t}.".encode() + body, sha256).hexdigest()
    return hmac.compare_digest(expected, candidate)
