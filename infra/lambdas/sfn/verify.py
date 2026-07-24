"""Step Functions `verify` stub. Phase 2: a second Bedrock call with a
sceptical-examiner persona independently solves the generated template and
reports agreement. The stub agrees unless the execution input carries
{"force_disagreement": true} — use that to demo the human-review branch."""


def handler(event: dict, context: object) -> dict:
    force = bool(event.get("force_disagreement"))
    print(f"stub-verifying (force_disagreement={force})")
    return {
        "agrees": not force,
        "notes": "stub verifier — real persona prompt arrives in Phase 2",
    }
