"""The worked example from MASTER_SPEC section 39, end to end.

If the evidence model cannot represent the example the specification uses to
describe itself, it is the wrong model. Everything here is deterministic: no
analysis engine, no sample binary, no network.
"""

from __future__ import annotations

from pathlib import Path

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

OBSERVATIONS = (
    ("E-014", EvidenceKind.CALL_GRAPH, "called from timer-related routine"),
    ("E-021", EvidenceKind.MEMORY_ACCESS, "reads timer capture register"),
    ("E-037", EvidenceKind.EXPERIMENT_RESULT, "output changes with simulated pulse frequency"),
)


def test_hypothesis_104_is_fully_representable(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    for key, kind, summary in OBSERVATIONS:
        store.save_evidence(
            binary_id,
            Evidence(
                key=key,
                kind=kind,
                summary=summary,
                source="static analysis",
                mechanically_observed=True,
            ),
        )

    revision = store.save_hypothesis(
        binary_id,
        Hypothesis(
            subject="FUN_923A",
            claim="Possible engine-speed calculation.",
            certainty=Certainty.INFERRED,
            confidence=0.88,
            status=HypothesisStatus.SUPPORTED,
            uncertainty="exact scaling formula",
        ),
        key="H-104",
        supporting=("E-014", "E-021", "E-037"),
    )

    assert revision.key == "H-104"
    assert revision.subject == "FUN_923A"
    assert revision.claim == "Possible engine-speed calculation."
    assert revision.status is HypothesisStatus.SUPPORTED
    assert revision.confidence == 0.88
    assert revision.uncertainty == "exact scaling formula"

    cited = store.evidence_for_revision(revision.id)
    supporting = [item.key for item, stance in cited if stance is EvidenceStance.SUPPORTS]
    contradicting = [item.key for item, stance in cited if stance is EvidenceStance.CONTRADICTS]

    assert supporting == ["E-014", "E-021", "E-037"]
    assert contradicting == []  # "none currently", per the specification


def test_the_belief_can_then_be_weakened_and_the_old_state_still_shows(tmp_path: Path) -> None:
    """The next test in the example is a frequency sweep. Suppose it fails."""
    store, binary_id = investigation(tmp_path)
    store.save_evidence(
        binary_id,
        Evidence("E-014", EvidenceKind.CALL_GRAPH, "called from timer routine", "ghidra", True),
    )
    store.save_evidence(
        binary_id,
        Evidence(
            "E-052",
            EvidenceKind.EXPERIMENT_RESULT,
            "output flat across the expected operating range",
            "experiment engine",
            True,
        ),
    )
    store.save_hypothesis(
        binary_id,
        Hypothesis(
            "FUN_923A",
            "Possible engine-speed calculation.",
            Certainty.INFERRED,
            0.88,
            status=HypothesisStatus.SUPPORTED,
        ),
        key="H-104",
        supporting=("E-014",),
    )

    store.revise_hypothesis(
        binary_id,
        "H-104",
        status=HypothesisStatus.WEAKENED,
        confidence=0.30,
        uncertainty="what the timer read is actually used for",
        contradicting=("E-052",),
        reason="pulse-frequency sweep over the operating range produced no response",
    )

    history = store.hypothesis_history(binary_id, "H-104")
    assert [entry.status for entry in history] == [
        HypothesisStatus.SUPPORTED,
        HypothesisStatus.WEAKENED,
    ]
    assert [entry.confidence for entry in history] == [0.88, 0.30]
    # The reason the belief moved is recoverable, which is the whole point.
    assert "pulse-frequency sweep" in history[1].change_reason
    # And the evidence that moved it is attached to the revision that moved.
    stances = {item.key: stance for item, stance in store.evidence_for_revision(history[1].id)}
    assert stances["E-052"] is EvidenceStance.CONTRADICTS
    assert stances["E-014"] is EvidenceStance.SUPPORTS


def test_relationships_capture_the_call_structure_behind_the_claim(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    store.save_evidence(
        binary_id,
        Evidence("E-014", EvidenceKind.CALL_GRAPH, "call site at 0x9134", "ghidra", True),
    )

    store.save_relationship(
        binary_id,
        Relationship("FUN_9100", "calls", "FUN_923A", 1.0, evidence=("E-014",)),
    )
    store.save_relationship(
        binary_id,
        Relationship("FUN_923A", "reads", "TIMER_CAPTURE", 0.9, evidence=("E-014",)),
    )

    relationships = store.current_relationships(binary_id)

    assert [(r.subject, r.predicate, r.object) for r in relationships] == [
        ("FUN_9100", "calls", "FUN_923A"),
        ("FUN_923A", "reads", "TIMER_CAPTURE"),
    ]
    assert all(r.evidence == ("E-014",) for r in relationships)
