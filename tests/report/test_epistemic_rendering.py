"""Does the report say what the evidence model knows?

The gap this node repairs was not a crash or a wrong number. The report rendered
`Certainty` under the label "Status" and never showed `HypothesisStatus`, so a
belief the system had *rejected* printed exactly like one it had never tested.
A reader had no way to tell them apart, which makes the report worse than
silent: it reads as informative.

These tests hold the two axes apart and keep the revision chain visible.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ecu_recovery.intake import profile_binary
from ecu_recovery.models import (
    Certainty,
    Evidence,
    EvidenceKind,
    Hypothesis,
    HypothesisStatus,
)
from ecu_recovery.report import render_markdown
from ecu_recovery.store import InvestigationStore

ALL_STATUSES = (
    HypothesisStatus.UNTESTED,
    HypothesisStatus.SUPPORTED,
    HypothesisStatus.WEAKENED,
    HypothesisStatus.REJECTED,
    HypothesisStatus.CONFIRMED,
)


def investigation(tmp_path: Path) -> tuple[InvestigationStore, int]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    firmware = tmp_path / "fixture.rom"
    firmware.write_bytes(bytes(range(128)))
    store = InvestigationStore(tmp_path / "analysis.sqlite3")
    return store, store.save_profile(profile_binary(firmware))


def believe(
    store: InvestigationStore,
    binary_id: int,
    *,
    subject: str = "FUN_923A",
    claim: str = "engine-speed calculation",
    certainty: Certainty = Certainty.INFERRED,
    confidence: float = 0.55,
    supporting: tuple[str, ...] = (),
) -> str:
    revision = store.save_hypothesis(
        binary_id,
        Hypothesis(subject, claim, certainty, confidence),
        supporting=list(supporting),
    )
    return revision.key


# --- the two axes ---


def test_certainty_and_hypothesis_status_render_as_separate_concepts(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    key = believe(store, binary_id)
    store.revise_hypothesis(
        binary_id, key, status=HypothesisStatus.SUPPORTED, reason="a probe matched"
    )

    report = render_markdown(store, binary_id)

    assert "- Certainty: **inferred**" in report
    assert "- Hypothesis status: **supported**" in report
    # The old mislabelling must not come back.
    assert "- Status: **inferred**" not in report


def test_a_supported_belief_says_it_is_supported(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    key = believe(store, binary_id)
    store.revise_hypothesis(
        binary_id, key, status=HypothesisStatus.SUPPORTED, confidence=0.88, reason="matched"
    )

    report = render_markdown(store, binary_id)

    assert "- Hypothesis status: **supported**" in report
    assert "- Confidence: 88%" in report


def test_rejected_and_untested_do_not_render_identically(tmp_path: Path) -> None:
    """The defect, stated as a test. These two must never look the same."""
    untested_store, untested_id = investigation(tmp_path / "a")
    believe(untested_store, untested_id)

    rejected_store, rejected_id = investigation(tmp_path / "b")
    key = believe(rejected_store, rejected_id)
    rejected_store.revise_hypothesis(
        rejected_id, key, status=HypothesisStatus.REJECTED, reason="the probe contradicted it"
    )

    untested = render_markdown(untested_store, untested_id)
    rejected = render_markdown(rejected_store, rejected_id)

    assert untested != rejected
    assert "- Hypothesis status: **untested**" in untested
    assert "- Hypothesis status: **rejected**" in rejected
    assert "rejected" not in untested


@pytest.mark.parametrize("status", ALL_STATUSES)
def test_every_status_is_distinguishable_in_the_report(
    tmp_path: Path, status: HypothesisStatus
) -> None:
    store, binary_id = investigation(tmp_path)
    key = believe(store, binary_id)
    store.revise_hypothesis(binary_id, key, status=status, reason="a recorded reason")

    report = render_markdown(store, binary_id)

    assert f"- Hypothesis status: **{status.value}**" in report
    for other in ALL_STATUSES:
        if other is not status:
            assert f"- Hypothesis status: **{other.value}**" not in report


# --- belief history ---


def test_a_two_revision_hypothesis_exposes_its_history(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    key = believe(store, binary_id, confidence=0.55)
    store.revise_hypothesis(
        binary_id,
        key,
        status=HypothesisStatus.SUPPORTED,
        confidence=0.88,
        reason="frequency sweep matched",
    )

    report = render_markdown(store, binary_id)

    assert "Belief history" in report
    assert "| 1 | untested | 55% | initial assertion |" in report
    assert "| 2 (current) | supported | 88% | frequency sweep matched |" in report


def test_the_recorded_reason_a_belief_changed_is_rendered(tmp_path: Path) -> None:
    """Without the reason, a revision chain is a list of numbers nobody can argue with."""
    store, binary_id = investigation(tmp_path)
    key = believe(store, binary_id)
    store.revise_hypothesis(
        binary_id,
        key,
        status=HypothesisStatus.WEAKENED,
        reason="the second probe disagreed with the first",
    )

    report = render_markdown(store, binary_id)

    assert "the second probe disagreed with the first" in report


def test_a_single_revision_belief_gets_no_history_table(tmp_path: Path) -> None:
    """A belief that never moved has no story; a table would be noise on every report."""
    store, binary_id = investigation(tmp_path)
    believe(store, binary_id)

    report = render_markdown(store, binary_id)

    assert "Belief history" not in report
    assert "- Hypothesis status: **untested**" in report


def test_history_grows_with_each_revision(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    key = believe(store, binary_id)
    store.revise_hypothesis(binary_id, key, status=HypothesisStatus.SUPPORTED, reason="first")
    store.revise_hypothesis(binary_id, key, status=HypothesisStatus.REJECTED, reason="second")

    report = render_markdown(store, binary_id)

    assert "current revision is 3" in report
    assert "| 3 (current) | rejected |" in report
    assert "first" in report
    assert "second" in report


# --- current-belief semantics ---


def test_the_current_belief_stays_clearly_identifiable(tmp_path: Path) -> None:
    """History must never read as a second belief held at the same time."""
    store, binary_id = investigation(tmp_path)
    key = believe(store, binary_id, confidence=0.55)
    store.revise_hypothesis(
        binary_id, key, status=HypothesisStatus.CONFIRMED, confidence=0.95, reason="verified"
    )

    report = render_markdown(store, binary_id)

    # One headline belief, stated once, with the superseded confidence appearing
    # only inside the history table.
    assert report.count("- Hypothesis status: **confirmed**") == 1
    assert report.count("- Confidence: 95%") == 1
    assert "- Confidence: 55%" not in report
    assert "current revision is 2" in report
    assert report.count("(current)") == 1


def test_a_superseded_revision_is_not_rendered_as_its_own_hypothesis(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    key = believe(store, binary_id)
    store.revise_hypothesis(binary_id, key, status=HypothesisStatus.SUPPORTED, reason="matched")

    report = render_markdown(store, binary_id)

    assert report.count("### FUN_923A") == 1


# --- what must not regress ---


def test_evidence_references_are_still_rendered(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    store.save_evidence(
        binary_id,
        Evidence(
            key="E-001",
            kind=EvidenceKind.CROSS_REFERENCE,
            summary="called from a timer routine",
            source="ghidra",
            mechanically_observed=True,
        ),
    )
    believe(store, binary_id, supporting=("E-001",))

    report = render_markdown(store, binary_id)

    assert "- Evidence:" in report
    assert "E-001" in report
    assert "called from a timer routine" in report


def test_the_safety_notice_and_framing_are_preserved(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    believe(store, binary_id)

    report = render_markdown(store, binary_id)

    assert "Static investigation artifact" in report
    assert "Do not treat this report as authorization" in report
    assert "## Intake facts" in report
    assert "## Functions" in report


def test_a_report_with_no_hypotheses_still_says_so(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)

    report = render_markdown(store, binary_id)

    assert "No hypotheses recorded yet" in report
    assert "Belief history" not in report


def test_rendering_is_deterministic_for_identical_stored_input(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    key = believe(store, binary_id)
    store.revise_hypothesis(binary_id, key, status=HypothesisStatus.SUPPORTED, reason="matched")

    assert render_markdown(store, binary_id) == render_markdown(store, binary_id)


def test_the_report_carries_no_environment_noise(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    key = believe(store, binary_id)
    store.revise_hypothesis(binary_id, key, status=HypothesisStatus.SUPPORTED, reason="matched")

    report = render_markdown(store, binary_id)

    assert str(tmp_path) not in report
    assert "/Users/" not in report
    assert "sqlite3" not in report
