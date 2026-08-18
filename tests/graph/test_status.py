"""Frontier semantics: what may start, what is waiting, what is obstructed.

These tests encode the rule the whole method rests on — only a verified
prerequisite unlocks downstream work.

They assert **rules**, not today's node statuses. A test that hardcodes the live
frontier fails every time a node advances, which trains people to edit tests
during a status change; so state-dependent behaviour is checked by simulating a
state with `with_status`, and the live graph is used only for invariants that
hold at every point in the project's life.

Two consequences of that, both load-bearing:

* A simulated state is declared in full. Rewinding one node while every other
  node keeps whatever it has reached since does not describe a past state; it
  describes a state the project was never in, and what such a test proves
  changes silently every time an unrelated node advances.
* The live file supplies structure — which nodes exist, which edges join them,
  what they are called. The only live *status* facts read on purpose are the
  permanent ones, marked as such below.
"""

from __future__ import annotations

from collections.abc import Mapping

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

#: Statuses a node can be picked up from. Rules about *becoming* ready are
#: checked from both, so none of them quietly depends on which one a node
#: happens to hold today.
EXECUTABLE_STATES = (NodeStatus.PENDING, NodeStatus.UNVERIFIED_UNDER_GRAPH)

#: The whole graph as it stood while GRAPH-001 was still being verified.
#:
#: Stated in full and deliberately not derived from the live file. SPEC-001 and
#: REPO-001 had passed, GRAPH-001 was in flight, and nothing behind it had run:
#: nodes carrying pre-graph code sat in UNVERIFIED-UNDER-GRAPH, and the rest had
#: never been started. Nodes absent here keep their live status, which for the
#: two foundation nodes is PASSED forever.
#:
#: Rewinding GRAPH-001 alone is what this replaces. That left every downstream
#: node at whatever it had reached since, so the "historical" state drifted with
#: the project and the frontier tests built on it had to be rewritten at each
#: transition.
PRE_FAN_OUT: Mapping[str, NodeStatus] = {
    "GRAPH-001": NodeStatus.VERIFYING,
    "DATA-001": NodeStatus.UNVERIFIED_UNDER_GRAPH,
    "RESEARCH-001": NodeStatus.PENDING,
    "EVIDENCE-001": NodeStatus.UNVERIFIED_UNDER_GRAPH,
    "GHIDRA-001": NodeStatus.UNVERIFIED_UNDER_GRAPH,
    "EVAL-STATIC-001": NodeStatus.PENDING,
    "TOOLS-001": NodeStatus.PENDING,
    "INTEGRATION-STATIC-001": NodeStatus.PENDING,
    "GATE-STATIC-MVP": NodeStatus.PENDING,
}


def simulate(graph: Graph, statuses: Mapping[str, NodeStatus]) -> Graph:
    """A copy of `graph` holding several statuses at once.

    `Graph.with_status` sets one node, and a state worth reasoning about names
    several. Stating them together is what stops a simulated state from
    inheriting live progress through the nodes nobody remembered to mention.
    """
    for node_id, status in statuses.items():
        graph = graph.with_status(node_id, status)
    return graph


def statuses_of(graph: Graph) -> dict[str, NodeStatus]:
    """Every node's status, for comparing two simulated states."""
    return {node.id: node.status for node in graph}


def descendants(graph: Graph, node_id: str) -> set[str]:
    """Every node reachable downstream of this one."""
    found: set[str] = set()
    frontier = [node_id]
    while frontier:
        for dependent in graph.dependents_of(frontier.pop()):
            if dependent not in found:
                found.add(dependent)
                frontier.append(dependent)
    return found


def line_for(rendered: str, node_id: str) -> str:
    """The single rendered line describing a node."""
    matches = [line for line in rendered.splitlines() if line.startswith(node_id)]
    assert len(matches) == 1, f"expected exactly one line for {node_id}, got {matches}"
    return matches[0]


@pytest.fixture
def graph() -> Graph:
    return load_graph()


@pytest.fixture
def graph_001_held(graph: Graph) -> Graph:
    """The live graph rewound to while GRAPH-001 was still in flight.

    A complete state, not a single edit: see `PRE_FAN_OUT`.
    """
    return simulate(graph, PRE_FAN_OUT)


@pytest.fixture
def fan_out_open(graph_001_held: Graph) -> Graph:
    """The moment after GRAPH-001 passed, before any fan-out node was verified."""
    return graph_001_held.with_status("GRAPH-001", NodeStatus.PASSED)


# --- invariants that hold regardless of how far the project has advanced ---


def test_foundation_nodes_are_passed(graph: Graph) -> None:
    """SPEC-001 and REPO-001 are done and never revert.

    The one live status fact these tests lean on, and an intentionally permanent
    one: reading it cannot make a test transition-sensitive.
    """
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


# --- the rewound state itself ---


