"""Ownership safety for parallel execution.

Two workers running concurrently must never be allowed to edit the same file.
The graph is where that is decided, so it is where it is checked — before a
fan-out starts rather than after two branches conflict.

Nodes in a dependency order cannot collide, because the second never starts
until the first has passed. Only independent nodes need disjoint ownership.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from support import graph_text, node_block

from graph import (
    GraphValidationError,
    can_run_concurrently,
    find_ownership_overlaps,
    load_graph,
    load_graph_text,
    paths_overlap,
)


def _owned(node_id: str, *paths: str, depends_on: tuple[str, ...] = ()) -> str:
    """A node block carrying allowed paths.

    Paths are quoted because a bare `**` begins with YAML's alias token, and the
    loader refuses ambiguous syntax rather than guessing at it.
    """
    block = [node_block(node_id, depends_on=depends_on)]
    block.append("    allowed_paths:")
    block.extend(f'      - "{path}"' for path in paths)
    return "\n".join(block)


# --- the live graph ---


def test_the_project_graph_has_no_unsafe_overlap() -> None:
    assert find_ownership_overlaps(load_graph()) == []


def test_the_current_fan_out_owns_disjoint_paths() -> None:
    """The three GRAPH-001 dependents can be assigned together.

    Siblings with no edge between them, so the graph never orders their work:
    whenever more than one is eligible they run concurrently, and that is a
    property of the edges rather than of anyone's current status.
    """
    graph = load_graph()
    fan_out = ("DATA-001", "RESEARCH-001", "EVIDENCE-001")

    for first in fan_out:
        for second in fan_out:
            if first == second:
                continue
            assert can_run_concurrently(graph, first, second) is True
            for left in graph.node(first).allowed_paths:
                for right in graph.node(second).allowed_paths:
                    assert not paths_overlap(left, right), (
                        f"{first}:{left} overlaps {second}:{right}"
                    )


def test_evidence_owns_the_code_it_must_change() -> None:
    """Its contract targets store.py and models.py, not just the shim package."""
    owned = set(load_graph().node("EVIDENCE-001").allowed_paths)

    assert "src/ecu_recovery/store.py" in owned
    assert "src/ecu_recovery/models.py" in owned
    assert "tests/test_store_report.py" in owned


def test_report_py_stays_outside_evidence_ownership() -> None:
    """A schema change must not silently alter what the report claims."""
    owned = set(load_graph().node("EVIDENCE-001").allowed_paths)

    assert "src/ecu_recovery/report.py" not in owned


def test_data_no_longer_owns_the_whole_test_tree() -> None:
    owned = set(load_graph().node("DATA-001").allowed_paths)

    assert "tests/**" not in owned
    assert "tests/test_synthetic_lab.py" in owned


def test_prompt_contracts_restate_the_canonical_paths() -> None:
    """Guards against the graph and a node contract drifting apart.

    The graph file is canonical; a prompt restates its node's paths for the
    worker. Restating invites drift, so the restatement is checked.
    """
    graph = load_graph()
    repository = Path(__file__).resolve().parents[2]
    for node in graph:
        if not node.prompt or not node.allowed_paths:
            continue
        contract = (repository / str(node.prompt)).read_text(encoding="utf-8")
        for path in node.allowed_paths:
            assert path in contract, f"{node.prompt} does not mention {path!r}"


#: The scorer's own fixture corpus. It exists to prove the detector finds
#: planted defects, and every reply in it is scripted.
AUTHORED_CORPUS = "tests/evaluation/agent/transcripts/**"


def test_the_gate_names_the_baseline_it_scores() -> None:
    """`GATE-AGENT-MVP` owns no paths, so it must name the ones it reads.

    The gate is the one node whose evidence is not its own ownership, which
    means nothing else here would notice it drifting onto a different corpus.
    Its sources are derived from the nodes that produce them, so renaming a
    baseline tree in the graph breaks this until the gate contract follows.

    The authored corpus is named too, as an exclusion: the failure mode this
    guards against is not a gate that reads nothing, it is a gate that quietly
    falls back to the fixtures that were always going to pass.
    """
    graph = load_graph()
    repository = Path(__file__).resolve().parents[2]
    contract = (repository / str(graph.node("GATE-AGENT-MVP").prompt)).read_text(encoding="utf-8")

    transcripts = [
        path for path in graph.node("BASELINE-AGENT-001").allowed_paths if "transcripts" in path
    ]
    reviews = list(graph.node("REVIEW-AGENT-BASELINE-001").allowed_paths)
    assert transcripts, "BASELINE-AGENT-001 owns no transcript tree for the gate to score"
    assert reviews, "REVIEW-AGENT-BASELINE-001 owns no review tree for the gate to read"

    for path in (*transcripts, *reviews):
        assert path in contract, f"GATE-AGENT-MVP does not name its evidence source {path!r}"

    assert AUTHORED_CORPUS in contract, (
        "GATE-AGENT-MVP must name the authored corpus to exclude it by name"
    )
    assert "REVIEW-AGENT-BASELINE-001" in graph.node("GATE-AGENT-MVP").depends_on


# --- the rule, on synthetic graphs ---


def test_the_original_bug_is_caught() -> None:
    """The exact case this check was added for.

    `tests/**` against `tests/evidence/**` between two nodes that fan out from
    the same parent: the whole tree contains the subtree, so both workers could
    edit the same file.
    """
    text = graph_text(
        _owned("PARENT-001", "graph/**"),
        _owned("DATA-001", "samples/**", "tests/**", depends_on=("PARENT-001",)),
        _owned("EVIDENCE-001", "tests/evidence/**", depends_on=("PARENT-001",)),
    )

    with pytest.raises(GraphValidationError, match="overlapping paths") as caught:
        load_graph_text(text)

    message = str(caught.value)
    assert "DATA-001" in message
    assert "EVIDENCE-001" in message
    assert "tests/**" in message


def test_an_ordered_pair_may_share_ownership() -> None:
    """A dependent never runs beside its prerequisite, so overlap is harmless."""
    text = graph_text(
        _owned("FIRST-001", "tests/**"),
        _owned("SECOND-001", "tests/evidence/**", depends_on=("FIRST-001",)),
    )

    graph = load_graph_text(text)

    assert can_run_concurrently(graph, "FIRST-001", "SECOND-001") is False
    assert find_ownership_overlaps(graph) == []


def test_transitively_ordered_nodes_may_share_ownership() -> None:
    text = graph_text(
        _owned("A-001", "src/**"),
        _owned("B-001", "docs/**", depends_on=("A-001",)),
        _owned("C-001", "src/thing.py", depends_on=("B-001",)),
    )

    assert find_ownership_overlaps(load_graph_text(text)) == []


def test_identical_ownership_between_independent_nodes_is_rejected() -> None:
    text = graph_text(
        _owned("A-001", "samples/**"),
        _owned("B-001", "samples/**"),
    )

    with pytest.raises(GraphValidationError, match="overlapping paths"):
        load_graph_text(text)


def test_a_node_owning_everything_collides_with_all_peers() -> None:
    text = graph_text(_owned("A-001", "**"), _owned("B-001", "docs/research/**"))

    with pytest.raises(GraphValidationError, match="overlapping paths"):
        load_graph_text(text)


def test_nodes_without_declared_paths_never_collide() -> None:
    text = graph_text(node_block("A-001"), node_block("B-001"))

    assert find_ownership_overlaps(load_graph_text(text)) == []


@pytest.mark.parametrize(
    "left,right",
    [
        ("tests/**", "tests/evidence/**"),
        ("tests/evidence/**", "tests/**"),
        ("samples/**", "samples/**"),
        ("src/a", "src/a/b/c.py"),
        ("**", "anything/at/all"),
        ("docs/x.md", "docs/x.md"),
    ],
)
def test_overlapping_patterns(left: str, right: str) -> None:
    assert paths_overlap(left, right) is True


@pytest.mark.parametrize(
    "left,right",
    [
        ("samples/**", "scripts/**"),
        ("docs/research/**", "docs/synthetic-lab.md"),
        ("tests/test_synthetic_lab.py", "tests/test_store_report.py"),
        ("src/ecu_recovery/evidence/**", "src/ecu_recovery/store.py"),
        ("src/ecu_recovery/analysis/**", "src/ecu_recovery/models.py"),
        # A shared prefix inside a filename is not a shared directory.
        ("tests/test_a.py", "tests/test_ab.py"),
    ],
)
def test_non_overlapping_patterns(left: str, right: str) -> None:
    assert paths_overlap(left, right) is False


def test_trailing_slash_and_star_forms_are_equivalent() -> None:
    assert paths_overlap("tests/", "tests/**") is True
    assert paths_overlap("tests", "tests/evidence/**") is True
