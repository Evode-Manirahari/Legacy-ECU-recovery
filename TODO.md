# Work Plan

Work is tracked as nodes of the development graph in `docs/MASTER_SPEC.md`. A
node moves only when its verification conditions pass.

## Node status

`UNVERIFIED-UNDER-GRAPH` means code exists from the deprecated linear sequence
but was never evaluated against this node's contract. See `ADR-002`.

The graph itself is now machine-readable in `ecu-project.graph.yaml`. This table
is the human-readable view of it; the file is authoritative.

```bash
uv run ecu-recovery graph status
uv run ecu-recovery graph ready
```

| Node | Status | Note |
|---|---|---|
| `SPEC-001` | PASSED | human-approved 2026-08-17 |
| `REPO-001` | PASSED | audited against contract; CI added |
| `GRAPH-001` | PASSED | amendment cleared GitHub CI and merged |
| `DATA-001` | PASSED | verified after PR #6; all eight fixture categories present |
| `RESEARCH-001` | PASSED | human gate cleared; ADR-004 selects MPC5xx PowerPC |
| `EVIDENCE-001` | PASSED | verified after PR #8 and #14; append-only belief history holds under audit |
| `GHIDRA-001` | PASSED | verified after PR #11; contract satisfied, eight fixtures structurally exact |
| `EVAL-STATIC-001` | PASSED | verified after PR #13 and #15; static gate passes on all six thresholds |
| `TOOLS-001` | PASSED | verified after PR #18; ten bounded, schema-checked tools |
| `INTEGRATION-STATIC-001` | PASSED | verified after PR #20; end-to-end flow proven, three findings reported |
| `REPORT-001` | PASSED | verified after PR #23; report distinguishes belief from testing |
| `GATE-STATIC-MVP` | PASSED | all twelve static MVP properties verified 2026-08-18 |
| `AGENT-001` | PASSED | verified after PR #29; claims are checked against gathered facts |
| `EVAL-AGENT-001` | PASSED | verified after PR #32; the evaluator is complete, a model baseline is not |
| `PROVIDER-001` | PASSED | verified after #35, #36, #39 and #40; transport only, one attempt, no key on disk |
| `PROVENANCE-001` | PASSED | verified after PR #42; a claim of model provenance is checked against a capture record |
| `DETECTION-SCOPE-001` | PASSED | verified after PR #45; detector verification has a scope and a third answer |
| `BASELINE-PREFLIGHT-001` | PASSED | verified after #51 and #52; an absent or broken transport refuses before iteration, with nothing called and nothing written |
| `BASELINE-AGENT-001` | PENDING | **READY** — all four prerequisites passed; no real-model transcripts exist yet |
| `REVIEW-AGENT-BASELINE-001` | PENDING | human gate; no blinded reviews exist |
| `GATE-AGENT-MVP` | PENDING | waits on `REVIEW-AGENT-BASELINE-001` |

Pre-graph code is *candidate implementation to verify and complete*, never
already-completed graph work. See `ADR-002`.

## Graph

```text
SPEC-001 → REPO-001 → GRAPH-001 ─┬─→ DATA-001 ─→ GHIDRA-001 ─→ EVAL-STATIC-001
                                 │                                    │
                                 ├─→ RESEARCH-001                     ▼
                                 │                                TOOLS-001
                                 └─→ EVIDENCE-001 ──┐                 │
                                                    ▼                 │
                                          INTEGRATION-STATIC-001 ◄────┘
                                                    ↓
                                            GATE-STATIC-MVP
```

`GRAPH-001` owns `ecu-project.graph.yaml`, `graph/**`, `prompts/**`, and
`artifacts/**`. Nothing else may create them. Each node's contract is in
`prompts/<NODE-ID>.md`.

## NOW — the transport exists, nothing has been captured through it

`PROVIDER-001` has passed. `ModelRequest -> OpenAI -> ModelResponse`, and
nothing else: no capture, no scoring, no tools, no streaming, no storage. The
suite still runs green with no key and no extra installed.

`PROVENANCE-001`, `DETECTION-SCOPE-001` and `BASELINE-PREFLIGHT-001` have
passed too, so `BASELINE-AGENT-001` is `READY` — the first node in this project
that spends money and leaves the machine.

`BASELINE-PREFLIGHT-001` passed 2026-08-28, before any real call. It came out of
the pre-spend checklist, which found a fourth case walking past all three
refusals `#50` had just installed.
Configuration being *present* is not the transport being *available*: with
`OPENAI_API_KEY` and `OPENAI_MODEL` both set and the `openai` extra absent, the
configuration guard passes, the SDK import fails inside the call, `investigate`
records an unreachable provider as an outcome, and the run completes — eight
transcripts labelled `provenance: model`, eight capture records the evaluator
verifies, `is_real_model=True`, and not one request off the machine.

