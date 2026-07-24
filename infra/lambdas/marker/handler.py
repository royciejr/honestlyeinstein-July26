"""Marker Lambda: S3 "Object Created" (via EventBridge) -> marking JSON ->
HMAC-signed POST to the API's /internal/marking-result.

Phase 1 ships the stub path only (MARKER_STUB_ENABLED=true): fixed marking
JSON referencing example-graph skills, so the whole pipe is provable without
prompt engineering. Phase 2 replaces the stub with a Bedrock (Claude) call on
the page image — the IAM policy and BEDROCK_MODEL_ID env are already in place.

Stdlib only, on purpose: no bundling step, no layers.
"""

import hmac
import json
import os
import time
import urllib.error
import urllib.request
from hashlib import sha256

# Skill slugs from content/graph.yaml (example content) so the stub exercises
# the real child_state update path end-to-end.
STUB_MARKING = {
    "marker": "stub",
    "questions": [
        {"question_no": "1", "skill_slug": "times-tables-to-12", "correct": True, "marks_awarded": 1},
        {"question_no": "2", "skill_slug": "place-value-to-10000", "correct": True, "marks_awarded": 1},
        {"question_no": "3a", "skill_slug": "multiply-2digit-by-1digit", "correct": False, "marks_awarded": 0, "misconception_tag": "carrying-error"},
    ],
}


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
            # 4xx = our bug or unknown s3_key; retrying won't help.
            if 400 <= exc.code < 500:
                raise RuntimeError(f"API rejected marking result ({exc.code}): {detail}") from exc
            last_error = RuntimeError(f"API 5xx ({exc.code}): {detail}")
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
        time.sleep(2**attempt)
    raise RuntimeError(f"Failed to deliver marking result after 3 attempts: {last_error}")


def lambda_handler(event: dict, context: object) -> dict:
    detail = event.get("detail") or {}
    bucket = (detail.get("bucket") or {}).get("name")
    key = (detail.get("object") or {}).get("key")
    if not bucket or not key:
        raise ValueError(f"Unexpected event shape (no bucket/object): {json.dumps(event)[:500]}")
    print(f"marking s3://{bucket}/{key}")

    if os.environ.get("MARKER_STUB_ENABLED", "true").lower() != "true":
        # Phase 2: fetch the image from S3, call Bedrock (BEDROCK_MODEL_ID),
        # parse structured marking JSON.
        raise NotImplementedError("Real marking is Phase 2 — set MARKER_STUB_ENABLED=true")

    result = _post_internal(
        "/internal/marking-result",
        {"s3_key": key, "status": "marked", "marking_json": STUB_MARKING},
    )
    print(f"api response: {json.dumps(result)}")
    return {"ok": True, "s3_key": key, "api": result}
