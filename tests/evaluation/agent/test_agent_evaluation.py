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
    REQUIRED_HUMAN_REVIEWERS,
    AdjudicationError,
    AgentMetrics,
    ClaimJudgement,
    Provenance,
    Review,
    ReviewPanel,
    Transcript,
    TranscriptError,
    check_gate,
    classification_accuracy,
    confidence_calibration,
    critical_unsupported_claims,
    evaluate,
    load_panel,
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


def test_an_unmeasured_metric_can_never_satisfy_the_gate() -> None:
    metrics = clean_metrics(
        critical=Measurement.unmeasured("critical_unsupported_claims", "no reviewer")
    )

    checks = {check.metric: check for check in check_gate(metrics)}

    assert checks["critical_unsupported_claims"].passed is False
    assert checks["critical_unsupported_claims"].render_observed() == "UNMEASURED"


# --- adjudication: reviewers, quorum, and reconciliation ---


def panel_of(*reviews: Review) -> ReviewPanel:
    return ReviewPanel(reviews=tuple(reviews))


def human(
    transcript_id: str,
    reviewer: str,
    *,
    classification: bool | None = None,
    supported: bool | None = None,
    critical: bool | None = None,
) -> Review:
    return Review(
        transcript_id=transcript_id,
        reviewer=reviewer,
        kind="human",
        classification_correct=classification,
        judgements=(
            ClaimJudgement(claim_index=0, semantically_supported=supported, critical=critical),
        ),
    )


def one_claim(transcript_id: str = "t", confidence: float = 0.5) -> Transcript:
    return Transcript(
        id=transcript_id,
        sample_id="multi_function_pipeline_v1",
        subject="0x00001000",
        scenario="synthetic",
        investigation={
            "claims": [
                {"statement": "s", "support": "observed", "confidence": confidence, "citations": []}
            ],
            "citation_checks": [],
            "demotions": [],
            "failure": None,
        },
    )


# --- 1. critical AND unsupported ---


@pytest.mark.parametrize(
    "supported,critical,expected",
    [
        (True, True, 0),  # critical but true: not a failure
        (False, False, 0),  # unsupported but nobody would act on it
        (False, True, 1),  # the case the metric names
        (True, False, 0),
    ],
)
def test_critical_unsupported_truth_table(supported: bool, critical: bool, expected: int) -> None:
    """The metric is the conjunction. Either half alone is a different number."""
    transcripts = (one_claim(),)
    panel = panel_of(
        human("t", "reviewer-a", supported=supported, critical=critical),
        human("t", "reviewer-b", supported=supported, critical=critical),
    )

    measurement = critical_unsupported_claims(transcripts, panel)

    assert measurement.measured is True
    assert measurement.count == expected


def test_no_adjudication_at_all_is_unmeasured_not_zero() -> None:
    """An empty panel is the extreme case of incomplete coverage, not a clean run."""
    measurement = critical_unsupported_claims((one_claim(),), ReviewPanel())

    assert measurement.measured is False
    assert measurement.count is None
    assert "nobody looked" in measurement.reason


# --- 2. calibration is not accuracy ---


def _corpus(pairs: list[tuple[float, bool]]) -> tuple[tuple[Transcript, ...], ReviewPanel]:
    transcripts = tuple(one_claim(f"t{i}", confidence) for i, (confidence, _) in enumerate(pairs))
    reviews = []
    for index, (_, correct) in enumerate(pairs):
        for reviewer in ("reviewer-a", "reviewer-b"):
            reviews.append(human(f"t{index}", reviewer, supported=correct, critical=False))
    return transcripts, panel_of(*reviews)


