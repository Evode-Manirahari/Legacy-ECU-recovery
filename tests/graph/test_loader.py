"""Loading and parsing the development graph.

The parser is intentionally strict, so most of these tests assert that a
malformed graph is *refused*. A graph file decides what work is allowed to
start; loading something subtly different from what the file says would be far
worse than refusing to load at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from support import graph_text, node_block

from graph import (
    GraphError,
    GraphParseError,
    NodeStatus,
    VerificationKind,
    load_graph,
    load_graph_text,
    parse_yaml_subset,
)

#: The graph the specification requires, as (node, dependency) edges.
REQUIRED_EDGES = {
    ("REPO-001", "SPEC-001"),
    ("GRAPH-001", "REPO-001"),
    ("DATA-001", "GRAPH-001"),
    ("RESEARCH-001", "GRAPH-001"),
    ("EVIDENCE-001", "GRAPH-001"),
    ("GHIDRA-001", "DATA-001"),
    ("EVAL-STATIC-001", "GHIDRA-001"),
    ("TOOLS-001", "EVAL-STATIC-001"),
    ("INTEGRATION-STATIC-001", "TOOLS-001"),
    ("INTEGRATION-STATIC-001", "EVIDENCE-001"),
    ("GATE-STATIC-MVP", "INTEGRATION-STATIC-001"),
}

REQUIRED_NODES = {
    "SPEC-001",
    "REPO-001",
    "GRAPH-001",
    "DATA-001",
    "RESEARCH-001",
    "EVIDENCE-001",
    "GHIDRA-001",
    "EVAL-STATIC-001",
    "TOOLS-001",
    "INTEGRATION-STATIC-001",
    "REPORT-001",
    "GATE-STATIC-MVP",
    "AGENT-001",
    "EVAL-AGENT-001",
    "PROVIDER-001",
    "PROVENANCE-001",
    "DETECTION-SCOPE-001",
    "BASELINE-AGENT-001",
    "REVIEW-AGENT-BASELINE-001",
    "GATE-AGENT-MVP",
}


def test_project_graph_loads() -> None:
    graph = load_graph()

    assert graph.project_id == "legacy-ecu-recovery"
    assert set(graph.ids) == REQUIRED_NODES


def test_project_graph_encodes_every_required_edge() -> None:
    graph = load_graph()

    edges = {(node.id, dependency) for node in graph for dependency in node.depends_on}

    missing = REQUIRED_EDGES - edges
    assert not missing, f"missing required edges: {sorted(missing)}"


def test_every_node_carries_the_required_fields() -> None:
    graph = load_graph()

    for node in graph:
        assert node.id
        assert node.title
        assert isinstance(node.depends_on, tuple)
        assert isinstance(node.status, NodeStatus)
        assert node.prompt, f"{node.id} has no prompt"
        assert node.retry_budget is not None, f"{node.id} has no retry budget"


def test_every_declared_prompt_file_exists() -> None:
    graph = load_graph()
    root = Path(__file__).resolve().parents[2]

    missing = [node.id for node in graph if not (root / str(node.prompt)).is_file()]

    assert not missing, f"nodes referencing absent prompt files: {missing}"


def test_verification_blocks_are_parsed() -> None:
    graph = load_graph()

    spec = graph.node("SPEC-001").verification
    assert spec is not None
    assert spec.kind is VerificationKind.HUMAN
    assert spec.requires_human is True

    repo = graph.node("REPO-001").verification
    assert repo is not None
    assert repo.kind is VerificationKind.COMMANDS
    assert "uv run pytest" in repo.commands

    gate = graph.node("GATE-STATIC-MVP").verification
    assert gate is not None
    assert gate.kind is VerificationKind.GATE


def test_scalar_forms_round_trip() -> None:
    parsed = parse_yaml_subset(
        'a: plain\nb: "quoted"\nc: 42\nd: true\ne: null\nf: []\ng: value # trailing\n'
    )

    assert parsed == {
        "a": "plain",
        "b": "quoted",
        "c": 42,
        "d": True,
        "e": None,
        "f": [],
        "g": "value",
    }


def test_comments_and_blank_lines_are_ignored() -> None:
    parsed = parse_yaml_subset("# leading\n\nkey: value\n\n# trailing\n")

    assert parsed == {"key": "value"}


def test_nested_blocks_and_sequences_parse() -> None:
    parsed = parse_yaml_subset("outer:\n  inner:\n    - one\n    - two\n  scalar: 3\n")

    assert parsed == {"outer": {"inner": ["one", "two"], "scalar": 3}}


def test_invalid_status_is_rejected() -> None:
    text = graph_text(node_block("A-001", status="ALMOST_DONE"))

    with pytest.raises(GraphError, match="invalid status"):
        load_graph_text(text)


def test_duplicate_node_id_is_rejected() -> None:
    text = graph_text(node_block("A-001"), node_block("A-001"))

    with pytest.raises(GraphParseError, match="duplicate key"):
        load_graph_text(text)


def test_missing_title_is_rejected() -> None:
    text = graph_text("  A-001:\n    depends_on: []\n    status: PENDING")

    with pytest.raises(GraphParseError, match="'title' is required"):
        load_graph_text(text)


def test_missing_status_is_rejected() -> None:
    text = graph_text("  A-001:\n    title: A\n    depends_on: []")

    with pytest.raises(GraphParseError, match="'status' is required"):
        load_graph_text(text)


def test_commands_verification_requires_commands() -> None:
    text = graph_text(
        "  A-001:\n"
        "    title: A\n"
        "    depends_on: []\n"
        "    status: PENDING\n"
        "    verification:\n"
        "      type: commands"
    )

    with pytest.raises(GraphParseError, match="requires commands"):
        load_graph_text(text)


def test_unknown_verification_type_is_rejected() -> None:
    text = graph_text(
        "  A-001:\n"
        "    title: A\n"
        "    depends_on: []\n"
        "    status: PENDING\n"
        "    verification:\n"
        "      type: vibes"
    )

    with pytest.raises(GraphParseError, match="invalid verification type"):
        load_graph_text(text)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("key:\n\tnested: 1\n", "tabs"),
        ("key: [a, b]\n", "flow collections"),
        ("key: |\n", "block scalars"),
        ("---\nkey: value\n", "multi-document"),
        ('key: "unterminated\n', "unterminated"),
        ("  indented: start\n", "column 0"),
    ],
)
def test_unsupported_yaml_is_refused_not_guessed(text: str, expected: str) -> None:
    with pytest.raises(GraphParseError, match=expected):
        parse_yaml_subset(text)


def test_graph_without_nodes_is_rejected() -> None:
    with pytest.raises(GraphParseError, match="must define 'nodes'"):
        load_graph_text('project:\n  id: x\n  version: "1"\n')


def test_missing_graph_file_reports_the_path(tmp_path: Path) -> None:
    absent = tmp_path / "absent.yaml"

    with pytest.raises(GraphParseError, match="cannot read graph file"):
        load_graph(absent)
