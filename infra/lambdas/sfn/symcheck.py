"""Step Functions `symcheck` stub. Phase 2: SymPy evaluates the template's
answer expression across sampled params (needs a container image — SymPy
doesn't fit the zip limit). The stub always passes."""


def handler(event: dict, context: object) -> dict:
    print("stub-symchecking")
    return {"ok": True, "notes": "stub symcheck — SymPy container arrives in Phase 2"}
