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
| `EVAL-AGENT-001` | PENDING | **READY** — no agent measurement exists |
| `PROVIDER-001` | PENDING | **READY** — no OpenAI transport exists |
| `BASELINE-AGENT-001` | PENDING | no real-model transcripts exist |
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

`BASELINE-AGENT-001` is `READY`, and it is the first node in this project that
spends money and leaves the machine.

```text
PROVIDER-001  ->  BASELINE-AGENT-001  ->  REVIEW-AGENT-BASELINE-001  ->  GATE-AGENT-MVP
   PASSED             READY                   human gate                 verification
```

Three prerequisites belong to whoever starts the capture, not to the code:

1. `OPENAI_API_KEY` exported. The adapter reads it from nowhere else.
2. `OPENAI_MODEL` set to an identifier the API actually reports. Nothing is
   defaulted; a snapshot name is never invented. What answered is recorded from
   the response rather than from the request.
3. The output budget understood. `max_output_tokens` bounds reasoning as well
   as visible output, so a ceiling set for the size of a JSON reply can be
   spent entirely on thinking and return nothing.

`GATE-AGENT-MVP` waits on the review node, not merely on the baseline. That edge
is what makes the gate impossible to fire on authored fixtures: every model reply
in the scorer-verification corpus is scripted, and the evaluator already reports
`sufficient_for_GATE-AGENT-MVP=False`.

Semantic metrics stay UNMEASURED until two blinded reviewers reach field-level
quorum. A coding agent may prepare review material and may never file a review.

## NEXT

- `BASELINE-AGENT-001` — all eight fixtures, transcripts frozen at capture,
  poor answers committed alongside good ones. No hand-picked subset.
- `REVIEW-AGENT-BASELINE-001` — two blinded human reviewers, filing
  independently. Reaches `NEEDS_HUMAN` if they do not exist.
- `GATE-AGENT-MVP` — verification node, after a reviewed baseline exists.
- `uv.lock` — records the `ghidra` extra with a pinned `pyghidra`; the `openai`
  extra has no equivalent entry, so `uv sync --extra openai` refreshes the lock
  rather than installing from it. CI is unaffected. Needs one line of
  authorization to close.
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
