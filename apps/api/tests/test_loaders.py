"""Validation-layer tests for the content loaders (no DB). The loader scripts
live in scripts/ (not a package), so they're imported by file path."""

import copy
import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_module(name: str):
    # Register in sys.modules BEFORE exec so the scripts' own
    # `from content_common import ...` shares the same module object —
    # otherwise ContentError would be two distinct classes.
    if name in sys.modules:
        return sys.modules[name]
    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


content_common = _load_module("content_common")
load_graph = _load_module("load_graph")
load_paper = _load_module("load_paper")

GRAPH_PATH = REPO_ROOT / "content" / "graph.yaml"
PAPER_DIR = REPO_ROOT / "content" / "papers" / "example-arithmetic-a"


@pytest.fixture()
def example_graph() -> dict:
    return yaml.safe_load(GRAPH_PATH.read_text(encoding="utf-8"))


def test_example_graph_is_valid(example_graph):
    spec = load_graph.parse_graph(example_graph)
    assert len(spec.modules) == 2
    assert len(spec.skills) == 5
    assert len(spec.edges) == 2
    assert sum(len(s.mappings) for s in spec.skills) == 9


def test_duplicate_skill_slug_rejected(example_graph):
    graph = copy.deepcopy(example_graph)
    graph["modules"][1]["skills"][0]["slug"] = "place-value-to-10000"
    with pytest.raises(content_common.ContentError, match="duplicate skill slug"):
        load_graph.parse_graph(graph)


def test_cycle_rejected(example_graph):
    graph = copy.deepcopy(example_graph)
    graph["edges"].append(
        {"prereq": "multiply-2digit-by-1digit", "unlocks": "place-value-to-10000"}
    )
    with pytest.raises(content_common.ContentError, match="cycle"):
        load_graph.parse_graph(graph)


def test_unknown_edge_endpoint_rejected(example_graph):
    graph = copy.deepcopy(example_graph)
    graph["edges"].append({"prereq": "no-such-skill", "unlocks": "times-tables-to-12"})
    with pytest.raises(content_common.ContentError, match="not a skill"):
        load_graph.parse_graph(graph)


def test_bad_ks2_code_rejected(example_graph):
    graph = copy.deepcopy(example_graph)
    graph["modules"][0]["skills"][0]["mappings"][0]["code"] = "XYZ99"
    with pytest.raises(content_common.ContentError, match="KS2 code"):
        load_graph.parse_graph(graph)


def test_bad_ccss_code_rejected(example_graph):
    graph = copy.deepcopy(example_graph)
    graph["modules"][0]["skills"][0]["mappings"][1]["code"] = "5NF1"
    with pytest.raises(content_common.ContentError, match="CCSS code"):
        load_graph.parse_graph(graph)


def test_bad_slug_format_rejected(example_graph):
    graph = copy.deepcopy(example_graph)
    graph["modules"][0]["slug"] = "Place Value!"
    with pytest.raises(content_common.ContentError, match="kebab-case"):
        load_graph.parse_graph(graph)


def test_code_regexes_directly():
    assert content_common.KS2_CODE_RE.match("6F5")
    assert content_common.KS2_CODE_RE.match("4C6b")
    assert not content_common.KS2_CODE_RE.match("7F5")  # KS2 stops at year 6
    assert not content_common.KS2_CODE_RE.match("4c6")  # lowercase strand
    assert content_common.CCSS_CODE_RE.match("5.NF.A.1")
    assert content_common.CCSS_CODE_RE.match("3.OA.C.7")
    assert not content_common.CCSS_CODE_RE.match("5.NF.1")  # missing cluster letter


def test_find_cycle_helper():
    assert content_common.find_cycle([("a", "b"), ("b", "c")]) is None
    assert content_common.find_cycle([("a", "b"), ("b", "a")]) == ["a", "b"]


def test_example_paper_valid_against_example_graph():
    known = load_paper.graph_skill_slugs(GRAPH_PATH)
    meta, questions = load_paper.parse_paper(PAPER_DIR, known)
    assert meta["slug"] == "example-arithmetic-a"
    assert len(questions) == 3
    assert questions[2]["question_no"] == "3a"


def test_paper_unknown_skill_rejected(tmp_path):
    paper = tmp_path / "fake-paper"
    paper.mkdir()
    (paper / "meta.yaml").write_text("title: T\ncountry: UK\n")
    (paper / "questions.yaml").write_text(
        "- {question_no: '1', skill: not-a-skill, max_marks: 1}\n"
    )
    known = load_paper.graph_skill_slugs(GRAPH_PATH)
    with pytest.raises(content_common.ContentError, match="not defined in the graph"):
        load_paper.parse_paper(paper, known)


def test_paper_duplicate_question_no_rejected(tmp_path):
    paper = tmp_path / "dup-paper"
    paper.mkdir()
    (paper / "meta.yaml").write_text("title: T\ncountry: UK\n")
    (paper / "questions.yaml").write_text(
        "- {question_no: '1', skill: times-tables-to-12, max_marks: 1}\n"
        "- {question_no: '1', skill: times-tables-to-12, max_marks: 1}\n"
    )
    known = load_paper.graph_skill_slugs(GRAPH_PATH)
    with pytest.raises(content_common.ContentError, match="duplicate question_no"):
        load_paper.parse_paper(paper, known)
