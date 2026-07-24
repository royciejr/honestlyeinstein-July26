"""Step Functions writer: posts the pipeline outcome to the API's HMAC-signed
/internal/generation-result endpoint. Invoked from both branches of the
Choice state with {"kind": "approved"|"review", "state": <full SFN state>} —
approved inserts a verified template, review inserts a review_queue row.

The HMAC helper is duplicated from the marker Lambda by design: both stay
stdlib-only zips (no shared layer to version/deploy).
"""

import hmac
import json
import os
import time
import urllib.error
import urllib.request
from hashlib import sha256


def _sign(body: bytes, secret: str) -> str:
    t = int(time.time())
    mac = hmac.new(secret.encode(), f"{t}.".encode() + body, sha256).hexdigest()
    return f"t={t},v1={mac}"


def _post_internal(path: str, payload: dict) -> dict:
    base = os.environ["API_BASE_URL"].rstrip("/")
    secret = os.environ.get("INTERNAL_HMAC_SECRET", "")
    if not secret:
        raise RuntimeError("INTERNAL_HMAC_SECRET is not set on this Lambda")
    body = json.dumps(payload).encode()
    last_error: Exception | None = None
    for attempt in range(3):
        request = urllib.request.Request(
            f"{base}{path}",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Internal-Signature": _sign(body, secret),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            if 400 <= exc.code < 500:
                raise RuntimeError(f"API rejected generation result ({exc.code}): {detail}") from exc
            last_error = RuntimeError(f"API 5xx ({exc.code}): {detail}")
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
        time.sleep(2**attempt)
    raise RuntimeError(f"Failed to deliver generation result after 3 attempts: {last_error}")


def handler(event: dict, context: object) -> dict:
    kind = event.get("kind")
    state = event.get("state") or {}
    template = (state.get("generated") or {}).get("template")
    if kind not in ("approved", "review") or not template:
        raise ValueError(f"Unexpected writer input: {json.dumps(event)[:500]}")

    verified = state.get("verified") or {}
    symchecked = state.get("symchecked") or {}
    payload: dict = {"kind": kind, "template": template}
    if kind == "review":
        reasons = []
        if not verified.get("agrees", True):
            reasons.append(f"verifier disagreed: {verified.get('notes', 'no notes')}")
        if not symchecked.get("ok", True):
            reasons.append(f"symcheck failed: {symchecked.get('notes', 'no notes')}")
        payload["reason"] = "; ".join(reasons) or "flagged by pipeline"
        payload["payloads"] = {"template": template, "verified": verified, "symchecked": symchecked}

    result = _post_internal("/internal/generation-result", payload)
    print(f"api response: {json.dumps(result)}")
    return {"ok": True, "kind": kind, "api": result}
