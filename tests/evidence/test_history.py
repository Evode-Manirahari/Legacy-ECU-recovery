"""The central requirement: a belief change must never destroy the old belief.

MASTER_SPEC section 23 - "Every hypothesis change must preserve history. Do not
silently overwrite previous belief state."
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from evidence_support import investigation

from ecu_recovery.models import Certainty, Hypothesis, HypothesisStatus
from ecu_recovery.store import InvestigationStore


def _initial(store: InvestigationStore, binary_id: int) -> str:
    revision = store.save_hypothesis(
        binary_id,
        Hypothesis(
            subject="FUN_923A",
            claim="possible engine-speed calculation",
            certainty=Certainty.INFERRED,
            confidence=0.55,
            evidence=("called from a timer-related routine",),
            uncertainty="exact scaling formula",
        ),
    )
    assert revision.revision == 1
    return revision.key


def test_revision_preserves_the_previous_belief(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    key = _initial(store, binary_id)

    store.revise_hypothesis(
        binary_id,
        key,
        confidence=0.88,
        status=HypothesisStatus.SUPPORTED,
        reason="timer capture register read confirmed by a second pass",
    )

    history = store.hypothesis_history(binary_id, key)
    assert [entry.revision for entry in history] == [1, 2]
    assert history[0].confidence == 0.55
    assert history[0].status is HypothesisStatus.UNTESTED
    assert history[1].confidence == 0.88
    assert history[1].status is HypothesisStatus.SUPPORTED
    assert history[1].supersedes_id == history[0].id


def test_revision_records_why_the_system_changed_its_mind(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    key = _initial(store, binary_id)
    store.revise_hypothesis(
        binary_id,
        key,
        status=HypothesisStatus.REJECTED,
        confidence=0.05,
        reason="pulse-frequency sweep produced no correlated output",
    )

    history = store.hypothesis_history(binary_id, key)

    assert history[0].change_reason == "initial assertion"
    assert history[1].change_reason == "pulse-frequency sweep produced no correlated output"


def test_a_revision_without_a_reason_is_refused(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    key = _initial(store, binary_id)
    with pytest.raises(ValueError, match="why the belief changed"):
        store.revise_hypothesis(binary_id, key, confidence=0.9, reason="   ")


def test_current_belief_is_the_newest_revision(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    key = _initial(store, binary_id)
    store.revise_hypothesis(binary_id, key, confidence=0.88, reason="second pass")
    store.revise_hypothesis(binary_id, key, confidence=0.20, reason="counter-example found")

    current = store.current_hypothesis(binary_id, key)

    assert current is not None
    assert current.revision == 3
    # Newest, not highest-confidence: a belief that weakened is still current.
    assert current.confidence == 0.20


def test_confirmed_belief_can_still_be_overturned(tmp_path: Path) -> None:
    """Nothing in the model forbids it; the history is what records the path."""
    store, binary_id = investigation(tmp_path)
    key = _initial(store, binary_id)
    store.revise_hypothesis(
        binary_id,
        key,
        status=HypothesisStatus.CONFIRMED,
        confidence=1.0,
        reason="bench measurement matched prediction",
    )
    store.revise_hypothesis(
        binary_id,
        key,
        status=HypothesisStatus.REJECTED,
        confidence=0.0,
        reason="bench rig was miswired; measurement retracted",
    )

    statuses = [entry.status for entry in store.hypothesis_history(binary_id, key)]
    assert statuses == [
        HypothesisStatus.UNTESTED,
        HypothesisStatus.CONFIRMED,
        HypothesisStatus.REJECTED,
    ]


def test_restating_the_same_claim_revises_rather_than_duplicates(tmp_path: Path) -> None:
    """The pre-graph store appended a second, indistinguishable row here."""
    store, binary_id = investigation(tmp_path)
    first = store.save_hypothesis(
        binary_id, Hypothesis("FUN_8000", "init routine", Certainty.INFERRED, 0.6)
    )
    second = store.save_hypothesis(
        binary_id, Hypothesis("FUN_8000", "init routine", Certainty.INFERRED, 0.75)
    )

    assert second.key == first.key
    assert second.revision == 2
    assert len(store.current_hypotheses(binary_id)) == 1


def test_a_different_claim_about_one_subject_is_a_different_hypothesis(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    first = store.save_hypothesis(
        binary_id, Hypothesis("FUN_8000", "init routine", Certainty.INFERRED, 0.6)
    )
    second = store.save_hypothesis(
        binary_id, Hypothesis("FUN_8000", "watchdog kick", Certainty.INFERRED, 0.3)
    )

    assert first.key != second.key
    assert len(store.current_hypotheses(binary_id)) == 2


def test_current_hypotheses_excludes_superseded_revisions(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    key = _initial(store, binary_id)
    store.revise_hypothesis(binary_id, key, confidence=0.88, reason="second pass")
    store.save_hypothesis(
        binary_id, Hypothesis("FUN_8000", "init routine", Certainty.INFERRED, 0.6)
    )

    current = store.current_hypotheses(binary_id)

    assert len(current) == 2
    assert {entry.confidence for entry in current} == {0.88, 0.6}


def test_created_at_survives_revision_while_updated_at_moves(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    key = _initial(store, binary_id)
    store.revise_hypothesis(binary_id, key, confidence=0.88, reason="second pass")

    history = store.hypothesis_history(binary_id, key)

    assert history[1].created_at == history[0].created_at
    assert history[1].updated_at >= history[0].updated_at


def test_direct_update_of_a_belief_is_refused_by_the_database(tmp_path: Path) -> None:
    """The guarantee has to hold against SQL, not just against the Python API."""
    store, binary_id = investigation(tmp_path)
    _initial(store, binary_id)

    with pytest.raises(sqlite3.IntegrityError, match="append-only"), store.connect() as connection:
        connection.execute("UPDATE hypotheses SET confidence = 0.99")


def test_revising_an_unknown_hypothesis_is_an_error(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    with pytest.raises(KeyError, match="does not exist"):
        store.revise_hypothesis(binary_id, "H-404", confidence=0.5, reason="typo")


def test_revision_carries_unnamed_fields_forward(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    key = _initial(store, binary_id)

    store.revise_hypothesis(binary_id, key, confidence=0.88, reason="second pass")

    current = store.current_hypothesis(binary_id, key)
    assert current is not None
    assert current.claim == "possible engine-speed calculation"
    assert current.uncertainty == "exact scaling formula"
    assert current.evidence == ("called from a timer-related routine",)