Reproduced with no network reached, in the environment the run would have used;
the extra is not installed here, so the trap was armed rather than hypothetical.
A complete baseline of nothing, indistinguishable from a real one taken during
an outage — and a transcript is frozen at capture, so finding it afterwards
costs a second round of real calls.

The repair is local readiness only. No health check, no credential probe, no
connectivity test: once the eight calls begin, a provider or network failure is
an **outcome** of the frozen experiment, never a reason to retry or adapt. Both
halves of that boundary are asserted — the check runs with sockets disabled, and
a run with two provider refusals still freezes all sixteen artifacts and makes
exactly eight calls.

The import is attempted rather than resolved with `find_spec`. `find_spec`
answers "is it on the path"; the question worth asking is the one the adapter
asks a moment later, and a findable-but-broken install passes the first and
fails the second.

Its own regressions caught a flaw before merge: the refusal interpolated the
import error's message — arbitrary text from outside the module, landing in a
printed line. It names the exception type only now, with the detail kept on the
traceback.

```text
PROVIDER-001            PASSED   transport            ┐
PROVENANCE-001          PASSED   proof of capture     ├─>  BASELINE-AGENT-001 ─> REVIEW-AGENT-BASELINE-001 ─> GATE-AGENT-MVP
DETECTION-SCOPE-001     PASSED   scope of a status    │        READY                    human gate              verification
BASELINE-PREFLIGHT-001  PASSED   transport is present ┘      spend gate
```

`DETECTION-SCOPE-001` passed 2026-08-28, before the eight real calls rather than
after them. `verify_detection` reported a mismatch for any transcript with no
`expects` block, which is right for a fixture and wrong for a capture: nothing
is planted in a real call, so all eight baseline transcripts would have tripped
it and the artifact certifying the baseline would have read
`detector_verification=FAIL` over a list of genuine samples described as
defective fixtures.

It failed no gate invariant, which was the reason to fix it first. A false FAIL
beside real PASSes teaches whoever reads the baseline that the line means
nothing — and that line is how a real detector regression would announce itself.
`BASELINE-AGENT-001` freezes what it captures, so repairing it afterwards would
have meant re-scoring a frozen run to change what its report says.

Letting the line read `PASS` instead would have been worse: a corpus with
nothing planted has not been detector-verified at all, so `PASS` there is as
empty a claim as `FAIL`. Detector verification now has three answers, and scope
is derived from verified capture linkage rather than from a transcript's own
provenance string — an exemption a transcript could declare for itself would
hand back, in a new place, exactly what `PROVENANCE-001` closed.

Four prerequisites belong to whoever starts the capture, not to the code:

1. `OPENAI_API_KEY` exported. The adapter reads it from nowhere else.
2. `OPENAI_MODEL` set to an identifier the API actually reports. Nothing is
   defaulted; a snapshot name is never invented. What answered is recorded from
   the response rather than from the request.
3. The output budget understood. `max_output_tokens` bounds reasoning as well
   as visible output, so a ceiling set for the size of a JSON reply can be
   spent entirely on thinking and return nothing.
4. The frozen environment used, every time: `uv run --extra openai --frozen`,
   with `git diff --exit-code uv.lock` before committing. A bare `uv run`
   re-resolved and bumped `openai 3.3.1 -> 3.5.0` once already.

`PROVENANCE-001` passed 2026-08-28. It was added the day before, after
independent review of `PROVIDER-001` found two defects and before any real call
was made: the adapter returned the whole provider record and `investigate` kept
two strings of it, so a frozen transcript could not say what answered; and the
evaluator derived real-model provenance from a free-text field, so a
hand-written transcript saying `"provenance": "model"` was accepted as a
baseline. Both are closed. A transcript now carries the whole call record, and a
claim of model provenance is checked against a content-addressed capture record
that must exist, match its own contents, and belong to that transcript.

What that record proves is integrity and linkage, not that a provider made the
call — no artifact this repository can hold would prove the second. The
provider-issued response id is the field a human can check against the
provider's own account records, which is why `GATE-AGENT-MVP` must publish it.

It depended on `EVAL-AGENT-001` rather than on `PROVIDER-001`: it repaired the
agent and evaluator trees, which sit behind that edge, so the two were
independent siblings with disjoint ownership and ran in parallel.

