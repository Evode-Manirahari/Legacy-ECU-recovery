# NODE: PROVENANCE-001

**Title:** Verifiable capture provenance
**Depends on:** `EVAL-AGENT-001`
**Verification:** commands
**Retry budget:** 2

## Why this node exists

Independent review of `PROVIDER-001` found two defects before any real call was
made. They are one cause seen twice: nothing between the transport and the gate
carries proof of what produced a reply.

**The provider record is discarded at the agent boundary.** The adapter returns
the returned model identifier, the response id, usage, status, and truncation
state. `investigate` copies two strings out of `ModelResponse` — `provider` and
`model` — into `Investigation`, and `Investigation.as_dict` emits them as
`{"model": {"provider": …, "name": …}}`. Everything else is gone before anything
is frozen. The requested identifier, the response id, the output ceiling, the
truncation state and the usage never reach a transcript, so a frozen transcript
cannot say what answered or under what bound.

**Provenance is self-asserted.** `evaluate` computes
`kinds == {"model"}` over `transcript.provenance`, a free-text field read by
`parse_transcript` with `payload.get("provenance", "authored")`. A transcript
file that says `"provenance": "model"` is reported as a real-model baseline —
`Provenance.kind == "model"`, `is_real_model` True, `baseline_only` False, and
the run's own detail line reads *every transcript came from a real provider*.
`GATE-AGENT-MVP` invariants 2 and 4 are satisfied by that string alone. This has
been demonstrated, not theorised: an authored fixture with one word changed
produces exactly that run record.

`BASELINE-AGENT-001` already carries the rule — *provenance is derived, not
asserted; do not write `model` by hand* — and nothing enforces it. A rule the
machinery does not check is a comment.

## Goal

```text
capture  ->  immutable capture record  ->  transcript references it  ->  evaluator verifies the linkage
```

The word `model` in a transcript becomes a claim to be checked against an
artifact, rather than a fact the evaluator adopts.

## Ownership

Allowed:

- `src/ecu_recovery/agent/models.py`
- `src/ecu_recovery/agent/investigator.py`
- `src/ecu_recovery/evaluation/agent/captures.py`
- `src/ecu_recovery/evaluation/agent/transcripts.py`
- `src/ecu_recovery/evaluation/agent/runner.py`
- `tests/agent/**`
- `tests/evaluation/agent/**`

Files, not trees. `AGENT-001` and `EVAL-AGENT-001` are both `PASSED`, and this
node exists to repair two specific things inside them. Owning
`src/ecu_recovery/agent/**` would let a repair rewrite the verified agent;
owning `models.py` and `investigator.py` can only change what a finished
investigation records about the call behind it.

Both test trees overlap their originating nodes exactly. That is safe for the
reason `REPORT-001`'s overlaps were safe: this node is directly downstream of
`EVAL-AGENT-001` and transitively downstream of `AGENT-001`, so it can never run
beside either.

`src/ecu_recovery/evaluation/agent/captures.py` is new. The capture record is
defined once, in the tree that verifies it, so the harness that writes records
and the evaluator that checks them cannot drift into two formats.

Forbidden, and load-bearing:

- `artifacts/evals/agent/**`. The recorded score of the authored corpus is the
  control for this repair. A node that could rewrite it could hide a change in
  what the evaluator reports.
- `src/ecu_recovery/providers/**`. `PROVIDER-001` already returns everything
  needed; the loss is downstream of it, and that node is under review.
- `src/ecu_recovery/evaluation/agent/gate.py`, `models.py`, `scoring.py`,
  `report.py`, `adjudication.py`. Thresholds, metrics, and adjudication are not
  in scope.
- `artifacts/agent-baseline/**`. This node builds the machinery; capture belongs
  to `BASELINE-AGENT-001`.

## Fixed decisions

- **No API call.** Every test uses a double. This node writes the machinery for
  a real capture and performs none.
- **The record is content-addressed.** A capture id is derived from the record's
  own body, so an edited record no longer matches its id.
- **The agent-side record stays deterministic.** No wall-clock, no run counter,
  no environment inside `Investigation.as_dict`; two identical investigations
  serialize identically. Time and run identity belong to the capture record,
  which is a separate artifact.
- **Allowlist, do not redact.** The frozen record is built from a named set of
  fields. Provider metadata is not copied wholesale, so a provider that returns
  a header, a key, or an account identifier cannot put it into a committed
  artifact by accident.
- **Verification can only downgrade.** An unverifiable claim of `model` becomes
  `authored` with a stated reason. Nothing in this node can promote a transcript
  the other way.

## Required properties

1. **The frozen record names what produced the reply**, per real call: provider,
   requested model identifier, exact returned model identifier and whether the
   API confirmed it, response id where available, status and incomplete reason,
   truncation state, `max_output_tokens` actually in force, usage including
   reasoning tokens where reported, and digests of the request and of the reply.
2. **A failed call is still recorded.** Provider, requested model and output
   ceiling survive on the failure paths, so a lost sample is auditable rather
   than blank.
3. **No credential, header, or account identifier reaches a committed
   artifact.** Enforced by the allowlist, proved by a test that puts a
   key-shaped value into provider metadata and asserts it appears nowhere in the
   serialized output.
4. **A transcript references its capture record**, and the evaluator verifies
   the linkage: the record exists, its id recomputes from its own body, it names
   this transcript, and its call record matches the transcript's field for
   field.
5. **A hand-edited transcript is not gate-eligible.** `"provenance": "model"`
   with no verifiable capture record yields `provenance.kind == "authored"`,
   `is_real_model` False, `baseline_only` True, and a stated reason naming the
   transcript.
6. **All or nothing is preserved.** One unverifiable transcript makes the whole
   run authored, exactly as one authored transcript does today.
7. **The evaluator is not weakened and no threshold moves.** `GATE_TARGETS` is
   untouched. The only change to `runner` is that a claim of model provenance
   must now be earned.
8. **The authored corpus scores exactly as before, byte for byte.** Re-running
   the evaluator over `tests/evaluation/agent/transcripts/**` reproduces the
   committed `artifacts/evals/agent/agent-results.json` unchanged — including
   the provenance detail line, which is the string that must not quietly change
   meaning.

## Required regressions

Adversarial first, because the finding was adversarial:

- a transcript identical to an authored fixture except `"provenance": "model"`,
  with no capture record, is not a model run;
- a transcript naming a capture record that does not exist is not a model run;
- a capture record edited after the fact — one field changed, id left alone —
  fails verification;
- two transcripts with each other's capture ids both fail on digest mismatch;
- a mixed corpus, one verified and one not, is authored;
- a positive control: a consistent capture record built from a double does
  verify, so the check cannot pass by refusing everything;
- the provider record survives serialization complete, on both the success and
  the failure path;
- a key-shaped value in provider metadata never reaches the frozen output;
- the same investigation serializes identically twice.

## Acceptance

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Plus: re-scoring the authored corpus reproduces the committed results artifact
with no diff.

## Exclusions

Do not make an OpenAI API call. Do not capture, write, or commit a baseline
transcript. Do not start `BASELINE-AGENT-001`, `REVIEW-AGENT-BASELINE-001`, or
`GATE-AGENT-MVP`. Do not change thresholds, metrics, scoring, or adjudication.
Do not touch `PROVIDER-001`'s tree. Do not widen this node's ownership: if the
repair genuinely cannot be done inside these files, stop and report it as an
authorization finding.

## Stop

Return the structured handoff and stop.
