"""Structural validation: the graph must be a real DAG over real nodes."""

from __future__ import annotations

import sys
from pathlib import Path

# `graph/` is a top-level package beside `src/`, but pytest's `pythonpath` is
# configured for `src` only and `pyproject.toml` is outside this node's
# ownership. Adding the repository root here keeps the import working; folding
# `graph` into the project's `pythonpath` is a recommended follow-up.
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pytest  # noqa: E402
from support import graph_text, node_block  # noqa: E402

from graph import (  # noqa: E402
    GraphValidationError,
    collect_errors,
    is_acyclic,
    load_graph,
    load_graph_text,
    validate,
)


def test_the_project_graph_is_a_valid_dag() -> None:
    graph = load_graph()

    assert is_acyclic(graph) is True
    assert collect_errors(graph) == []
    assert validate(graph) is graph


def test_cycle_is_rejected() -> None:
    text = graph_text(
        node_block("A-001", depends_on=("C-001",)),
        node_block("B-001", depends_on=("A-001",)),
        node_block("C-001", depends_on=("B-001",)),
    )

    with pytest.raises(GraphValidationError, match="cycle detected") as caught:
        load_graph_text(text)

    # The message must name the cycle, not merely announce that one exists.
    message = str(caught.value)
    assert "A-001" in message
    assert "B-001" in message
    assert "C-001" in message


def test_two_node_cycle_is_rejected() -> None:
    text = graph_text(
        node_block("A-001", depends_on=("B-001",)),
        node_block("B-001", depends_on=("A-001",)),
    )

    with pytest.raises(GraphValidationError, match="cycle detected"):
        load_graph_text(text)


def test_self_dependency_is_rejected() -> None:
    text = graph_text(node_block("A-001", depends_on=("A-001",)))

    with pytest.raises(GraphValidationError, match="depends on itself"):
        load_graph_text(text)


def test_unknown_dependency_is_rejected() -> None:
    text = graph_text(node_block("A-001", depends_on=("GHOST-001",)))

    with pytest.raises(GraphValidationError, match="unknown node 'GHOST-001'"):
        load_graph_text(text)


def test_a_self_dependency_is_not_also_reported_as_a_cycle() -> None:
    """Self-dependency has its own clearer message; do not double-report it."""
    text = graph_text(node_block("A-001", depends_on=("A-001",)))

    with pytest.raises(GraphValidationError) as caught:
        load_graph_text(text)

    assert caught.value.errors == ["A-001: depends on itself"]


def test_every_problem_is_reported_together() -> None:
    text = graph_text(
        node_block("A-001", depends_on=("GHOST-001",)),
        node_block("B-001", depends_on=("B-001",)),
    )

    with pytest.raises(GraphValidationError) as caught:
        load_graph_text(text)

    assert len(caught.value.errors) == 2
    assert "2 problems" in str(caught.value)


def test_a_single_problem_is_described_in_the_singular() -> None:
    text = graph_text(node_block("A-001", depends_on=("GHOST-001",)))

    with pytest.raises(GraphValidationError, match="1 problem"):
        load_graph_text(text)


def test_a_diamond_is_valid() -> None:
    """Shared prerequisites are normal; only cycles are forbidden."""
    text = graph_text(
        node_block("ROOT-001"),
        node_block("LEFT-001", depends_on=("ROOT-001",)),
        node_block("RIGHT-001", depends_on=("ROOT-001",)),
        node_block("JOIN-001", depends_on=("LEFT-001", "RIGHT-001")),
    )

    graph = load_graph_text(text)

    assert is_acyclic(graph) is True
    assert len(graph) == 4