They are separate because they fail differently. A transport fault is not a bad
answer; generating a transcript is not having it judged; and the thing being
measured must not grade itself.

`GATE-AGENT-MVP` waits on the review node, not merely on the baseline. That edge
is what makes the gate impossible to fire on authored fixtures: every model reply
in the scorer-verification corpus is scripted, and the evaluator already reports
`sufficient_for_GATE-AGENT-MVP=False`.

Semantic metrics stay UNMEASURED until two blinded reviewers reach field-level
quorum. A coding agent may prepare review material and may never file a review.

## NEXT

- `BASELINE-AGENT-001` — all eight fixtures, no hand-picked subset, each
  transcript frozen at capture and referencing the capture record written when
  the call was made. Poor answers committed alongside good ones.
- `REVIEW-AGENT-BASELINE-001` — two blinded human reviewers, filing
  independently. Reaches `NEEDS_HUMAN` if they do not exist.
- `GATE-AGENT-MVP` — verification node, after a reviewed baseline exists.
- MPC5xx dataset work — still a separate measurable step.

## LATER

Gated, in order. Do not begin a phase before its gate passes.

- **Agent phase** (after `GATE-STATIC-MVP`): `AGENT-001`, `HYPOTHESIS-001`,
  `EVAL-AGENT-001`, `REPORT-001`, `GATE-AGENT-MVP`.
- **Emulation** (after `GATE-AGENT-MVP`): `EMU-001`, `EMU-TRACE-001`,
  `PERIPHERAL-001`, `GATE-EMULATION`.
- **Experimentation**: proposal → deterministic validator → human approval →
  execution → evidence → hypothesis revision.
- **Reconstruction**: one function, compiled, behaviorally verified.
- **Real authorized ECU firmware**: only after every prior gate, a security
  review, documented authorization, and human approval.

## Candidate nodes (not in the graph)

Ideas under consideration. They are deliberately **absent from
`ecu-project.graph.yaml`**: the graph is the authority for what work may start,
and listing an unassigned idea there would imply it is scheduled. A candidate
becomes a node only when a human assigns it.

### `SYMBOLIC-001` — symbolic behavioral analysis

Derive behavioral evidence from a function mechanically, before any LLM
interpretation and without paying for full emulation. For a discovered
function, attempt to establish which inputs affect behavior, what paths exist,
which constraints select each path, what outputs and memory change, and which
inputs are observably equivalent.

Proposed position — an **optional branch**, never a mandatory dependency:

```text
GATE-STATIC-MVP
      │
      ├──────────────┐
      ▼              ▼
AGENT-001      SYMBOLIC-001
      │              │
      └──────┬───────┘
             ▼
       EVIDENCE-JOIN
             ↓
       GATE-ANALYSIS
```

Key constraints if it is ever assigned:

- Results are **evidence, not semantic truth**. A recovered partition is a
  deterministic fact; "this classifies an input into three operating ranges" is
  an inference, and the two must not be merged.
- Failure is a legitimate structured result. Peripherals, interrupts, global
  state, timing, unsupported instructions, path explosion, and environment
  dependencies all make functions unsuitable; return an
  unsupported/inconclusive result and let the investigation continue by other
  means. Do not force it to succeed.
- Engine behind an internal interface, as with Ghidra. `angr` is the first
  candidate; nothing outside the adapter may depend on it.
- Evaluated against synthetic fixtures with hidden ground truth before any real
  firmware, measuring completion rate, path coverage, condition accuracy,
  output-effect accuracy, equivalence-class precision and recall, timeout rate,
  solver-failure rate, and path-explosion rate.
- It does not replace emulation. Symbolic analysis suits behavior derivable
  from the function itself; emulation remains necessary where behavior depends
  on the runtime environment.

The underlying principle is the one already driving the graph: cheap
deterministic evidence first, AI to interpret it, experiments to challenge the
interpretation, verification to settle it. Do not ask a model to rediscover
what a solver can establish.

Nothing has been installed, implemented, or added to the architecture.

## Carried technical gaps

Recorded so they are not lost between nodes. Each belongs to a node above.

- Ghidra parses untrusted input in our own process with no sandbox, memory limit,
  or timeout. A blocker for real firmware; see `THREAT_MODEL.md`.
- Intake rejects extension-free files, which raw ROM dumps commonly are.
- `--base-address` is exercised only against Mach-O fixtures that carry their own
  base; it needs a raw-binary fixture before it can be called verified.
- Four of six fixtures are unscored, and constant detection, table detection,
  evidence validity, and calibration are defined but unmeasured.
