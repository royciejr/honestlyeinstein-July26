"""Template instantiation for drill questions. Pure functions, unit-tested.

param_constraints format (Phase 1: integer ranges only):
    {"a": {"min": 2, "max": 12}, "b": {"min": 3, "max": 9}}
Body placeholders use {name}, e.g. "What is {a} × {b}?"
"""

import random


def instantiate_params(constraints: dict, rng: random.Random | None = None) -> dict[str, int]:
    rng = rng or random.Random()
    params: dict[str, int] = {}
    for name, spec in constraints.items():
        if not isinstance(spec, dict) or "min" not in spec or "max" not in spec:
            raise ValueError(f"param {name!r}: expected {{min, max}}, got {spec!r}")
        lo, hi = int(spec["min"]), int(spec["max"])
        if lo > hi:
            raise ValueError(f"param {name!r}: min {lo} > max {hi}")
        params[name] = rng.randint(lo, hi)
    return params


def render_body(body: str, params: dict[str, int]) -> str:
    rendered = body
    for name, value in params.items():
        rendered = rendered.replace("{" + name + "}", str(value))
    return rendered