def test_calibration_distinguishes_corpora_with_identical_accuracy() -> None:
    """The adversarial case: same accuracy, opposite calibration.

    Confident-when-right is well calibrated. Confident-when-wrong is not. Both
    are right half the time, so an accuracy rate cannot tell them apart — which
    is exactly why publishing one under the name calibration hid the difference.
    """
    calibrated, calibrated_panel = _corpus([(0.9, True), (0.1, False)])
    miscalibrated, miscalibrated_panel = _corpus([(0.1, True), (0.9, False)])

    good = confidence_calibration(calibrated, calibrated_panel)
    bad = confidence_calibration(miscalibrated, miscalibrated_panel)

    # Identical semantic accuracy.
    assert sum(1 for _, correct in [(0.9, True), (0.1, False)] if correct) == 1
    assert sum(1 for _, correct in [(0.1, True), (0.9, False)] if correct) == 1

    assert good.value is not None and bad.value is not None
    assert good.value < bad.value
    assert good.value == pytest.approx(0.1, abs=1e-6)
    assert bad.value == pytest.approx(0.9, abs=1e-6)


def test_perfect_calibration_scores_zero() -> None:
    perfect, panel = _corpus([(1.0, True), (0.0, False)])

    assert confidence_calibration(perfect, panel).value == pytest.approx(0.0, abs=1e-6)


def test_calibration_is_unmeasured_without_semantic_labels() -> None:
    assert confidence_calibration((one_claim(),), ReviewPanel()).measured is False


def test_citation_support_calibration_is_kept_but_separate() -> None:
    """Citations resolving is a diagnostic, not correctness. 07 is the proof."""
    run = evaluate(TRANSCRIPTS)

    assert run.metrics.citation_support_calibration
    assert run.metrics.confidence_calibration.name == "confidence_calibration"


# --- 3. two blinded reviewers ---


def test_two_distinct_human_reviewers_are_required_for_quorum() -> None:
    single = panel_of(human("t", "reviewer-a", supported=True, critical=False))
    pair = panel_of(
        human("t", "reviewer-a", supported=True, critical=False),
        human("t", "reviewer-b", supported=True, critical=False),
    )

    assert single.has_quorum("t") is False
    assert pair.has_quorum("t") is True
    assert REQUIRED_HUMAN_REVIEWERS == 2


def test_one_reviewer_filing_twice_does_not_make_a_quorum(tmp_path: Path) -> None:
    for name in ("a", "b"):
        (tmp_path / f"t.{name}.json").write_text(
            json.dumps(
                {
                    "transcript_id": "t",
                    "reviewer": "reviewer-a",
                    "kind": "human",
                    "classification_correct": True,
                    "judgements": [],
                }
            ),
            encoding="utf-8",
        )

    with pytest.raises(AdjudicationError, match="twice"):
        load_panel(tmp_path)


def test_authored_labels_never_satisfy_quorum() -> None:
    authored = panel_of(
        Review("t", "authored-a", kind="authored", classification_correct=True),
        Review("t", "authored-b", kind="authored", classification_correct=True),
    )

    assert authored.has_quorum("t") is False
    assert authored.fully_human is False


def test_a_single_human_reviewer_is_not_enough_for_a_gate_eligible_metric() -> None:
    transcripts = (one_claim(),)
    panel = panel_of(human("t", "reviewer-a", classification=True, supported=True, critical=False))

    measurement = classification_accuracy(transcripts, panel)

    assert measurement.measured is True  # a number exists
    assert measurement.gate_eligible is False  # but it cannot pass a gate
    assert "two distinct human reviewers" in measurement.reason


def test_two_human_reviewers_in_agreement_are_gate_eligible() -> None:
    transcripts = (one_claim(),)
    panel = panel_of(
        human("t", "reviewer-a", classification=True, supported=True, critical=False),
        human("t", "reviewer-b", classification=True, supported=True, critical=False),
    )

    measurement = classification_accuracy(transcripts, panel)

    assert measurement.gate_eligible is True
    assert measurement.ratio == Ratio(1, 1)


def test_reviewer_disagreement_is_recorded_and_left_unresolved() -> None:
    """Never silently pick a side; a contested judgement is not a measurement."""
    transcripts = (one_claim(),)
    panel = panel_of(
        human("t", "reviewer-a", classification=True, supported=True, critical=False),
        human("t", "reviewer-b", classification=False, supported=False, critical=False),
    )

    assert panel.classification("t").disagreed is True
    assert panel.classification("t").value is None
    assert panel.claim_support("t", 0).disagreed is True
    assert panel.disagreements("t", 1)

    # ...and a disagreed subject is not counted as either right or wrong.
    assert classification_accuracy(transcripts, panel).measured is False


