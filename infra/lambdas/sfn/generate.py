"""Step Functions `generate` stub. Phase 2: Bedrock (Claude) writes candidate
question templates for a target skill. The stub returns a fixed, valid
template so the pipeline produces a real row the app can serve as a drill.

Execution input (all optional): {"skill_slug": "...", "force_disagreement": true}
"""


def handler(event: dict, context: object) -> dict:
    skill_slug = event.get("skill_slug") or "times-tables-to-12"
    print(f"stub-generating template for skill {skill_slug}")
    return {
        "stub": True,
        "template": {
            "skill_slug": skill_slug,
            "body": "What is {a} × {b}?",
            "param_constraints": {
                "a": {"min": 2, "max": 12},
                "b": {"min": 2, "max": 12},
            },
            "distractor_specs": {"off_by_one_table": True, "digit_swap": True},
            "difficulty_elo": 1200,
        },
    }
