# NODE: GATE-STATIC-MVP

**Title:** Static MVP gate
**Depends on:** `INTEGRATION-STATIC-001`
**Worker:** verification
**Verification:** gate
**Retry budget:** 0

## Type

Verification node. No implementation work happens here.

## Required properties

Every line must pass:

```text
Synthetic fixtures reproducible          PASS
Stripped binaries available              PASS
Ghidra import                            PASS
Function extraction                      PASS
Call extraction                          PASS
Structured serialization                 PASS
Static evaluation executes               PASS
Function-quality thresholds              PASS
Call-graph threshold                     PASS
Agent-facing tool schemas                PASS
Evidence persistence                     PASS
Full regression suite                    PASS
```

## Outcome

**If PASS:** the investigator-agent phase unlocks — `AGENT-001`,
`HYPOTHESIS-001`, `EVAL-AGENT-001`, `REPORT-001`, `GATE-AGENT-MVP`.

**If FAIL:** identify the failing upstream node, create a repair path, and stop.
Do not continue into AI-agent work.

## Why this gate exists

Before deterministic retrieval is measurable, an LLM makes error attribution
ambiguous: a wrong answer could come from Ghidra, the parser, the tool layer,
the context, the prompt, or the model. Make the information pipeline measurable
first, then add reasoning.

## Exclusions

No AI agent work before this gate passes. No emulation before
`GATE-AGENT-MVP`. No real firmware before the real-firmware gate and its
authorization conditions.

## Stop

Report the gate result and stop.
