import random

import pytest

from app.drill import instantiate_params, render_body


def test_params_within_bounds():
    constraints = {"a": {"min": 2, "max": 12}, "b": {"min": 3, "max": 9}}
    params = instantiate_params(constraints, random.Random(42))
    assert set(params) == {"a", "b"}
    assert 2 <= params["a"] <= 12
    assert 3 <= params["b"] <= 9


def test_deterministic_with_seed():
    constraints = {"a": {"min": 1, "max": 100}}
    assert instantiate_params(constraints, random.Random(7)) == instantiate_params(
        constraints, random.Random(7)
    )


def test_bad_constraint_shapes_raise():
    with pytest.raises(ValueError):
        instantiate_params({"a": {"min": 5}})
    with pytest.raises(ValueError):
        instantiate_params({"a": {"min": 9, "max": 2}})
    with pytest.raises(ValueError):
        instantiate_params({"a": [1, 2]})


def test_render_body():
    body = "What is {a} × {b}? (hint: {a} again)"
    out = render_body(body, {"a": 6, "b": 7})
    assert out == "What is 6 × 7? (hint: 6 again)"
