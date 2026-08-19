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
from ecu_recovery.evaluation.agent.models import Measurement
from ecu_recovery.evaluation.models import Ratio

TRANSCRIPTS = Path(__file__).resolve().parent / "transcripts"
ARTIFACTS = Path(__file__).resolve().parents[3] / "artifacts" / "evals" / "agent"
RESULTS = ARTIFACTS / "agent-results.json"
REPORT = ARTIFACTS / "agent-report.md"


def clean_metrics(
    unsupported: Ratio | None = None, critical: Measurement | None = None
) -> AgentMetrics:
    """A metrics object that passes everything, for testing one knob at a time."""
    return AgentMetrics(
        evidence_reference_validity=Ratio(10, 10),
        schema_compliance=Ratio(4, 4),
        unsupported_factual_claims=unsupported or Ratio(0, 8),
        tool_hallucinations=0,
        critical_unsupported_claims=critical or Measurement("c", count=0),
        classification_accuracy=Measurement.unmeasured("classification_accuracy", "no reviewer"),
        confidence_calibration=Measurement.unmeasured("confidence_calibration", "no reviewer"),
        classification_term_recall_diagnostic=Ratio(3, 9),
    )


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
    """Counted before demotion. The agent catching it is not the model not doing it.

    Scoring survivors alone reported zero here, which read as "the model made no
    unsupported claims" when it had made one and been caught.
    """
    score = score_transcript(by_id("04-unsupported-assertion"))

    assert score.demotions == 1
    assert score.unsupported_factual_claims == 1
    assert score.raw_factual_claims == 1
    assert score.factual_claims == 0


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
    # A complete vector with exactly one field wrong, so the mismatch reported
    # is the disagreement itself rather than the incompleteness.
    lying = Transcript(
        id=transcript.id,
        sample_id=transcript.sample_id,
        subject=transcript.subject,
        scenario=transcript.scenario,
        investigation=transcript.investigation,
        expects={**transcript.expects, "fabricated_citations": 3},
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
    metrics = clean_metrics(unsupported=Ratio(0, 8), critical=Measurement("c", count=0))

    assert all(check.passed for check in check_gate(metrics))


def test_the_unsupported_threshold_is_a_ceiling_not_an_equality() -> None:
    under = clean_metrics(unsupported=Ratio(1, 100), critical=Measurement("c", count=0))
    over = clean_metrics(unsupported=Ratio(10, 100), critical=Measurement("c", count=0))

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


# --- review findings ---


def test_unsupported_claims_are_counted_before_demotion() -> None:
    """The whole corpus, end to end: overreach must not vanish into a demotion."""
    run = evaluate(TRANSCRIPTS)

    unsupported = run.metrics.unsupported_factual_claims

    assert unsupported.numerator == 3, "02, 03 and 04 each plant one unsupported claim"
    assert unsupported.denominator == 8
    assert unsupported.rate is not None and unsupported.rate > 0.0


def test_a_corpus_of_uncited_assertions_does_not_report_zero_unsupported(
    tmp_path: Path,
) -> None:
    """The regression the review asked for, stated as a corpus rather than a case.

    Every transcript here is a factual claim with no citation. AGENT-001 demotes
    all of them, so a scorer looking only at survivors would report 0% - a
    perfect score for a model that asserted things it could not support.
    """
    directory = tmp_path / "transcripts"
    directory.mkdir()
    source = by_id("04-unsupported-assertion")
    for index in range(4):
        payload = source.as_dict()
        payload["id"] = f"gen-{index:02d}"
        directory.joinpath(f"gen-{index:02d}.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    run = evaluate(directory, adjudications_dir=tmp_path / "none")

    assert run.metrics.unsupported_factual_claims == Ratio(4, 4)
    assert run.metrics.unsupported_factual_claims.percent == 100.0
    assert not any(
        check.passed for check in run.gate if check.metric == "unsupported_factual_claims"
    )


def test_detector_verification_catches_a_defect_nobody_planted() -> None:
    """False positives, not just false negatives.

    The fixture declares a clean vector; the scorer is handed a transcript that
    is not clean. Comparing only declared fields would have agreed with it.
    """
    from ecu_recovery.evaluation.agent.scoring import verify_detection

    dirty = by_id("02-fabricated-citation")
    clean_expectation = dict(by_id("01-supported").expects)
    mislabelled = Transcript(
        id=dirty.id,
        sample_id=dirty.sample_id,
        subject=dirty.subject,
        scenario=dirty.scenario,
        investigation=dirty.investigation,
        expects=clean_expectation,
    )

    mismatches = verify_detection(mislabelled, score_transcript(mislabelled))

    assert mismatches
    assert any("fabricated_citations" in item for item in mismatches)


def test_an_incomplete_fixture_expectation_is_itself_a_failure() -> None:
    """A partial vector hides false positives in the fields it omits."""
    from ecu_recovery.evaluation.agent.scoring import verify_detection

    source = by_id("01-supported")
    partial = Transcript(
        id=source.id,
        sample_id=source.sample_id,
        subject=source.subject,
        scenario=source.scenario,
        investigation=source.investigation,
        expects={"parsed": True},
    )

    mismatches = verify_detection(partial, score_transcript(partial))

    assert mismatches
    assert any("declares no expectation" in item for item in mismatches)


def test_classification_accuracy_is_unmeasured_without_a_reviewer(tmp_path: Path) -> None:
    run = evaluate(TRANSCRIPTS, adjudications_dir=tmp_path / "absent")

    accuracy = run.metrics.classification_accuracy

    assert accuracy.measured is False
    assert accuracy.render() == "UNMEASURED"
    assert "blinded" in accuracy.reason


def test_confidence_calibration_is_unmeasured_without_semantic_labels(
    tmp_path: Path,
) -> None:
    """Citations resolving is not correctness; 07 is the proof."""
    run = evaluate(TRANSCRIPTS, adjudications_dir=tmp_path / "absent")

    assert run.metrics.confidence_calibration.measured is False
    # The citation-based buckets remain, under a name that says what they are.
    assert run.metrics.citation_support_calibration


def test_a_well_cited_wrong_claim_is_not_counted_as_supported() -> None:
    """07 resolves every citation and is wrong. Only adjudication can say so."""
    score = score_transcript(by_id("07-wrong-classification"))

    assert score.valid_citations == score.citations == 1
    assert score.unsupported_factual_claims == 0

    run = evaluate(TRANSCRIPTS)

    assert run.metrics.confidence_calibration.measured is True
    assert run.metrics.classification_accuracy.ratio is not None
    assert run.metrics.classification_accuracy.ratio.numerator < (
        run.metrics.classification_accuracy.ratio.denominator
    )


def test_critical_unsupported_claims_is_unmeasured_without_adjudication(
    tmp_path: Path,
) -> None:
    """A zero nobody assessed would be the most dangerous line in the file."""
    run = evaluate(TRANSCRIPTS, adjudications_dir=tmp_path / "absent")

    assert run.metrics.critical_unsupported_claims.measured is False


def test_an_unmeasured_metric_can_never_satisfy_the_gate() -> None:
    metrics = clean_metrics(
        critical=Measurement.unmeasured("critical_unsupported_claims", "no reviewer")
    )

    checks = {check.metric: check for check in check_gate(metrics)}

    assert checks["critical_unsupported_claims"].passed is False
    assert checks["critical_unsupported_claims"].render_observed() == "UNMEASURED"


def test_adjudication_never_modifies_the_frozen_transcript() -> None:
    """Judgement arrives beside the transcript, never inside it."""
    transcript = by_id("07-wrong-classification")

    assert "adjudication" not in transcript.investigation
    assert "semantically_supported" not in json.dumps(transcript.investigation)
    assert (TRANSCRIPTS.parent / "adjudications" / "07-wrong-classification.json").is_file()


def test_authored_adjudication_keeps_the_run_baseline_only() -> None:
    """A label written to test the scorer is not a reviewer's verdict."""
    run = evaluate(TRANSCRIPTS)

    assert run.adjudicators == ("authored",)
    assert run.baseline_only is True
    assert run.as_dict()["sufficient_for_gate_agent_mvp"] is False