def test_the_committed_corpus_records_its_disagreement() -> None:
    run = evaluate(TRANSCRIPTS)

    assert any("03-mixed-citations" in item for item in run.metrics.review_disagreements)


def test_authored_reviews_keep_the_run_baseline_only() -> None:
    run = evaluate(TRANSCRIPTS)

    assert run.adjudicators == ("authored",)
    assert run.baseline_only is True
    assert run.as_dict()["sufficient_for_gate_agent_mvp"] is False


def test_reviews_live_beside_the_transcript_never_inside_it() -> None:
    transcript = by_id("07-wrong-classification")

    assert "semantically_supported" not in json.dumps(transcript.investigation)
    assert (
        TRANSCRIPTS.parent / "adjudications" / "07-wrong-classification.authored-a.json"
    ).is_file()
    assert (
        TRANSCRIPTS.parent / "adjudications" / "07-wrong-classification.authored-b.json"
    ).is_file()


# --- 4. classification is per subject, not per claim ---


def test_classification_is_one_verdict_per_subject_however_many_claims() -> None:
    """A five-claim function must not outvote a one-claim function."""
    chatty = Transcript(
        id="chatty",
        sample_id="multi_function_pipeline_v1",
        subject="0x00001000",
        scenario="five claims about one function",
        investigation={
            "claims": [
                {"statement": f"s{i}", "support": "observed", "confidence": 0.5, "citations": []}
                for i in range(5)
            ],
            "citation_checks": [],
            "demotions": [],
            "failure": None,
        },
    )
    terse = one_claim("terse")
    panel = panel_of(
        human("chatty", "reviewer-a", classification=False),
        human("chatty", "reviewer-b", classification=False),
        human("terse", "reviewer-a", classification=True),
        human("terse", "reviewer-b", classification=True),
    )

    measurement = classification_accuracy((chatty, terse), panel)

    # Two subjects, two votes — not six.
    assert measurement.ratio == Ratio(1, 2)


def test_an_unknown_claim_does_not_become_a_classification_failure() -> None:
    """Only an explicit reviewer verdict counts; silence is not a wrong answer."""
    unknown_only = Transcript(
        id="u",
        sample_id="multi_function_pipeline_v1",
        subject="0x00001000",
        scenario="agent declined",
        investigation={
            "claims": [
                {
                    "statement": "cannot tell",
                    "support": "unknown",
                    "confidence": 0.0,
                    "citations": [],
                }
            ],
            "citation_checks": [],
            "demotions": [],
            "failure": None,
        },
    )
    panel = panel_of(
        human("u", "reviewer-a", supported=True, critical=False),
        human("u", "reviewer-b", supported=True, critical=False),
    )

    measurement = classification_accuracy((unknown_only,), panel)

    assert measurement.measured is False
    assert measurement.ratio is None


def test_the_lexical_diagnostic_stays_separate_and_ungated() -> None:
    run = evaluate(TRANSCRIPTS)

    assert run.metrics.classification_term_recall_diagnostic.denominator > 0
    assert not [metric for metric, _, _ in GATE_TARGETS if "term_recall" in metric]


# --- reviewer quorum is not adjudication coverage ---


def claims_transcript(transcript_id: str, count: int = 1) -> Transcript:
    return Transcript(
        id=transcript_id,
        sample_id="multi_function_pipeline_v1",
        subject="0x00001000",
        scenario="synthetic",
        investigation={
            "claims": [
                {"statement": f"s{i}", "support": "observed", "confidence": 0.5, "citations": []}
                for i in range(count)
            ],
            "citation_checks": [],
            "demotions": [],
            "failure": None,
        },
    )


def review_of(
    transcript_id: str,
    reviewer: str,
    index: int,
    supported: bool | None,
    critical: bool | None,
) -> Review:
    return Review(
        transcript_id=transcript_id,
        reviewer=reviewer,
        kind="human",
        judgements=(
            ClaimJudgement(claim_index=index, semantically_supported=supported, critical=critical),
        ),
    )


