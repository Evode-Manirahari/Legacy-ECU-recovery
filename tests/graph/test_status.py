"""Frontier semantics: what may start, what is waiting, what is obstructed.

These tests encode the rule the whole method rests on — only a verified
prerequisite unlocks downstream work.

They assert **rules**, not today's node statuses. A test that hardcodes the live
frontier fails every time a node advances, which trains people to edit tests
during a status change; so state-dependent behaviour is checked by simulating a
state with `with_status`, and the live graph is used only for invariants that
hold at every point in the project's life.
"""

from __future__ import annotations

import pytest
from support import graph_text, node_block

from graph import (
    Graph,
    NodeStatus,
    blocked_nodes,
    is_blocked,
    is_ready,
    load_graph,
    load_graph_text,
    newly_ready_if_passed,
    obstruction_of,
    passed_nodes,
    ready_nodes,
    render_ready,
    render_status_table,
    satisfies_dependency,
    unmet_dependencies,
)

FAN_OUT = ("DATA-001", "RESEARCH-001", "EVIDENCE-001")


@pytest.fixture
def graph() -> Graph:
    return load_graph()


@pytest.fixture
def graph_001_held(graph: Graph) -> Graph:
    """The live graph rewound to while GRAPH-001 was still in flight."""
    return graph.with_status("GRAPH-001", NodeStatus.VERIFYING)


# --- invariants that hold regardless of how far the project has advanced ---


def test_foundation_nodes_are_passed(graph: Graph) -> None:
    """SPEC-001 and REPO-001 are done and never revert."""
    assert graph.node("SPEC-001").status is NodeStatus.PASSED
    assert graph.node("REPO-001").status is NodeStatus.PASSED
    assert {"SPEC-001", "REPO-001"} <= set(passed_nodes(graph))


def test_graph_001_dependencies_are_satisfied(graph: Graph) -> None:
    assert unmet_dependencies(graph, "GRAPH-001") == ()


def test_a_node_that_has_passed_is_not_ready_again(graph: Graph) -> None:
    for node_id in passed_nodes(graph):
        assert is_ready(graph, node_id) is False


def test_nothing_is_obstructed(graph: Graph) -> None:
    """Waiting on a pending prerequisite is not the same as being obstructed."""
    assert blocked_nodes(graph) == ()


def test_dependency_lookups_work_in_both_directions(graph: Graph) -> None:
    assert graph.dependencies_of("GRAPH-001") == ("REPO-001",)
    assert set(graph.dependents_of("GRAPH-001")) == set(FAN_OUT)
    assert graph.dependents_of("GATE-STATIC-MVP") == ()


def test_tools_001_depends_only_on_eval_static_001(graph: Graph) -> None:
    """Canonical as of 2026-08-17.

    Deterministic analysis must be measured before it is exposed through the
    tool layer, and GHIDRA-001 is already transitive through EVAL-STATIC-001, so
    a direct edge would be redundant.
    """
    assert graph.dependencies_of("TOOLS-001") == ("EVAL-STATIC-001",)
    assert "GHIDRA-001" in graph.dependencies_of("EVAL-STATIC-001")


def test_unknown_node_lookups_fail_loudly(graph: Graph) -> None:
    with pytest.raises(KeyError, match="unknown node"):
        graph.node("NOPE-001")


# --- the unlocking rule, checked against simulated states ---


@pytest.mark.parametrize("node_id", FAN_OUT)
def test_fan_out_waits_while_graph_001_is_in_flight(graph_001_held: Graph, node_id: str) -> None:
    assert is_ready(graph_001_held, node_id) is False
    assert unmet_dependencies(graph_001_held, node_id) == ("GRAPH-001",)


@pytest.mark.parametrize("node_id", FAN_OUT)
def test_fan_out_opens_once_graph_001_passes(graph_001_held: Graph, node_id: str) -> None:
    passed = graph_001_held.with_status("GRAPH-001", NodeStatus.PASSED)

    assert is_ready(passed, node_id) is True


def test_exactly_the_fan_out_opens_when_graph_001_passes(graph_001_held: Graph) -> None:
    assert newly_ready_if_passed(graph_001_held, "GRAPH-001") == FAN_OUT


