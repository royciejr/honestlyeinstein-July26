#!/usr/bin/env python3
"""End-to-end demo of the photo pipeline through the public API, acting as the
browser would: create/find a child, presign, PUT a tiny image to S3, then poll
until the marker Lambda's result lands in Postgres.

Usage:
    # Against a local API with CLERK_AUTH_DISABLED=1:
    python scripts/demo_upload.py

    # Against the deployed stack (see RUNBOOK for grabbing a JWT):
    python scripts/demo_upload.py --api-base https://<render-url> --token '<clerk JWT>'

Stdlib only — no dependencies to install.
"""

import argparse
import json
import struct
import sys
import time
import urllib.error
import urllib.request
import zlib


def tiny_png() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    ihdr = struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0)
    idat = zlib.compress((b"\x00" + b"\x4f\x46\xe5" * 8) * 8)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


class Api:
    def __init__(self, base: str, token: str | None):
        self.base = base.rstrip("/")
        self.token = token

    def call(self, method: str, path: str, payload: dict | None = None) -> dict | list:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(
            f"{self.base}{path}",
            method=method,
            headers=headers,
            data=json.dumps(payload).encode() if payload is not None else None,
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            sys.exit(f"✗ {method} {path} -> {exc.code}: {body}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--token", default=None, help="Clerk JWT (omit if CLERK_AUTH_DISABLED=1)")
    parser.add_argument("--timeout", type=int, default=120, help="seconds to wait for marking")
    args = parser.parse_args()
    api = Api(args.api_base, args.token)

    print(f"→ health check {args.api_base}/healthz")
    health = api.call("GET", "/healthz")
    print(f"  {health}")

    children = api.call("GET", "/children")
    assert isinstance(children, list)
    if children:
        child = children[0]
        print(f"→ using existing child {child['display_name']!r}")
    else:
        child = api.call(
            "POST", "/children", {"display_name": "Demo Child", "country": "UK", "year_band": "Y4"}
        )
        assert isinstance(child, dict)
        print(f"→ created child {child['display_name']!r}")

    print("→ requesting presigned PUT URL")
    presign = api.call(
        "POST", "/uploads/presign", {"child_id": child["id"], "content_type": "image/png"}
    )
    assert isinstance(presign, dict)
    print(f"  s3_key: {presign['s3_key']}")

    print("→ PUTting a tiny PNG straight to S3 (not through the API)")
    put = urllib.request.Request(
        presign["url"], method="PUT", data=tiny_png(), headers=presign["headers"]
    )
    try:
        with urllib.request.urlopen(put, timeout=30) as response:
            print(f"  S3 responded {response.status}")
    except urllib.error.HTTPError as exc:
        sys.exit(f"✗ S3 PUT failed ({exc.code}): {exc.read().decode(errors='replace')[:300]}")

    print(
        f"→ polling upload status (S3 → EventBridge → marker Lambda → API), up to {args.timeout}s"
    )
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        uploads = api.call("GET", f"/children/{child['id']}/uploads")
        assert isinstance(uploads, list)
        row = next((u for u in uploads if u["s3_key"] == presign["s3_key"]), None)
        if row and row["status"] != "pending":
            print(f"✓ upload is {row['status']!r}")
            print(f"  marking_json: {json.dumps(row['marking_json'], indent=2)[:600]}")
            print("→ child progress after mastery update:")
            progress = api.call("GET", f"/children/{child['id']}/progress")
            assert isinstance(progress, dict)
            for module in progress["modules"]:
                lock = "🌍" if module["unlocked"] else "🔒"
                skills = ", ".join(f"{s['slug']}:L{s['mastery_level']}" for s in module["skills"])
                print(f"  {lock} {module['title']}: {skills}")
            return
        time.sleep(5)
        print("  … still pending")
    sys.exit("✗ timed out — check the marker Lambda's CloudWatch logs (see RUNBOOK)")


if __name__ == "__main__":
    main()