def reconciled(transcript_id: str, index: int, supported: bool, critical: bool) -> list[Review]:
    return [
        review_of(transcript_id, "reviewer-a", index, supported, critical),
        review_of(transcript_id, "reviewer-b", index, supported, critical),
    ]


def test_an_entirely_unjudged_claim_beside_a_judged_one_is_unmeasured() -> None:
    """The gate-integrity hole, stated exactly.

    One benign claim fully reviewed by two humans, one claim nobody judged at
    all. The earlier implementation only noticed a claim with *one* verdict
    missing, so a claim missing *both* fell through and the corpus reported zero
    with human-quorum provenance — gate-eligible, on a corpus half of which
    nobody had read.
    """
    transcripts = (claims_transcript("judged"), claims_transcript("unjudged"))
    panel = panel_of(*reconciled("judged", 0, supported=True, critical=False))

    measurement = critical_unsupported_claims(transcripts, panel)

    assert measurement.measured is False
    assert measurement.count is None
    assert measurement.gate_eligible is False
    assert "nobody looked" in measurement.reason


def test_a_claim_disputed_on_both_axes_is_unmeasured() -> None:
    transcripts = (claims_transcript("judged"), claims_transcript("disputed"))
    panel = panel_of(
        *reconciled("judged", 0, supported=True, critical=False),
        review_of("disputed", "reviewer-a", 0, True, True),
        review_of("disputed", "reviewer-b", 0, False, False),
    )

    measurement = critical_unsupported_claims(transcripts, panel)

    assert measurement.measured is False
    assert "disputed between reviewers" in measurement.reason


@pytest.mark.parametrize(
    "supported,critical,missing",
    [(None, False, "support"), (False, None, "criticality")],
)
def test_a_claim_missing_either_verdict_is_unmeasured(
    supported: bool | None, critical: bool | None, missing: str
) -> None:
    transcripts = (claims_transcript("judged"), claims_transcript("partial"))
    panel = panel_of(
        *reconciled("judged", 0, supported=True, critical=False),
        *[
            review_of("partial", reviewer, 0, supported, critical)
            for reviewer in ("reviewer-a", "reviewer-b")
        ],
    )

    measurement = critical_unsupported_claims(transcripts, panel)

    assert measurement.measured is False, missing


def test_a_second_claim_in_one_transcript_must_also_be_judged() -> None:
    """Coverage is per claim, not per transcript."""
    transcripts = (claims_transcript("two", count=2),)
    panel = panel_of(*reconciled("two", 0, supported=False, critical=True))

    measurement = critical_unsupported_claims(transcripts, panel)

    assert measurement.measured is False


def test_a_fully_reconciled_corpus_is_measured() -> None:
    transcripts = (claims_transcript("a"), claims_transcript("b"))
    panel = panel_of(
        *reconciled("a", 0, supported=False, critical=True),
        *reconciled("b", 0, supported=True, critical=False),
    )

    measurement = critical_unsupported_claims(transcripts, panel)

    assert measurement.measured is True
    assert measurement.count == 1
    assert measurement.gate_eligible is True


def test_quorum_alone_never_makes_an_incompletely_judged_count_gate_eligible() -> None:
    """Two reviewer identities prove two people looked at *something*.

    They say nothing about whether every claim was covered, and this metric is a
    count, which is read as completeness.
    """
    transcripts = (claims_transcript("judged"), claims_transcript("unjudged"))
    panel = panel_of(*reconciled("judged", 0, supported=True, critical=False))

    assert panel.has_quorum("judged") is True
    assert panel.has_quorum("unjudged") is False
    assert panel.fully_human is True

    measurement = critical_unsupported_claims(transcripts, panel)

    assert measurement.gate_eligible is False
    checks = {check.metric: check for check in check_gate(clean_metrics(critical=measurement))}
    assert checks["critical_unsupported_claims"].passed is False


def test_the_committed_corpus_reports_incomplete_coverage() -> None:
    """Its planted disagreement leaves a claim unreconciled, so the count refuses."""
    run = evaluate(TRANSCRIPTS)

    assert run.metrics.critical_unsupported_claims.measured is False
    assert run.metrics.review_disagreements