def test_nothing_is_ready_while_graph_001_is_held(graph_001_held: Graph) -> None:
    assert ready_nodes(graph_001_held) == ()


def test_ghidra_stays_unready_until_data_passes(graph: Graph) -> None:
    assert is_ready(graph, "GHIDRA-001") is False
    assert "DATA-001" in unmet_dependencies(graph, "GHIDRA-001")

    after_data = graph.with_status("DATA-001", NodeStatus.PASSED)

    assert is_ready(after_data, "GHIDRA-001") is True


def test_unverified_under_graph_does_not_satisfy_a_dependency(graph: Graph) -> None:
    """The rule that makes the first gate mean anything.

    DATA-001 holds pre-graph code, but candidate implementation is not a
    verified prerequisite, so GHIDRA-001 must not open.
    """
    assert graph.node("DATA-001").status is NodeStatus.UNVERIFIED_UNDER_GRAPH
    assert satisfies_dependency(NodeStatus.UNVERIFIED_UNDER_GRAPH) is False
    assert is_ready(graph, "GHIDRA-001") is False


def test_unverified_nodes_are_themselves_executable(graph: Graph) -> None:
    """Pre-graph code still has to be re-verified, so its node must be assignable."""
    assert is_ready(graph, "DATA-001") is True
    assert is_ready(graph, "EVIDENCE-001") is True


@pytest.mark.parametrize("status", [NodeStatus.FAILED, NodeStatus.BLOCKED, NodeStatus.NEEDS_HUMAN])
def test_no_hard_stop_state_unlocks_a_dependent(graph: Graph, status: NodeStatus) -> None:
    stopped = graph.with_status("GRAPH-001", status)

    assert satisfies_dependency(status) is False
    for node_id in FAN_OUT:
        assert is_ready(stopped, node_id) is False


def test_a_failed_dependency_obstructs_everything_downstream(graph: Graph) -> None:
    failed = graph.with_status("DATA-001", NodeStatus.FAILED)

    assert is_blocked(failed, "GHIDRA-001") is True
    assert obstruction_of(failed, "GHIDRA-001") == ("DATA-001",)
    assert is_ready(failed, "GHIDRA-001") is False
    # Obstruction propagates transitively, not just one hop.
    assert is_blocked(failed, "GATE-STATIC-MVP") is True
    assert "GHIDRA-001" in blocked_nodes(failed)


def test_querying_the_future_does_not_mutate_the_graph(graph: Graph) -> None:
    before = graph.node("GRAPH-001").status

    newly_ready_if_passed(graph, "GRAPH-001")

    assert graph.node("GRAPH-001").status is before


# --- rendering ---


def test_status_table_covers_every_node(graph: Graph) -> None:
    rendered = render_status_table(graph)

    assert len(rendered.splitlines()) == len(graph)
    for node in graph:
        assert node.id in rendered


def test_status_table_explains_waiting(graph_001_held: Graph) -> None:
    assert "waiting on GRAPH-001" in render_status_table(graph_001_held)


def test_status_table_marks_the_frontier(graph: Graph) -> None:
    ready = ready_nodes(graph)
    rendered = render_status_table(graph)

    assert ready, "expected a non-empty frontier for this assertion to mean anything"
    assert "(ready)" in rendered


def test_status_table_names_the_obstruction(graph: Graph) -> None:
    failed = graph.with_status("DATA-001", NodeStatus.FAILED)

    assert "blocked by DATA-001" in render_status_table(failed)


def test_ready_rendering_reports_an_empty_frontier(graph_001_held: Graph) -> None:
    assert render_ready(graph_001_held) == "No nodes are ready."


def test_ready_rendering_lists_the_frontier(graph_001_held: Graph) -> None:
    passed = graph_001_held.with_status("GRAPH-001", NodeStatus.PASSED)

    rendered = render_ready(passed)

    assert len(rendered.splitlines()) == 3
    assert "DATA-001" in rendered
    assert "Synthetic firmware laboratory" in rendered


def test_a_root_node_with_no_dependencies_is_ready() -> None:
    graph = load_graph_text(graph_text(node_block("A-001")))

    assert ready_nodes(graph) == ("A-001",)
