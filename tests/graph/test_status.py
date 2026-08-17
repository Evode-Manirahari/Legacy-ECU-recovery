"""Frontier semantics: what may start, what is waiting, what is obstructed.

These tests encode the rule the whole method rests on — only a verified
prerequisite unlocks downstream work.
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


def test_foundation_nodes_are_passed(graph: Graph) -> None:
    assert graph.node("SPEC-001").status is NodeStatus.PASSED
    assert graph.node("REPO-001").status is NodeStatus.PASSED
    assert set(passed_nodes(graph)) == {"SPEC-001", "REPO-001"}


def test_graph_001_is_in_flight_with_satisfied_dependencies(graph: Graph) -> None:
    """GRAPH-001 is being executed, so it is held rather than free to assign."""
    assert unmet_dependencies(graph, "GRAPH-001") == ()
    assert graph.node("GRAPH-001").status in {
        NodeStatus.READY,
        NodeStatus.RUNNING,
        NodeStatus.VERIFYING,
    }
    assert is_ready(graph, "GRAPH-001") is False


@pytest.mark.parametrize("node_id", FAN_OUT)
def test_fan_out_is_not_ready_before_graph_001_passes(graph: Graph, node_id: str) -> None:
    assert is_ready(graph, node_id) is False
    assert unmet_dependencies(graph, node_id) == ("GRAPH-001",)


@pytest.mark.parametrize("node_id", FAN_OUT)
def test_fan_out_becomes_ready_after_graph_001_passes(graph: Graph, node_id: str) -> None:
    passed = graph.with_status("GRAPH-001", NodeStatus.PASSED)

    assert is_ready(passed, node_id) is True


def test_exactly_the_fan_out_opens_when_graph_001_passes(graph: Graph) -> None:
    assert newly_ready_if_passed(graph, "GRAPH-001") == FAN_OUT


def test_ghidra_stays_unready_until_data_passes(graph: Graph) -> None:
    after_graph = graph.with_status("GRAPH-001", NodeStatus.PASSED)

    assert is_ready(after_graph, "GHIDRA-001") is False
    assert "DATA-001" in unmet_dependencies(after_graph, "GHIDRA-001")

    after_data = after_graph.with_status("DATA-001", NodeStatus.PASSED)

    assert is_ready(after_data, "GHIDRA-001") is True


def test_unverified_under_graph_does_not_satisfy_a_dependency(graph: Graph) -> None:
    """The rule that makes the first gate mean anything.

    DATA-001 holds pre-graph code, but candidate implementation is not a
    verified prerequisite, so GHIDRA-001 must not open.
    """
    assert graph.node("DATA-001").status is NodeStatus.UNVERIFIED_UNDER_GRAPH
    assert satisfies_dependency(NodeStatus.UNVERIFIED_UNDER_GRAPH) is False

    after_graph = graph.with_status("GRAPH-001", NodeStatus.PASSED)

    assert is_ready(after_graph, "GHIDRA-001") is False


def test_unverified_nodes_are_themselves_executable(graph: Graph) -> None:
    """Pre-graph code still has to be re-verified, so its node must be assignable."""
    after_graph = graph.with_status("GRAPH-001", NodeStatus.PASSED)

    assert is_ready(after_graph, "DATA-001") is True
    assert is_ready(after_graph, "EVIDENCE-001") is True


def test_nothing_is_ready_while_graph_001_is_held(graph: Graph) -> None:
    assert ready_nodes(graph) == ()


def test_nothing_is_blocked_in_the_current_graph(graph: Graph) -> None:
    """Waiting on a pending prerequisite is not the same as being obstructed."""
    assert blocked_nodes(graph) == ()


def test_a_failed_dependency_obstructs_everything_downstream(graph: Graph) -> None:
    failed = graph.with_status("DATA-001", NodeStatus.FAILED)

    assert is_blocked(failed, "GHIDRA-001") is True
    assert obstruction_of(failed, "GHIDRA-001") == ("DATA-001",)
    assert is_ready(failed, "GHIDRA-001") is False
    # Obstruction propagates transitively, not just one hop.
    assert is_blocked(failed, "GATE-STATIC-MVP") is True
    assert "GHIDRA-001" in blocked_nodes(failed)


@pytest.mark.parametrize("status", [NodeStatus.FAILED, NodeStatus.BLOCKED, NodeStatus.NEEDS_HUMAN])
def test_no_hard_stop_state_unlocks_a_dependent(graph: Graph, status: NodeStatus) -> None:
    stopped = graph.with_status("GRAPH-001", status)

    assert satisfies_dependency(status) is False
    for node_id in FAN_OUT:
        assert is_ready(stopped, node_id) is False


def test_a_node_already_passed_is_not_ready_again(graph: Graph) -> None:
    assert is_ready(graph, "SPEC-001") is False
    assert is_ready(graph, "REPO-001") is False


def test_querying_the_future_does_not_mutate_the_graph(graph: Graph) -> None:
    before = graph.node("GRAPH-001").status

    newly_ready_if_passed(graph, "GRAPH-001")

    assert graph.node("GRAPH-001").status is before


def test_dependency_lookups_work_in_both_directions(graph: Graph) -> None:
    assert graph.dependencies_of("GRAPH-001") == ("REPO-001",)
    assert set(graph.dependents_of("GRAPH-001")) == set(FAN_OUT)
    assert graph.dependents_of("GATE-STATIC-MVP") == ()


def test_unknown_node_lookups_fail_loudly(graph: Graph) -> None:
    with pytest.raises(KeyError, match="unknown node"):
        graph.node("NOPE-001")


def test_status_table_explains_why_a_node_is_not_ready(graph: Graph) -> None:
    rendered = render_status_table(graph)

    assert "SPEC-001" in rendered
    assert "PASSED" in rendered
    assert "waiting on GRAPH-001" in rendered
    assert len(rendered.splitlines()) == len(graph)


def test_status_table_names_the_obstruction(graph: Graph) -> None:
    failed = graph.with_status("DATA-001", NodeStatus.FAILED)

    assert "blocked by DATA-001" in render_status_table(failed)


def test_ready_rendering_reports_an_empty_frontier(graph: Graph) -> None:
    assert render_ready(graph) == "No nodes are ready."


def test_ready_rendering_lists_the_frontier(graph: Graph) -> None:
    passed = graph.with_status("GRAPH-001", NodeStatus.PASSED)

    rendered = render_ready(passed)

    assert len(rendered.splitlines()) == 3
    assert "DATA-001" in rendered
    assert "Synthetic firmware laboratory" in rendered


def test_a_root_node_with_no_dependencies_is_ready() -> None:
    graph = load_graph_text(graph_text(node_block("A-001")))

    assert ready_nodes(graph) == ("A-001",)
