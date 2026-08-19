# NODE: REVIEW-AGENT-BASELINE-001

**Title:** Blinded human review of the baseline
**Depends on:** `BASELINE-AGENT-001`
**Worker:** human-reviewers
**Verification:** human
**Retry budget:** 2

## Type

A human gate. `EVALS.md` requires two blinded reviewers for semantic judgement,
and this is where they file.

`verification: human` already carries its meaning in `graph/models.py`: *an agent
must never self-approve one.* Nothing new is invented here to represent that.

## Goal

Supply the semantic labels the evaluator has been reporting as UNMEASURED:
claim-level correctness, claim-level criticality, and one classification verdict
per subject.

## Ownership

Allowed: `artifacts/agent-baseline/reviews/**`.

Nothing else. Not the transcripts, which are frozen; not the evaluator, which
scores them; not the agent, which produced them.

## Required properties

1. **Two distinct human reviewers.** Reviewer identity is recorded and must
   differ. One person filing twice is one opinion and is refused at load.

2. **Independent submission.** Each reviewer works without seeing the other's
   verdicts. Blinding is the point: two reviewers who conferred are one
   reviewer with extra steps.

3. **Field-level quorum, as already enforced.** A verdict counts only where two
   distinct humans adjudicated *that field on that claim* and agreed. An
   abstention is not agreement. Reviewer presence on a transcript is not
   quorum on a field.

4. **Authored labels never count.** The `authored` fixtures exist to verify the
   scorer and can never reach human quorum. Do not relabel them.

5. **Disagreement stays explicit.** Where reviewers differ the label is left
   unsettled and the disagreement is recorded. It is not resolved by picking
   one, by averaging, or by sending reviewers back to agree.

6. **A coding agent must never impersonate a reviewer.** It may prepare
   material, describe the format, and check that submitted files parse. It may
   not author a verdict, and it may not mark this node passed.

## Outcome

**If both independent reviews exist:** the node may pass, and the semantic
metrics become measurable at human-quorum provenance.

**If they do not:** the node reaches `NEEDS_HUMAN` — a real state in the graph's
status model — and stops. It does not pass on partial review, and it does not
pass on authored labels.

## Acceptance

Human. An agent must not self-approve this node.

## Exclusions

Do not modify the transcripts, the evaluator, the agent, or the provider. Do not
start `GATE-AGENT-MVP`. No emulation.

## Stop

Report the review state and stop.