def test_the_rewind_covers_everything_behind_graph_001(graph: Graph) -> None:
    """The historical state must name every node it is responsible for.

    Anything downstream of GRAPH-001 that `PRE_FAN_OUT` forgets would keep its
    live status inside a state meant to predate it, and every frontier test
    built on the fixture would start tracking today's progress again. A node
    added behind GRAPH-001 fails here, once, instead of there.
    """
    assert set(PRE_FAN_OUT) == {"GRAPH-001"} | descendants(graph, "GRAPH-001")


def test_the_rewind_reproduces_the_pre_fan_out_state(graph_001_held: Graph) -> None:
    """GRAPH-001 in flight, its foundation behind it, nothing else started."""
    assert graph_001_held.node("GRAPH-001").status is NodeStatus.VERIFYING
    assert set(passed_nodes(graph_001_held)) == {"SPEC-001", "REPO-001"}
    assert ready_nodes(graph_001_held) == ()
    assert blocked_nodes(graph_001_held) == ()


# --- the unlocking rule, checked against simulated states ---


@pytest.mark.parametrize("node_id", FAN_OUT)
def test_fan_out_waits_while_graph_001_is_in_flight(graph_001_held: Graph, node_id: str) -> None:
    assert is_ready(graph_001_held, node_id) is False
    assert unmet_dependencies(graph_001_held, node_id) == ("GRAPH-001",)


@pytest.mark.parametrize("node_id", FAN_OUT)
def test_fan_out_opens_once_graph_001_passes(fan_out_open: Graph, node_id: str) -> None:
    assert is_ready(fan_out_open, node_id) is True


def test_exactly_the_fan_out_opens_when_graph_001_passes(graph_001_held: Graph) -> None:
    assert newly_ready_if_passed(graph_001_held, "GRAPH-001") == FAN_OUT


def test_nothing_is_ready_while_graph_001_is_held(graph_001_held: Graph) -> None:
    assert ready_nodes(graph_001_held) == ()


@pytest.mark.parametrize("ghidra_status", EXECUTABLE_STATES)
def test_ghidra_stays_unready_until_data_passes(graph: Graph, ghidra_status: NodeStatus) -> None:
    """DATA-001 passing is the thing that makes GHIDRA-001 graph-eligible.

    Simulated rather than read off the live graph: this is a statement about the
    edge, and it has to keep holding after DATA-001 really does pass. Both
    executable states are checked so the result cannot depend on which one
    GHIDRA-001 is sitting in.
    """
    waiting = simulate(
        graph,
        {
            "REPO-001": NodeStatus.PASSED,
            "DATA-001": NodeStatus.UNVERIFIED_UNDER_GRAPH,
            "GHIDRA-001": ghidra_status,
        },
    )

    assert is_ready(waiting, "GHIDRA-001") is False
    assert unmet_dependencies(waiting, "GHIDRA-001") == ("DATA-001",)

    after_data = waiting.with_status("DATA-001", NodeStatus.PASSED)

    assert unmet_dependencies(after_data, "GHIDRA-001") == ()
    assert is_ready(after_data, "GHIDRA-001") is True


def test_unverified_under_graph_does_not_satisfy_a_dependency(graph: Graph) -> None:
    """The rule that makes the first gate mean anything.

    Candidate implementation is not a verified prerequisite, so a node holding
    it must not unlock anything downstream. Asserted against a simulated
    DATA-001, because the live one is only in that state until it is verified.
    """
    candidate = simulate(
        graph,
        {
            "REPO-001": NodeStatus.PASSED,
            "DATA-001": NodeStatus.UNVERIFIED_UNDER_GRAPH,
            "GHIDRA-001": NodeStatus.UNVERIFIED_UNDER_GRAPH,
        },
    )

    assert satisfies_dependency(NodeStatus.UNVERIFIED_UNDER_GRAPH) is False
    assert unmet_dependencies(candidate, "GHIDRA-001") == ("DATA-001",)
    assert is_ready(candidate, "GHIDRA-001") is False


@pytest.mark.parametrize("node_id", FAN_OUT)
def test_unverified_nodes_are_themselves_executable(fan_out_open: Graph, node_id: str) -> None:
    """Pre-graph code still has to be re-verified, so its node must be assignable.

    Being unverified blocks a node's dependents, never the node itself: with its
    prerequisite passed, a node holding candidate code belongs in the frontier.
    """
    candidate = fan_out_open.with_status(node_id, NodeStatus.UNVERIFIED_UNDER_GRAPH)

    assert candidate.node(node_id).status is NodeStatus.UNVERIFIED_UNDER_GRAPH
    assert is_ready(candidate, node_id) is True
    assert node_id in ready_nodes(candidate)


@pytest.mark.parametrize("node_id", FAN_OUT)
def test_passing_a_node_takes_it_out_of_the_frontier(fan_out_open: Graph, node_id: str) -> None:
    """PASSED unlocks dependents; it does not leave the node itself assignable."""
    assert is_ready(fan_out_open, node_id) is True

    done = fan_out_open.with_status(node_id, NodeStatus.PASSED)

    assert is_ready(done, node_id) is False
    assert node_id not in ready_nodes(done)


