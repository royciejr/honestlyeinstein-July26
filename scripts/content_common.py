"""Shared validation helpers for the content loaders. Pure functions — no DB
imports here, so they stay unit-testable and usable in --check (CI) mode."""

import re
import sys
from pathlib import Path
from typing import Any

import yaml

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# UK KS2 content-domain codes: year 1-6, strand letter(s), number, optional
# sub-letter. Examples: 6F5, 4C6b, 5G4a.
KS2_CODE_RE = re.compile(r"^[1-6][A-Z]{1,2}\d{1,2}[a-z]?$")
# US Common Core: Grade.Domain.Cluster.Standard[sub]. Examples: 5.NF.A.1,
# 3.OA.C.7, 4.NBT.B.5a. (K-prefixed codes exist but are out of our age range.)
CCSS_CODE_RE = re.compile(r"^[K1-8]\.[A-Z]{1,3}\.[A-Z]\.\d{1,2}[a-z]?$")

SCHEMES = {"KS2", "CCSS"}
COUNTRIES = {"UK", "US"}


class ContentError(Exception):
    """Raised with the full list of validation problems, not just the first."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


def read_yaml(path: Path) -> Any:
    if not path.exists():
        raise ContentError([f"file not found: {path}"])
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ContentError([f"{path}: invalid YAML: {exc}"]) from exc


def check_slug(value: Any, where: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value:
        errors.append(f"{where}: slug is required")
    elif len(value) > 64:
        errors.append(f"{where}: slug {value!r} exceeds 64 chars")
    elif not SLUG_RE.match(value):
        errors.append(f"{where}: slug {value!r} must be lowercase kebab-case (a-z, 0-9, -)")


def check_mapping_code(scheme: Any, code: Any, where: str, errors: list[str]) -> None:
    if scheme not in SCHEMES:
        errors.append(f"{where}: scheme must be one of {sorted(SCHEMES)}, got {scheme!r}")
        return
    if not isinstance(code, str):
        errors.append(f"{where}: code must be a string, got {code!r}")
        return
    pattern = KS2_CODE_RE if scheme == "KS2" else CCSS_CODE_RE
    if not pattern.match(code):
        example = "6F5 / 4C6b" if scheme == "KS2" else "5.NF.A.1 / 3.OA.C.7"
        errors.append(
            f"{where}: {scheme} code {code!r} doesn't match the expected format ({example})"
        )


def find_cycle(edges: list[tuple[str, str]]) -> list[str] | None:
    """Kahn's algorithm. Returns the nodes stuck in a cycle, or None if acyclic."""
    nodes = {n for edge in edges for n in edge}
    out: dict[str, set[str]] = {n: set() for n in nodes}
    indegree = dict.fromkeys(nodes, 0)
    for prereq, unlocks in edges:
        if unlocks not in out[prereq]:
            out[prereq].add(unlocks)
            indegree[unlocks] += 1
    queue = [n for n, d in indegree.items() if d == 0]
    seen = 0
    while queue:
        node = queue.pop()
        seen += 1
        for nxt in out[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if seen == len(nodes):
        return None
    return sorted(n for n, d in indegree.items() if d > 0)


def load_env_fallback() -> None:
    """If DATABASE_URL isn't exported, borrow it from apps/api/.env so loaders
    'just work' after local API setup. Tiny parser on purpose — no dotenv dep."""
    import os

    if os.environ.get("DATABASE_URL"):
        return
    env_file = Path(__file__).resolve().parents[1] / "apps" / "api" / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            if value:
                os.environ["DATABASE_URL"] = value
            return


def fail(errors: list[str]) -> None:
    print(f"✗ {len(errors)} problem(s) found:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    raise SystemExit(1)
