# NODE: EVAL-STATIC-001

**Title:** Hidden-ground-truth static evaluation
**Depends on:** `GHIDRA-001`, `DATA-001`
**Verification:** commands
**Retry budget:** 2

## Goal

Measure the static-analysis layer against hidden ground truth.

## Ownership

Allowed: `src/ecu_recovery/evaluation/**`, `artifacts/evals/**`,
`tests/evaluation/**`.

Forbidden: `src/ecu_recovery/analysis/**`, `samples/**`.

## Required metrics

```text
binary import success
function discovery precision
function discovery recall
function start-address accuracy
call-edge precision
call-edge recall
constant discovery
analysis crash rate
serialization success
```

## Initial gate targets

| Metric | Initial target |
|---|---:|
| Binary import success | 100% |
| Serialization success | 100% |
| Function discovery recall | >= 95% |
| Function discovery precision | >= 95% |
| Call-edge recall | >= 90% |
| Unexpected crashes | 0 |

These are starting thresholds. If a baseline shows a threshold is poorly
chosen, record the observed baseline, the reason, the proposed change, and the
human approval. Do not silently lower a gate.

## Protocol

Analyze `firmware.stripped` only. Freeze the results, and only then reveal
symbols-on addresses and JSON ground truth.

## Artifacts

```text
artifacts/evals/static-results.json
artifacts/evals/static-report.md
```

Report numerators, denominators, tool versions, and failures alongside every
percentage.

## Acceptance

```bash
uv run pytest
```

Plus regression tests over the recorded baseline.

## Exclusions

Do not use an LLM judge for any property available from ground truth.

## Stop

Return the structured handoff and stop.
