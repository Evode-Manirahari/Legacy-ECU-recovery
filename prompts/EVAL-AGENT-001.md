# NODE: EVAL-AGENT-001

**Title:** Deterministic agent evaluation
**Depends on:** `AGENT-001`
**Verification:** commands
**Retry budget:** 2

## Goal

Measure the investigator agent against hidden ground truth, deterministically.

`EVAL-STATIC-001` established the pattern and this node follows it: analyze,
freeze, reveal, score. What changes is the subject — the claims a model made,
rather than the facts a tool derived.

## Ownership

Allowed: `src/ecu_recovery/evaluation/agent/**`, `tests/evaluation/agent/**`,
`artifacts/evals/agent/**`.

Forbidden: `src/ecu_recovery/agent/**` — a node must not repair the thing it is
grading. Report failures; do not fix them here.

## Required metrics

From `EVALS.md`:

```text
evidence references valid
schema compliance
unsupported factual claims
tool hallucinations
critical unsupported claims
function classification accuracy
confidence calibration
```

**Evidence validity is the load-bearing one.** Every citation must resolve to
the tool result it claims. A citation that names a real address but does not
support the claim is still invalid.

**Tool hallucination is a distinct failure** from being wrong: it means the
agent reported a tool result that the tool never produced. Count it separately
and gate it at zero.

## Initial gate targets

From `EVALS.md`, agent phase:

| Metric | Target |
|---|---|
| Evidence references valid | 100% |
| Schema compliance | 100% |
| Unsupported factual claims | <= 5% |
| Tool hallucinations | 0 |
| Critical unsupported claims | 0 |

Classification accuracy is **baselined first and not gated**. `EVALS.md` is
explicit: do not invent a flattering threshold before seeing performance.

## Required properties

- numerator and denominator published with every rate;
- results reproducible for a fixed transcript, so a scoring change is
  distinguishable from a model change;
- no LLM judge for anything ground truth can decide;
- ground truth revealed only after the agent's output is frozen.

## Artifacts

```text
artifacts/evals/agent/agent-results.json
artifacts/evals/agent/agent-report.md
```

## Acceptance

```bash
uv run pytest
```

## Exclusions

Do not modify the agent. Do not use a model as the sole evaluator of any
property ground truth can decide.

## Stop

Return the structured handoff and stop.
