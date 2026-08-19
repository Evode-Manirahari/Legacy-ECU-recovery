# NODE: GATE-AGENT-MVP

**Title:** Agent MVP gate
**Depends on:** `EVAL-AGENT-001`, `REVIEW-AGENT-BASELINE-001`
**Worker:** verification
**Verification:** gate
**Retry budget:** 0

## Type

Verification node. No implementation work happens here, and it owns no paths.

## Required properties

Every line must pass:

```text
Agent operates only through the bounded tool layer   PASS
Evidence references valid                            PASS
Schema compliance                                    PASS
Tool hallucinations zero                             PASS
Critical unsupported claims zero                     PASS
Unsupported factual claims within target             PASS
Classification accuracy baselined and published      PASS
Agent evaluation reproducible                        PASS
Full regression suite                                PASS
```

Classification accuracy must be **baselined and published**, not thresholded.
Passing this gate does not require the model to be good; it requires the
measurement to be trustworthy and the agent to be honest about what it does not
know.

## Outcome

**If PASS:** the emulation phase may be authorized.

**If FAIL:** identify the failing upstream node, create a repair path, and stop.

## Why this gate exists

`GATE-STATIC-MVP` made retrieval measurable so model errors would be
attributable. This gate makes the model's *claims* measurable before anything
executes firmware. An agent that fabricates evidence is more dangerous with an
emulator attached, not less.

## Exclusions

No emulation before this gate passes. No real firmware before the real-firmware
gate and its authorization conditions. No flashing, no vehicle control.

## Stop

Report the gate result and stop.
