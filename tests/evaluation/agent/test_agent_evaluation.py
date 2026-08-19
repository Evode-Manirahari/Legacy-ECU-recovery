"""Scoring the agent, checked without an agent.

The evaluator reads frozen JSON, so every test here runs with no Ghidra, no
model, and no network. That is the property the transcript-first design was
chosen for.

The fixtures are adversarial on purpose. A detector only ever shown clean input
has not been tested, so each fixture declares the defect it plants and the
scorer is held to finding exactly that - no more, no less.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ecu_recovery.evaluation.agent import (
    GATE_TARGETS,
    AgentMetrics,
    Provenance,
    Transcript,
    TranscriptError,
    check_gate,
    evaluate,
    load_transcripts,
    parse_transcript,
    render_report,
    score_transcript,
)
from ecu_recovery.evaluation.models import Ratio

TRANSCRIPTS = Path(__file__).resolve().parent / "transcripts"
ARTIFACTS = Path(__file__).resolve().parents[3] / "artifacts" / "evals" / "agent"
RESULTS = ARTIFACTS / "agent-results.json"
REPORT = ARTIFACTS / "agent-report.md"


def by_id(transcript_id: str) -> Transcript:
    return next(item for item in load_transcripts(TRANSCRIPTS) if item.id == transcript_id)


# --- the fixture corpus covers what the contract asked for ---


def test_every_required_scenario_has_a_fixture() -> None:
    ids = {item.id for item in load_transcripts(TRANSCRIPTS)}

    for required in (
        "01-supported",
        "02-fabricated-citation",
        "03-mixed-citations",
        "04-unsupported-assertion",
        "05-honest-unknown",
        "06-malformed-reply",
        "07-wrong-classification",
        "08-confidence-extremes",
    ):
        assert required in ids


def test_the_fixtures_hold_real_tool_output() -> None:
    """Scripted replies over a real fact sheet, not a hand-written transcript."""
    transcript = by_id("01-supported")

    facts = transcript.investigation["fact_sheet"]["facts"]
    assert facts
    assert all(item["result_digest"] for item in facts)
    assert all(len(item["result_digest"]) == 64 for item in facts)
    assert all(item["tool"] for item in facts)


# --- each metric detects the defect it exists for ---


def test_a_clean_transcript_scores_clean() -> None:
    score = score_transcript(by_id("01-supported"))

    assert score.parsed is True
    assert score.fabricated_citations == 0
    assert score.unsupported_factual_claims == 0
    assert score.critical_unsupported_claims == 0
    assert score.valid_citations == score.citations


def test_a_fabricated_citation_is_counted_as_a_tool_hallucination() -> None:
    score = score_transcript(by_id("02-fabricated-citation"))

    assert score.fabricated_citations == 1
    assert score.demotions == 1


def test_one_valid_citation_does_not_excuse_a_fabricated_one() -> None:
    score = score_transcript(by_id("03-mixed-citations"))

    assert score.fabricated_citations == 1
    assert score.valid_citations == 1
    assert score.demotions == 1


def test_an_uncited_factual_claim_is_counted_as_unsupported() -> None:
    score = score_transcript(by_id("04-unsupported-assertion"))

    assert score.demotions == 1


def test_an_honest_unknown_carries_no_evidential_burden() -> None:
    score = score_transcript(by_id("05-honest-unknown"))

    assert score.claims == 1
    assert score.factual_claims == 0
    assert score.unsupported_factual_claims == 0
    assert score.demotions == 0


def test_a_malformed_reply_fails_schema_compliance() -> None:
    score = score_transcript(by_id("06-malformed-reply"))

    assert score.parsed is False
    assert score.claims == 0
    assert score.notes


def test_confidence_extremes_are_both_retained() -> None:
    transcript = by_id("08-confidence-extremes")

    confidences = sorted(float(item["confidence"]) for item in transcript.claims)

    assert confidences[0] <= 0.05
    assert confidences[-1] == 1.0


# --- the detector is held to what the fixtures planted ---


def test_the_scorer_finds_exactly_what_each_fixture_planted() -> None:
    """The check that makes an adversarial corpus worth having."""
    run = evaluate(TRANSCRIPTS)

    assert run.adversarial is True
    assert run.detection_mismatches == ()
    assert run.detection_verified is True


def test_a_fixture_claiming_a_defect_it_does_not_contain_is_caught() -> None:
    """Proves the previous test is not vacuous."""
    from ecu_recovery.evaluation.agent.scoring import verify_detection

    transcript = by_id("01-supported")
    lying = Transcript(
        id=transcript.id,
        sample_id=transcript.sample_id,
        subject=transcript.subject,
        scenario=transcript.scenario,
        investigation=transcript.investigation,
        expects={"fabricated_citations": 3},
    )

    mismatches = verify_detection(lying, score_transcript(lying))

    assert mismatches
    assert "fabricated_citations" in mismatches[0]


# --- the gate ---


def test_the_gate_targets_are_the_ones_the_contract_states() -> None:
    assert dict(
        (metric, (comparison, threshold)) for metric, comparison, threshold in GATE_TARGETS
    ) == {
        "evidence_reference_validity": ("==", 100.0),
        "schema_compliance": ("==", 100.0),
        "unsupported_factual_claims": ("<=", 5.0),
        "tool_hallucinations": ("==", 0.0),
        "critical_unsupported_claims": ("==", 0.0),
    }


def test_classification_accuracy_is_not_gated() -> None:
    """EVALS.md forbids inventing a threshold before seeing performance."""
    assert not [metric for metric, _, _ in GATE_TARGETS if "classification" in metric]


def test_the_gate_fails_over_the_adversarial_corpus_as_expected() -> None:
    run = evaluate(TRANSCRIPTS)

    assert run.gate_passed is False
    # ...and that failure is not evidence about an agent.
    assert run.adversarial is True


def test_a_clean_corpus_would_pass_the_gate() -> None:
    """Proves the gate is satisfiable, not merely strict."""
    metrics = AgentMetrics(
        evidence_reference_validity=Ratio(10, 10),
        schema_compliance=Ratio(4, 4),
        unsupported_factual_claims=Ratio(0, 8),
        tool_hallucinations=0,
        critical_unsupported_claims=0,
        classification_term_recall=Ratio(3, 9),
    )

    assert all(check.passed for check in check_gate(metrics))


def test_the_unsupported_threshold_is_a_ceiling_not_an_equality() -> None:
    under = AgentMetrics(
        evidence_reference_validity=Ratio(10, 10),
        schema_compliance=Ratio(4, 4),
        unsupported_factual_claims=Ratio(1, 100),
        tool_hallucinations=0,
        critical_unsupported_claims=0,
        classification_term_recall=Ratio(0, 0),
    )
    over = AgentMetrics(
        evidence_reference_validity=Ratio(10, 10),
        schema_compliance=Ratio(4, 4),
        unsupported_factual_claims=Ratio(10, 100),
        tool_hallucinations=0,
        critical_unsupported_claims=0,
        classification_term_recall=Ratio(0, 0),
    )

    assert all(check.passed for check in check_gate(under))
    assert not all(check.passed for check in check_gate(over))


# --- authored transcripts may never pass the agent gate ---


def test_authored_transcripts_are_never_sufficient_for_the_agent_gate() -> None:
    run = evaluate(TRANSCRIPTS)

    assert run.provenance.is_real_model is False
    assert run.baseline_only is True
    assert run.as_dict()["sufficient_for_gate_agent_mvp"] is False


def test_one_authored_transcript_makes_a_whole_run_authored() -> None:
    """A mixed set would let scripted replies inflate a number read as a model's."""
    assert Provenance(kind="authored").is_real_model is False
    assert Provenance(kind="model").is_real_model is True


