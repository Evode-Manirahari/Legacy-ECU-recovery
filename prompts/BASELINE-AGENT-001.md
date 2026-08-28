# NODE: BASELINE-AGENT-001

**Title:** First real-model baseline transcripts
**Depends on:** `PROVIDER-001`, `PROVENANCE-001`, `DETECTION-SCOPE-001`
**Verification:** commands
**Retry budget:** 2

## Goal

```text
existing agent + OpenAI provider + all 8 synthetic fixtures -> frozen transcripts
```

Experiment execution. The machinery to score these already exists and is
verified; this node supplies the subject.

## Ownership

Allowed: `artifacts/agent-baseline/transcripts/**`,
`artifacts/agent-baseline/captures/**`,
`artifacts/agent-baseline/results/**`, `tests/agent_baseline/**`.

Deliberately outside `EVAL-AGENT-001`'s artifacts and tests, so a real baseline
can never be confused with the authored fixtures that verify the scorer.

`artifacts/agent-baseline/captures/**` holds one immutable record per real call,
written at capture time by the machinery `PROVENANCE-001` supplies. It is a
separate tree from the transcripts because it answers a different question: a
transcript is what the model said, a capture record is what the provider did.
Records are written once and never edited, exactly like the transcripts that
reference them.

`tests/agent_baseline/**` is also where the capture harness lives. This node
owns no source tree by design — it runs the system rather than changing it — and
a driver that makes eight real calls needs a named home rather than one
improvised on the day.

Forbidden: `src/ecu_recovery/**` entirely, and the authored fixtures under
`tests/evaluation/agent/**`. This node runs the system; it does not change it.

## Required ordering

```text
model executes -> transcript freezes
```

Only after a transcript is frozen may ground truth or reviewer material become
available for it. A transcript is never edited after capture.

## Required properties

1. **All eight fixtures.** No hand-picked subset for the first baseline.
2. **Commit the poor answers too.** A baseline curated for flattering examples
   is not a baseline, and the failures are the most useful part of the first
   one.
3. **The exact model identifier is recorded in every transcript**, as
   `PROVIDER-001` supplies it, together with the rest of the call record
   `PROVENANCE-001` defines: requested identifier, response id, output ceiling,
   truncation state and usage.
4. **Provenance is derived, not asserted.** Each transcript references the
   capture record written when the call was made, and the evaluator verifies
   that linkage. Do not write `model` by hand — since `PROVENANCE-001` it no
   longer works, and that is the point: the rule is now checked rather than
   trusted.
5. **No retrying into a better answer.** A refusal, a timeout, or an unusable
   reply is frozen as what happened. If a run must be repeated for a transport
   fault, say so in the results.
6. **This node does not adjudicate its own output.** Semantic labels come from
   `REVIEW-AGENT-BASELINE-001`, filed by humans. A coding agent must not write
   a review, here or anywhere.

## Deliverables

```text
artifacts/agent-baseline/captures/**         one immutable record per real call
artifacts/agent-baseline/transcripts/**      frozen, one per fixture
artifacts/agent-baseline/results/**          scored by the existing evaluator
```

The semantic metrics will read UNMEASURED until review lands. That is correct
and should not be worked around.

Detector verification will read as out of scope rather than as a failure, which
is `DETECTION-SCOPE-001`'s doing: nothing is planted in a real call, so there is
nothing for the detector to have found or missed. That is also correct and
should not be worked around.

## Acceptance

```bash
uv run pytest
```

Plus a regression that re-scores the committed transcripts and reproduces the
recorded numbers.

## Exclusions

Do not modify the agent, the provider, or the evaluator. Do not write reviews.
Do not tune prompts to improve the numbers — if the agent scores badly, that is
the finding, and a bounded follow-up is the answer. Do not start
`GATE-AGENT-MVP`. No emulation.

## Stop

Return the structured handoff and stop.