@pytest.mark.parametrize("status", [NodeStatus.FAILED, NodeStatus.BLOCKED, NodeStatus.NEEDS_HUMAN])
def test_no_hard_stop_state_unlocks_a_dependent(graph_001_held: Graph, status: NodeStatus) -> None:
    stopped = graph_001_held.with_status("GRAPH-001", status)

    assert satisfies_dependency(status) is False
    for node_id in FAN_OUT:
        assert is_ready(stopped, node_id) is False


def test_a_failed_dependency_obstructs_everything_downstream(fan_out_open: Graph) -> None:
    failed = fan_out_open.with_status("DATA-001", NodeStatus.FAILED)

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


# --- regression: a real status transition must not invalidate these tests ---


@pytest.mark.parametrize("status", list(NodeStatus))
def test_the_rewind_ignores_whatever_data_001_has_reached(graph: Graph, status: NodeStatus) -> None:
    """The repair itself, guarded.

    The fixture used to rewind GRAPH-001 alone and inherit every downstream live
    status, so simulating DATA-001 as PASSED changed the historical state and
    broke eight tests that had nothing to do with DATA-001. Advancing DATA-001
    to any status — PASSED included — must now leave the rewound state
    byte-for-byte identical.
    """
    advanced = graph.with_status("DATA-001", status)

    assert statuses_of(simulate(advanced, PRE_FAN_OUT)) == statuses_of(simulate(graph, PRE_FAN_OUT))


@pytest.mark.parametrize("node_id", (*FAN_OUT, "GHIDRA-001", "EVAL-STATIC-001"))
def test_frontier_behaviour_survives_downstream_progress(graph: Graph, node_id: str) -> None:
    """No node passing may change what the pre-fan-out tests prove."""
    held = simulate(graph.with_status(node_id, NodeStatus.PASSED), PRE_FAN_OUT)

    assert ready_nodes(held) == ()
    assert render_ready(held) == "No nodes are ready."
    assert newly_ready_if_passed(held, "GRAPH-001") == FAN_OUT
    assert ready_nodes(held.with_status("GRAPH-001", NodeStatus.PASSED)) == FAN_OUT


def test_data_001_passing_opens_exactly_ghidra_001(fan_out_open: Graph) -> None:
    """The next real transition, simulated end to end.

    Verifying DATA-001 from the state the fan-out opened in puts GHIDRA-001 —
    and only GHIDRA-001 — into the frontier, while DATA-001 itself leaves it.
    EVAL-STATIC-001 keeps waiting, because it also needs GHIDRA-001.
    """
    assert newly_ready_if_passed(fan_out_open, "DATA-001") == ("GHIDRA-001",)

    after_data = fan_out_open.with_status("DATA-001", NodeStatus.PASSED)

    assert is_ready(after_data, "GHIDRA-001") is True
    assert is_ready(after_data, "DATA-001") is False
    assert is_ready(after_data, "EVAL-STATIC-001") is False
    assert ready_nodes(after_data) == ("RESEARCH-001", "EVIDENCE-001", "GHIDRA-001")


# --- rendering ---


def test_status_table_covers_every_node(graph: Graph) -> None:
    rendered = render_status_table(graph)

    assert len(rendered.splitlines()) == len(graph)
    for node in graph:
        assert node.id in rendered


def test_status_table_explains_waiting(graph_001_held: Graph) -> None:
    rendered = render_status_table(graph_001_held)

    for node_id in FAN_OUT:
        assert line_for(rendered, node_id).endswith("(waiting on GRAPH-001)")


def test_status_table_marks_the_frontier(fan_out_open: Graph) -> None:
    rendered = render_status_table(fan_out_open)

    assert ready_nodes(fan_out_open) == FAN_OUT
    for node_id in FAN_OUT:
        assert line_for(rendered, node_id).endswith("(ready)")
    assert line_for(rendered, "GHIDRA-001").endswith("(waiting on DATA-001)")


def test_status_table_names_the_obstruction(fan_out_open: Graph) -> None:
    failed = fan_out_open.with_status("DATA-001", NodeStatus.FAILED)

    rendered = render_status_table(failed)

    assert line_for(rendered, "DATA-001").endswith(NodeStatus.FAILED.value)
    assert line_for(rendered, "GHIDRA-001").endswith("(blocked by DATA-001)")


def test_ready_rendering_reports_an_empty_frontier(graph_001_held: Graph) -> None:
    assert render_ready(graph_001_held) == "No nodes are ready."


def test_ready_rendering_lists_the_frontier(fan_out_open: Graph) -> None:
    rendered = render_ready(fan_out_open)
    lines = rendered.splitlines()

    assert tuple(line.split()[0] for line in lines) == FAN_OUT
    assert "Synthetic firmware laboratory" in rendered


def test_a_root_node_with_no_dependencies_is_ready() -> None:
    graph = load_graph_text(graph_text(node_block("A-001")))

    assert ready_nodes(graph) == ("A-001",)