# --- transcripts ---


def test_a_transcript_missing_required_fields_is_refused() -> None:
    with pytest.raises(TranscriptError, match="missing"):
        parse_transcript({"id": "x"})


def test_an_empty_transcript_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(TranscriptError, match="no transcripts"):
        load_transcripts(tmp_path)


# --- the recorded artifacts ---


def test_the_committed_results_match_a_fresh_scoring_run() -> None:
    assert RESULTS.is_file(), f"missing recorded results at {RESULTS}"

    fresh = json.loads(json.dumps(evaluate(TRANSCRIPTS).as_dict(), sort_keys=True))
    committed = json.loads(RESULTS.read_text(encoding="utf-8"))

    assert fresh == committed


def test_the_committed_report_matches_a_fresh_render() -> None:
    assert REPORT.is_file()

    assert render_report(evaluate(TRANSCRIPTS)) == REPORT.read_text(encoding="utf-8")


def test_scoring_is_deterministic() -> None:
    first = evaluate(TRANSCRIPTS).as_dict()
    second = evaluate(TRANSCRIPTS).as_dict()

    assert first == second


def test_the_report_says_the_transcripts_are_not_a_model_baseline() -> None:
    """The artifact must not be readable as model performance."""
    text = REPORT.read_text(encoding="utf-8")

    assert "not model-generated" in text
    assert "GATE-AGENT-MVP` must not be passed" in text
    assert "planted defects" in text


def test_the_artifacts_carry_no_environment_noise() -> None:
    text = RESULTS.read_text(encoding="utf-8") + REPORT.read_text(encoding="utf-8")

    assert "/Users/" not in text
    assert "/home/" not in text
