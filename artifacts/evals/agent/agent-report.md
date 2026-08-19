# Agent evaluation — frozen transcripts against hidden ground truth

**Detector verification: PASS** — gate over this corpus: FAIL, expected to fail

> **This corpus contains deliberately planted defects.** Fabricated
> citations, an unusable reply, and uncited assertions are in it on
> purpose, so the gate failing over it is the intended outcome and says
> nothing about any agent.
>
> What is being checked here is the *scorer*: each fixture declares what
> it plants, and the run is only a success if every planted defect was
> found and none was invented. A detector shown nothing but clean input
> has not been tested.

> **These transcripts are authored, not model-generated.**
>
> Scripted replies stood in for a model over real tool output. That
> verifies the scoring machinery. It is **not** a baseline of any
> model's behaviour, and `GATE-AGENT-MVP` must not be passed on this
> evidence.
>
> One thing is missing: a transcript produced by a real provider. The
> evaluator does not need to change to consume one.

Scoring reads frozen JSON only — no Ghidra, no model, no network — so any
machine can recompute these numbers, and re-running the scorer measures the
scorer while re-running the agent measures the agent.

## Provenance

- kind: `authored`
- scripted replies over real tool output; no model was called
- transcripts scored: 8
- adversarial corpus: True
- detector verification: PASS
- adjudicators: authored
- results schema: 1

## Gated metrics

Shown for completeness. Over a corpus with planted defects these are 
expected to fail; they are not a verdict on an agent.

| Metric | Target | Observed | Result |
|---|---|---|---|
| evidence_reference_validity | == 100% | 77.7778% (7/9) | FAIL |
| schema_compliance | == 100% | 87.5% (7/8) | FAIL |
| unsupported_factual_claims | <= 5% | 37.5% (3/8) | FAIL |
| tool_hallucinations | == 0 | 2 | FAIL |
| critical_unsupported_claims | == 0% | UNMEASURED | FAIL |

Four of these are gated at a perfect score because they measure the
checking, not the reasoning. A fabricated citation reaching a surviving
claim is a failure of the mechanism, and there is no acceptable rate for it.

## Adjudicated metrics

These need semantic judgement. `EVALS.md` requires two blinded reviewers,
so only a reconciled two-human verdict is gate-eligible; authored labels
compute a number to verify the scorer and nothing more. A metric nobody
qualified has judged reports UNMEASURED rather than a flattering zero.

| Metric | Value | Adjudicated | Provenance | Note |
|---|---|---|---|---|
| classification_accuracy | 40.0% (2/5) | 62.5% (5/8) | authored | fewer than two distinct human reviewers; authored labels verify the scorer and never satisfy review quorum |
| confidence_calibration (ECE) | 0.2857 | 77.7778% (7/9) | authored | fewer than two distinct human reviewers; authored labels verify the scorer and never satisfy review quorum |
| critical_unsupported_claims | UNMEASURED | — | none | 2 claim(s) lack a reconciled verdict on support or criticality, 1 of them disputed between reviewers; a count over an incompletely judged corpus would read as 'there are none' when it means 'nobody looked' |

## Diagnostics — not the metrics above

- `classification_term_recall_diagnostic`: 8.9286% (5/56)

Term overlap between the agent's sentences and the ground-truth role. It
measures vocabulary, not whether the role was identified, and it is named
so it cannot be mistaken for classification accuracy.

## Citation-support calibration

Stated confidence against **citation resolution**, which is not semantic
correctness: `07-wrong-classification` resolves every citation and is wrong
on purpose. Real confidence calibration stays unmeasured above.

| Confidence | Claims | Citations held | Observed | Gap |
|---|---:|---:|---|---:|
| 0.00–0.25 | 1 | 1 | 100.0% (1/1) | -0.875 |
| 0.50–0.75 | 1 | 1 | 100.0% (1/1) | -0.375 |
| 0.75–1.00 | 3 | 3 | 100.0% (3/3) | -0.125 |

## Confidence calibration (ECE)

Expected calibration error: the size-weighted mean gap between stated
confidence and adjudicated correctness. Zero is perfect. This is not an
accuracy rate — two runs can be right equally often and differ entirely
here. Only claims whose correctness met the required review strength
enter the bands; the adjudicated count is in the table above.

| Confidence | Claims | Correct | Mean stated | Accuracy | Gap |
|---|---:|---:|---:|---:|---:|
| 0.00–0.25 | 3 | 1 | 0.017 | 0.333 | -0.317 |
| 0.50–0.75 | 1 | 1 | 0.700 | 1.000 | -0.300 |
| 0.75–1.00 | 3 | 2 | 0.917 | 0.667 | +0.250 |

## Reviewer disagreements — left unresolved on purpose

Where reviewers differ the label is not settled by picking one or by
averaging. The claim stays unjudged and the disagreement is recorded.

- 03-mixed-citations: reviewers disagree on classification
- 03-mixed-citations: reviewers disagree on claim 0 support

## Per transcript

| Transcript | Scenario | Parsed | Claims | Citations valid | Fabricated | Unsupported | Demoted |
|---|---|---|---:|---|---:|---:|---:|
| `01-supported` | every factual claim carries citations that all resolve | PASS | 2 | 3/3 | 0 | 0 | 0 |
| `02-fabricated-citation` | a claim citing a fact that was never gathered | PASS | 1 | 0/1 | 1 | 1 | 1 |
| `03-mixed-citations` | one resolving citation beside one fabricated citation | PASS | 1 | 1/2 | 1 | 1 | 1 |
| `04-unsupported-assertion` | a factual claim carrying no citation at all | PASS | 1 | 0/0 | 0 | 1 | 1 |
| `05-honest-unknown` | the agent declining to answer, correctly | PASS | 1 | 0/0 | 0 | 0 | 0 |
| `06-malformed-reply` | a reply that is not usable JSON | FAIL | 0 | 0/0 | 0 | 0 | 0 |
| `07-wrong-classification` | well-cited claims describing the wrong role | PASS | 1 | 1/1 | 0 | 0 | 0 |
| `08-confidence-extremes` | maximum and minimum stated confidence side by side | PASS | 2 | 2/2 | 0 | 0 | 0 |

### Recorded failures

- `06-malformed-reply`: unusable reply: reply is not JSON: Expecting value: line 1 column 1 (char 0)
