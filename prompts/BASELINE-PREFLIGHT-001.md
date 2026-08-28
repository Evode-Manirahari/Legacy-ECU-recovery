# NODE: BASELINE-PREFLIGHT-001

**Title:** Local transport readiness before the baseline spends
**Depends on:** `PROVIDER-001`
**Verification:** commands
**Retry budget:** 2

## Why this node exists

`#50` moved three pre-spend checks in front of the first outbound call:
configuration, the frozen subjects, and an empty destination. The pre-spend
checklist written immediately afterwards found a fourth case that walks past all
three, and it is the same defect wearing a different coat.

Configuration being *present* is not the transport being *available*. With
`OPENAI_API_KEY` and `OPENAI_MODEL` both set and the `openai` extra absent, the
configuration guard passes — the configuration is genuinely there. The SDK
import then fails inside the call, `investigate` records an unreachable provider
as an **outcome** rather than an error, and the run completes.

Reproduced 2026-08-28, with no network reached, because the import fails before
any client or socket exists:

```text
run COMPLETED. transcripts=8 captures=8
  failure    = 'model unavailable: the openai extra is not installed; run `uv sync --extra openai`'
  provenance = 'model'
  evaluator  : kind='model' is_real_model=True baseline_only=False
```

Eight transcripts, eight capture records, every linkage the evaluator checks
intact, `is_real_model=True` — and not one request left the machine.

**This is a complete baseline of nothing, indistinguishable from a real one
taken during a provider outage.** It has to be closed before the capture rather
than after: a transcript is frozen at capture and never edited, so a defect
found afterwards costs a second round of real calls to repair.

The environment this was found in is the one the run would have used. The
`openai` extra is not installed here: `uv run --frozen python -c "import openai"`
raises `ModuleNotFoundError`. The trap was armed, not hypothetical.

## Goal

Prove the local OpenAI transport dependency is importable **before any fixture
is processed and before any baseline artifact is written**, and refuse the run
if it is not.

## Scope boundary — read before designing

**Do not add a network request to test credentials or connectivity.** Not a
health check, not a models list, not a one-token probe. The repair is about
*local transport readiness*, which is answerable without leaving the machine.

A probe would also be the wrong shape twice over: it spends before the
experiment starts, and it invites the idea that a provider failure is something
to detect and route around. It is not. Once the SDK is available and the eight
calls begin, **genuine provider and network failures are outcomes of the frozen
experiment** — captured, committed, and reported — never reasons to retry,
adapt, or re-run a fixture. That property is `BASELINE-AGENT-001`'s and this
node must not weaken it.

The distinction this node draws is exactly: *could a request have been made at
all* (checkable locally, and a precondition) versus *what happened when it was*
(the measurement).

## Ownership

Three files.

- `tests/agent_baseline/capture_harness.py` — the check belongs beside the
  other pre-spend guards, in the sequence that already refuses before the first
  call.
- `tests/agent_baseline/test_transport_preflight.py` — new, this node's
  regressions.
- `tests/agent_baseline/test_prespend_guards.py` — existing. Adding a refusal to
  the guard sequence changes which refusal a configured run meets first, and a
  node that cannot repair the tests it moves would have to leave them failing.

**Not authorized: `src/ecu_recovery/**`.** Inspection before this node was
opened found the defect entirely repairable in the harness — the SDK's
availability is answerable locally with the standard library, and the adapter's
own error is already correct and already redacted. It is raised too late to be
free, which is a caller's problem, not the adapter's.

If implementation shows a source change is genuinely required, **stop and open
an authorization amendment.** Do not widen this node's ownership. In particular,
evaluator and provenance semantics stay untouched, as they did through `#45` and
`#50`.

## Fixed decisions

1. **Local only.** Availability is determined without constructing a client,
   without reading a credential, and without any I/O beyond module resolution.
2. **Before iteration.** The check runs in the pre-call sequence, above the line
   that iterates fixtures — the same place the other four refusals live.
3. **The refusal is actionable.** It names the extra and the command that
   installs it. It never names, echoes, or logs a credential.
4. **Provider failures stay outcomes.** Nothing in this node may cause a fixture
   to be retried, skipped, re-attempted, or adapted once capture begins.

## Required properties

After this node passes, with `OPENAI_API_KEY` and `OPENAI_MODEL` set and the
SDK unimportable:

- the run fails **before fixture iteration**
- **0** provider calls
- **0** transcripts written
- **0** captures written
- **0** mutation of any existing baseline result
- the API key is never printed, logged, or serialized

And unchanged, asserted rather than assumed:

- the frozen subject manifest and its identity
  `M-dd677b4a5603966052d08feb7de8e7f01d98a6186044ed7cea4fd93ecacd0248`
- the exact eight-fixture protocol, with no subset and no reordering
- `max_output_tokens = 8192`
- exactly one attempt per fixture
- no retry and no adaptation anywhere

## The canonical live command

`BASELINE-AGENT-001` runs under the frozen environment **with the extra**:

```bash
uv run --extra openai --frozen ...
```

`--frozen` on every invocation. A bare `uv run` re-resolves and has already
bumped `openai 3.3.1 -> 3.5.0` once in this project; the run this protects is
the one whose entire purpose is a frozen artifact. Update the run instructions
in the harness docstring to match.

## Required regressions

Adversarial first, each asserting the same triple — refused, zero provider
calls, nothing written:

- configured environment, SDK unimportable → refused before iteration
- the same, asserting no transcript and no capture file exists afterwards
- the same, asserting an existing baseline elsewhere on disk is not mutated
- the refusal names the extra and the install command
- the refusal contains no credential, with a key-shaped value in the environment
- the check performs no network I/O and constructs no client

Positive controls, so the check cannot pass by refusing everything:

- SDK importable → the run proceeds and captures eight
- SDK importable but destination non-empty → the *destination* refusal is the
  one that arrives, proving the transport check let the run through

Unchanged-behaviour controls:

- the frozen manifest identity is still the recorded one
- eight fixtures, `8192`, one attempt each, no retry parameter
- a provider refusal during a capture is still frozen as an outcome, not retried

The suite must stay green on a host with **no extra installed**, which is the
condition the verification runs under.

## Acceptance

- `uv run --frozen pytest` green
- `git diff --exit-code uv.lock` clean — the lock does not move
- `uv run --frozen ruff check .`, `ruff format --check .`, `mypy` clean
- every changed file inside this node's allowed paths
- no `src/` file in the diff
- no OpenAI request made at any point

## Exclusions

- No API key set, no model chosen, no OpenAI request, no baseline capture.
- No network health check, credential probe, or connectivity test.
- No change to evaluator or provenance semantics.
- No change to gate thresholds.
- No change to the frozen manifest or its identity.
- No retry, backoff, or adaptive behaviour introduced anywhere.

## Stop

At the implementation PR's merge boundary. `BASELINE-AGENT-001` becomes the
ready frontier only when this node is `PASSED`, and the eight calls remain a
human spend gate after that.
