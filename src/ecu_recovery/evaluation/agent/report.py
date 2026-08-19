"""Render an agent evaluation run.

The first thing this report says is what the transcripts are. A page of green
percentages computed over scripted replies looks exactly like a page of green
percentages computed over a real model, and only one of them means the model
works. Putting the provenance above the numbers is the difference between a
measurement and a misleading artifact.
"""

from __future__ import annotations

from .models import SCHEMA_VERSION, AgentEvaluationRun


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def render_report(run: AgentEvaluationRun) -> str:
    metrics = run.metrics
    lines = [
        "# Agent evaluation — frozen transcripts against hidden ground truth",
        "",
    ]
    if run.adversarial:
        lines += [
            f"**Detector verification: {_status(run.detection_verified)}** — "
            f"gate over this corpus: {_status(run.gate_passed)}, expected to fail",
            "",
            "> **This corpus contains deliberately planted defects.** Fabricated",
            "> citations, an unusable reply, and uncited assertions are in it on",
            "> purpose, so the gate failing over it is the intended outcome and says",
            "> nothing about any agent.",
            ">",
            "> What is being checked here is the *scorer*: each fixture declares what",
            "> it plants, and the run is only a success if every planted defect was",
            "> found and none was invented. A detector shown nothing but clean input",
            "> has not been tested.",
            "",
        ]
    else:
        lines += [f"**Gate: {_status(run.gate_passed)}**", ""]
    if run.baseline_only:
        lines += [
            "> **These transcripts are authored, not model-generated.**",
            ">",
            "> Scripted replies stood in for a model over real tool output. That",
            "> verifies the scoring machinery. It is **not** a baseline of any",
            "> model's behaviour, and `GATE-AGENT-MVP` must not be passed on this",
            "> evidence.",
            ">",
            "> One thing is missing: a transcript produced by a real provider. The",
            "> evaluator does not need to change to consume one.",
            "",
        ]
    lines += [
        "Scoring reads frozen JSON only — no Ghidra, no model, no network — so any",
        "machine can recompute these numbers, and re-running the scorer measures the",
        "scorer while re-running the agent measures the agent.",
        "",
        "## Provenance",
        "",
        f"- kind: `{run.provenance.kind}`",
        f"- {run.provenance.detail}",
        f"- transcripts scored: {metrics.transcripts}",
        f"- adversarial corpus: {run.adversarial}",
        f"- detector verification: {_status(run.detection_verified)}",
        f"- adjudicators: {', '.join(run.adjudicators) or 'none'}",
        f"- results schema: {SCHEMA_VERSION}",
        "",
        "## Gated metrics",
        "",
    ]
    if not run.adversarial:
        lines += ["| Metric | Target | Observed | Result |", "|---|---|---|---|"]
    if run.adversarial:
        lines.append("Shown for completeness. Over a corpus with planted defects these are ")
        lines.append("expected to fail; they are not a verdict on an agent.")
        lines.append("")
        lines.append("| Metric | Target | Observed | Result |")
        lines.append("|---|---|---|---|")
    for check in run.gate:
        lines.append(
            f"| {check.metric} | {check.render_target()} | {check.render_observed()} | "
            f"{_status(check.passed)} |"
        )
    lines += [
        "",
        "Four of these are gated at a perfect score because they measure the",
        "checking, not the reasoning. A fabricated citation reaching a surviving",
        "claim is a failure of the mechanism, and there is no acceptable rate for it.",
        "",
        "## Not measured",
        "",
        "These need semantic adjudication. None is reported as a number until a",
        "reviewer supplies one, because a metric nobody computed must not read like",
        "a metric that came out well.",
        "",
        "| Metric | State | Why |",
        "|---|---|---|",
        f"| classification_accuracy | {metrics.classification_accuracy.render()} | "
        f"{metrics.classification_accuracy.reason} |",
        f"| confidence_calibration | {metrics.confidence_calibration.render()} | "
        f"{metrics.confidence_calibration.reason} |",
        f"| critical_unsupported_claims | {metrics.critical_unsupported_claims.render()} | "
        f"{metrics.critical_unsupported_claims.reason} |",
        "",
        "## Diagnostics — not the metrics above",
        "",
        f"- `classification_term_recall_diagnostic`: "
        f"{metrics.classification_term_recall_diagnostic.render()}",
        "",
        "Term overlap between the agent's sentences and the ground-truth role. It",
        "measures vocabulary, not whether the role was identified, and it is named",
        "so it cannot be mistaken for classification accuracy.",
        "",
        "## Citation-support calibration",
        "",
        "Stated confidence against **citation resolution**, which is not semantic",
        "correctness: `07-wrong-classification` resolves every citation and is wrong",
        "on purpose. Real confidence calibration stays unmeasured above.",
        "",
    ]
    if metrics.citation_support_calibration:
        lines += [
            "| Confidence | Claims | Citations held | Observed | Gap |",
            "|---|---:|---:|---|---:|",
        ]
        for bucket in metrics.citation_support_calibration:
            lines.append(
                f"| {bucket.lower:.2f}–{bucket.upper:.2f} | {bucket.claims} | "
                f"{bucket.supported} | {bucket.observed.render()} | {bucket.gap} |"
            )
    else:
        lines.append("No factual claims carried confidence, so this is undefined here.")

    lines += [
        "",
        "## Per transcript",
        "",
        "| Transcript | Scenario | Parsed | Claims | Citations valid "
        "| Fabricated | Unsupported | Demoted |",
        "|---|---|---|---:|---|---:|---:|---:|",
    ]
    for score in run.scores:
        valid = f"{score.valid_citations}/{score.citations}"
        lines.append(
            f"| `{score.transcript_id}` | {score.scenario} | {_status(score.parsed)} | "
            f"{score.claims} | {valid} | {score.fabricated_citations} | "
            f"{score.unsupported_factual_claims} | {score.demotions} |"
        )
    if run.detection_mismatches:
        lines += ["", "### Detector disagreed with what the fixtures planted", ""]
        lines += [f"- {item}" for item in run.detection_mismatches]
    notes = [(item.transcript_id, note) for item in run.scores for note in item.notes]
    if notes:
        lines += ["", "### Recorded failures", ""]
        lines += [f"- `{transcript_id}`: {note}" for transcript_id, note in notes]
    return "\n".join(lines).rstrip() + "\n"
