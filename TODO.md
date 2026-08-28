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
| `PROVIDER-001` | PENDING | **READY** — implementation merged (#35, #36, #37, #40); pass under review in #38 |
| `PROVENANCE-001` | PASSED | verified after PR #42; a claim of model provenance is checked against a capture record |
| `BASELINE-AGENT-001` | PENDING | waits on `PROVIDER-001` alone now; no real-model transcripts exist |
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

## NOW — the measurement exists, the measurement subject does not

`EVAL-AGENT-001` has passed: the deterministic evaluator is complete and its
scorer is verified against an adversarial corpus that plants each defect it
claims to detect.

`PROVIDER-001` is `READY`. Three nodes now stand between here and a gate that
means something:

```text
PROVENANCE-001 ┐  PASSED
  proof of capture
                ├─>  BASELINE-AGENT-001  ->  REVIEW-AGENT-BASELINE-001  ->  GATE-AGENT-MVP
PROVIDER-001   ┘      experiment               human gate                    verification
  transport
```

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

- `PROVIDER-001` — OpenAI transport behind the existing `ModelProvider`
  protocol. Key from `OPENAI_API_KEY` only, model name configurable,
  `store=False`, no tools, no streaming, optional `openai` extra. Suite stays
  green with nothing installed.
- `BASELINE-AGENT-001` — all eight fixtures, transcripts frozen at capture,
  each referencing the capture record written when the call was made, poor
  answers committed alongside good ones.
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
