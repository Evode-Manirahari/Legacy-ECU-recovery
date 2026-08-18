"""Evidence-to-hypothesis traceability.

MASTER_SPEC section 39 - "No important AI conclusion should exist without
traceable evidence" - and its worked example, which reports supporting and
contradicting evidence separately.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from evidence_support import investigation

from ecu_recovery.models import (
    Certainty,
    Evidence,
    EvidenceKind,
    EvidenceStance,
    Hypothesis,
    HypothesisStatus,
    Relationship,
)
from ecu_recovery.store import InvestigationStore


def _observe(store: InvestigationStore, binary_id: int, key: str, summary: str) -> None:
    store.save_evidence(
        binary_id,
        Evidence(
            key=key,
            kind=EvidenceKind.CROSS_REFERENCE,
            summary=summary,
            source="ghidra",
            mechanically_observed=True,
        ),
    )


def test_evidence_is_addressable_and_typed(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    store.save_evidence(
        binary_id,
        Evidence(
            key="E-014",
            kind=EvidenceKind.CALL_GRAPH,
            summary="called from a timer-related routine",
            source="ghidra",
            mechanically_observed=True,
            detail="caller FUN_9100 at 0x9134",
            function_address=0x923A,
        ),
    )

    recorded = store.evidence_for_binary(binary_id)

    assert len(recorded) == 1
    assert recorded[0].key == "E-014"
    assert recorded[0].kind is EvidenceKind.CALL_GRAPH
    assert recorded[0].function_address == 0x923A


def test_mechanically_observed_fact_is_separable_from_interpretation(tmp_path: Path) -> None:
    """The fact/evidence line the project depends on has to be queryable."""
    store, binary_id = investigation(tmp_path)
    _observe(store, binary_id, "E-001", "reads timer capture register")
    store.save_evidence(
        binary_id,
        Evidence(
            key="E-002",
            kind=EvidenceKind.EXPERT_REVIEW,
            summary="reviewer reads this as an RPM path",
            source="human reviewer",
            mechanically_observed=False,
        ),
    )

    assert len(store.evidence_for_binary(binary_id)) == 2
    mechanical = store.evidence_for_binary(binary_id, mechanical_only=True)
    assert [item.key for item in mechanical] == ["E-001"]


def test_supporting_and_contradicting_evidence_are_distinguished(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    _observe(store, binary_id, "E-014", "called from a timer-related routine")
    _observe(store, binary_id, "E-021", "reads timer capture register")
    _observe(store, binary_id, "E-099", "also reached from the fuel-trim path")

    revision = store.save_hypothesis(
        binary_id,
        Hypothesis(
            subject="FUN_923A",
            claim="possible engine-speed calculation",
            certainty=Certainty.INFERRED,
            confidence=0.88,
            status=HypothesisStatus.SUPPORTED,
        ),
        supporting=("E-014", "E-021"),
        contradicting=("E-099",),
    )

    cited = store.evidence_for_revision(revision.id)
    stances = {item.key: stance for item, stance in cited}

    assert stances == {
        "E-014": EvidenceStance.SUPPORTS,
        "E-021": EvidenceStance.SUPPORTS,
        "E-099": EvidenceStance.CONTRADICTS,
    }


def test_one_observation_can_bear_on_two_claims_differently(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    _observe(store, binary_id, "E-050", "writes to 0xFFFF8004 every 10ms")

    timer = store.save_hypothesis(
        binary_id,
        Hypothesis("FUN_A", "periodic timer service", Certainty.INFERRED, 0.7),
        supporting=("E-050",),
    )
    oneshot = store.save_hypothesis(
        binary_id,
        Hypothesis("FUN_A", "one-shot initialisation", Certainty.INFERRED, 0.1),
        contradicting=("E-050",),
    )

    assert store.evidence_for_revision(timer.id)[0][1] is EvidenceStance.SUPPORTS
    assert store.evidence_for_revision(oneshot.id)[0][1] is EvidenceStance.CONTRADICTS


def test_a_revision_keeps_the_basis_of_the_belief_it_replaced(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    _observe(store, binary_id, "E-014", "called from a timer-related routine")
    _observe(store, binary_id, "E-037", "output tracks simulated pulse frequency")
    first = store.save_hypothesis(
        binary_id,
        Hypothesis("FUN_923A", "engine-speed calculation", Certainty.INFERRED, 0.55),
        supporting=("E-014",),
    )

    second = store.revise_hypothesis(
        binary_id,
        first.key,
        confidence=0.88,
        status=HypothesisStatus.SUPPORTED,
        supporting=("E-037",),
        reason="frequency sweep produced a matching output",
    )

    # Revision 1 still shows only what was known then.
    assert [item.key for item, _ in store.evidence_for_revision(first.id)] == ["E-014"]
    # Revision 2 carries the earlier basis forward alongside the new evidence.
    assert [item.key for item, _ in store.evidence_for_revision(second.id)] == ["E-014", "E-037"]


def test_citing_unrecorded_evidence_is_refused(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    with pytest.raises(KeyError, match="not recorded"):
        store.save_hypothesis(
            binary_id,
            Hypothesis("FUN_1", "a claim", Certainty.INFERRED, 0.5),
            supporting=("E-does-not-exist",),
        )


def test_a_refused_citation_leaves_no_hypothesis_behind(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    with pytest.raises(KeyError):
        store.save_hypothesis(
            binary_id,
            Hypothesis("FUN_1", "a claim", Certainty.INFERRED, 0.5),
            supporting=("E-missing",),
        )
    assert store.current_hypotheses(binary_id) == []


def test_evidence_cannot_be_recorded_twice_under_one_key(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    _observe(store, binary_id, "E-014", "called from a timer-related routine")
    with pytest.raises(ValueError, match="immutable"):
        _observe(store, binary_id, "E-014", "actually it was something else")


def test_direct_update_of_evidence_is_refused_by_the_database(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    _observe(store, binary_id, "E-014", "called from a timer-related routine")

    with pytest.raises(sqlite3.IntegrityError, match="immutable"), store.connect() as connection:
        connection.execute("UPDATE evidence SET summary = 'rewritten'")


def test_relationships_carry_confidence_and_evidence(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    _observe(store, binary_id, "E-014", "call site at 0x9134")

    store.save_relationship(
        binary_id,
        Relationship("FUN_9100", "calls", "FUN_923A", 0.95, evidence=("E-014",)),
    )

    relationships = store.current_relationships(binary_id)
    assert len(relationships) == 1
    assert relationships[0].subject == "FUN_9100"
    assert relationships[0].predicate == "calls"
    assert relationships[0].object == "FUN_923A"
    assert relationships[0].confidence == 0.95
    assert relationships[0].evidence == ("E-014",)


def test_reasserting_a_relationship_revises_rather_than_overwrites(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    store.save_relationship(binary_id, Relationship("FUN_A", "calls", "FUN_B", 0.6))
    store.save_relationship(
        binary_id,
        Relationship("FUN_A", "calls", "FUN_B", 0.9),
        reason="second decompilation pass agreed",
    )

    history = store.relationship_history(binary_id, "FUN_A", "calls", "FUN_B")

    assert [(revision, confidence) for revision, confidence, _ in history] == [(1, 0.6), (2, 0.9)]
    assert history[1][2] == "second decompilation pass agreed"
    assert len(store.current_relationships(binary_id)) == 1
    assert store.current_relationships(binary_id)[0].confidence == 0.9


def test_relationship_citing_unrecorded_evidence_is_refused(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    with pytest.raises(KeyError, match="not recorded"):
        store.save_relationship(
            binary_id, Relationship("FUN_A", "calls", "FUN_B", 0.6, evidence=("E-nope",))
        )


def test_a_restated_stance_replaces_the_carried_forward_one(tmp_path: Path) -> None:
    """Deciding an observation now cuts the other way is itself a belief change."""
    store, binary_id = investigation(tmp_path)
    _observe(store, binary_id, "E-014", "writes 0xFFFF8004 on every pass")
    first = store.save_hypothesis(
        binary_id,
        Hypothesis("FUN_A", "periodic timer service", Certainty.INFERRED, 0.7),
        supporting=("E-014",),
    )

    second = store.revise_hypothesis(
        binary_id,
        first.key,
        confidence=0.2,
        status=HypothesisStatus.WEAKENED,
        contradicting=("E-014",),
        reason="that register turned out to be a watchdog, not a timer",
    )

    # The old revision keeps the stance it was decided on.
    assert store.evidence_for_revision(first.id)[0][1] is EvidenceStance.SUPPORTS
    # The new revision reflects the reversal rather than the carried-forward stance.
    assert store.evidence_for_revision(second.id) == [
        (store.evidence_for_binary(binary_id)[0], EvidenceStance.CONTRADICTS)
    ]
