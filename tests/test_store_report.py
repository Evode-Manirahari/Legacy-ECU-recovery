from pathlib import Path

from ecu_recovery.intake import profile_binary
from ecu_recovery.models import (
    Certainty,
    Evidence,
    EvidenceKind,
    FunctionRecord,
    Hypothesis,
    HypothesisStatus,
)
from ecu_recovery.report import render_markdown
from ecu_recovery.store import InvestigationStore


def test_round_trip_investigation(tmp_path: Path) -> None:
    firmware = tmp_path / "fixture.rom"
    firmware.write_bytes(bytes(range(128)))
    store = InvestigationStore(tmp_path / "analysis.sqlite3")
    analysis_id = store.save_profile(profile_binary(firmware))
    store.save_function(analysis_id, FunctionRecord(0x8000, "FUN_8000", 24))
    store.save_hypothesis(
        analysis_id,
        Hypothesis(
            subject="FUN_8000",
            claim="possible initialization routine",
            certainty=Certainty.INFERRED,
            confidence=0.65,
            evidence=("first discovered function at ROM base",),
            uncertainty="reset vector has not been confirmed",
        ),
    )

    report = render_markdown(store, analysis_id)

    assert "Unknown (manual selection required)" in report
    assert "`0x8000` — FUN_8000 (24 bytes)" in report
    assert "possible initialization routine" in report
    assert "65%" in report


def test_report_shows_current_belief_not_superseded_ones(tmp_path: Path) -> None:
    """Before this node the report listed every revision as a live claim.

    Two saves of one claim produced two rows, and `report_data` ordered them by
    confidence, so a superseded belief could be rendered above the current one
    as though both were still held.
    """
    firmware = tmp_path / "fixture.rom"
    firmware.write_bytes(bytes(range(128)))
    store = InvestigationStore(tmp_path / "analysis.sqlite3")
    analysis_id = store.save_profile(profile_binary(firmware))
    revision = store.save_hypothesis(
        analysis_id,
        Hypothesis(
            subject="FUN_8000",
            claim="possible initialization routine",
            certainty=Certainty.INFERRED,
            confidence=0.90,
        ),
    )
    store.revise_hypothesis(
        analysis_id,
        revision.key,
        confidence=0.20,
        status=HypothesisStatus.WEAKENED,
        reason="reset vector points elsewhere",
    )

    report = render_markdown(store, analysis_id)

    assert report.count("possible initialization routine") == 1
    assert "- Confidence: 20%" in report
    # The superseded 90% is not gone - REPORT-001 renders it inside the belief
    # history, which is the point of keeping history. What must never happen is
    # it appearing as a headline belief, as though both were still held.
    assert "- Confidence: 90%" not in report
    assert "| 1 | inferred" not in report
    assert "| 1 | untested | 90% |" in report


def test_report_still_renders_a_single_hypothesis_unchanged(tmp_path: Path) -> None:
    """A caller that never revises sees exactly the pre-graph output."""
    firmware = tmp_path / "fixture.rom"
    firmware.write_bytes(bytes(range(128)))
    store = InvestigationStore(tmp_path / "analysis.sqlite3")
    analysis_id = store.save_profile(profile_binary(firmware))
    store.save_hypothesis(
        analysis_id,
        Hypothesis(
            subject="FUN_8000",
            claim="possible initialization routine",
            certainty=Certainty.INFERRED,
            confidence=0.65,
            evidence=("first discovered function at ROM base",),
            uncertainty="reset vector has not been confirmed",
        ),
    )

    report = render_markdown(store, analysis_id)

    assert "- Evidence:\n  - first discovered function at ROM base" in report
    assert "- Uncertainty: reset vector has not been confirmed" in report


def test_structured_evidence_reaches_the_report_with_its_stance(tmp_path: Path) -> None:
    """report.py is not owned by this node, so evidence has to arrive through
    the free-text list it already reads. Stance is rendered inline."""
    firmware = tmp_path / "fixture.rom"
    firmware.write_bytes(bytes(range(128)))
    store = InvestigationStore(tmp_path / "analysis.sqlite3")
    analysis_id = store.save_profile(profile_binary(firmware))
    store.save_evidence(
        analysis_id,
        Evidence("E-021", EvidenceKind.MEMORY_ACCESS, "reads timer capture", "ghidra", True),
    )
    store.save_evidence(
        analysis_id,
        Evidence("E-099", EvidenceKind.CALL_GRAPH, "also on the fuel-trim path", "ghidra", True),
    )
    store.save_hypothesis(
        analysis_id,
        Hypothesis("FUN_923A", "engine-speed calculation", Certainty.INFERRED, 0.7),
        supporting=("E-021",),
        contradicting=("E-099",),
    )

    report = render_markdown(store, analysis_id)

    assert "E-021 [supports] reads timer capture" in report
    assert "E-099 [contradicts] also on the fuel-trim path" in report


def test_report_renders_status_and_history(tmp_path: Path) -> None:
    """The gap this test used to pin, now closed.

    It previously asserted the opposite - that the report said
    `Status: **inferred**` and contained neither the status nor the change
    reason - because `report.py` belonged to no node and EVIDENCE-001 could not
    fix it. REPORT-001 was created to close exactly that, so the assertions are
    inverted rather than deleted: the record of what was wrong stays legible.
    """
    firmware = tmp_path / "fixture.rom"
    firmware.write_bytes(bytes(range(128)))
    store = InvestigationStore(tmp_path / "analysis.sqlite3")
    analysis_id = store.save_profile(profile_binary(firmware))
    revision = store.save_hypothesis(
        analysis_id,
        Hypothesis("FUN_923A", "engine-speed calculation", Certainty.INFERRED, 0.55),
    )
    store.revise_hypothesis(
        analysis_id,
        revision.key,
        status=HypothesisStatus.SUPPORTED,
        confidence=0.88,
        reason="frequency sweep matched",
    )

    report = render_markdown(store, analysis_id)

    assert "- Status: **inferred**" not in report  # the mislabelling is gone
    assert "- Certainty: **inferred**" in report
    assert "- Hypothesis status: **supported**" in report
    assert "frequency sweep matched" in report
