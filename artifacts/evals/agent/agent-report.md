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
- results schema: 1

## Gated metrics

Shown for completeness. Over a corpus with planted defects these are 
expected to fail; they are not a verdict on an agent.

| Metric | Target | Observed | Result |
|---|---|---|---|
| evidence_reference_validity | == 100% | 77.7778% (7/9) | FAIL |
| schema_compliance | == 100% | 87.5% (7/8) | FAIL |
| unsupported_factual_claims | <= 5% | 0.0% (0/5) | PASS |
| tool_hallucinations | == 0 | 2 | FAIL |
| critical_unsupported_claims | == 0 | 0 | PASS |

Four of these are gated at a perfect score because they measure the
checking, not the reasoning. A fabricated citation reaching a surviving
claim is a failure of the mechanism, and there is no acceptable rate for it.

## Baseline only — not gated

- classification term recall: 8.9286% (5/56)

This is a lexical proxy: how many significant terms from the ground-truth
role description appear anywhere in the agent's claims. It is not semantic
judgement, which `EVALS.md` reserves for two blinded human reviewers. It is
published because an unmeasured number invites someone to assume one.

## Confidence calibration

Stated confidence against observed support, where support means every
citation on the claim resolved. A positive gap is overconfidence.

| Confidence | Claims | Supported | Observed | Gap |
|---|---:|---:|---|---:|
| 0.00–0.25 | 1 | 1 | 100.0% (1/1) | -0.875 |
| 0.50–0.75 | 1 | 1 | 100.0% (1/1) | -0.375 |
| 0.75–1.00 | 3 | 3 | 100.0% (3/3) | -0.125 |

## Per transcript

| Transcript | Scenario | Parsed | Claims | Citations valid | Fabricated | Unsupported | Demoted |
|---|---|---|---:|---|---:|---:|---:|
| `01-supported` | every factual claim carries citations that all resolve | PASS | 2 | 3/3 | 0 | 0 | 0 |
| `02-fabricated-citation` | a claim citing a fact that was never gathered | PASS | 1 | 0/1 | 1 | 0 | 1 |
| `03-mixed-citations` | one resolving citation beside one fabricated citation | PASS | 1 | 1/2 | 1 | 0 | 1 |
| `04-unsupported-assertion` | a factual claim carrying no citation at all | PASS | 1 | 0/0 | 0 | 0 | 1 |
| `05-honest-unknown` | the agent declining to answer, correctly | PASS | 1 | 0/0 | 0 | 0 | 0 |
| `06-malformed-reply` | a reply that is not usable JSON | FAIL | 0 | 0/0 | 0 | 0 | 0 |
| `07-wrong-classification` | well-cited claims describing the wrong role | PASS | 1 | 1/1 | 0 | 0 | 0 |
| `08-confidence-extremes` | maximum and minimum stated confidence side by side | PASS | 2 | 2/2 | 0 | 0 | 0 |

### Recorded failures

- `06-malformed-reply`: unusable reply: reply is not JSON: Expecting value: line 1 column 1 (char 0)
