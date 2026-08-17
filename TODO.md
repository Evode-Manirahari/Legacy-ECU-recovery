# Work Plan

Work is tracked as nodes of the development graph in `docs/MASTER_SPEC.md`. A
node moves only when its verification conditions pass.

## Node status

`UNVERIFIED-UNDER-GRAPH` means code exists from the deprecated linear sequence
but was never evaluated against this node's contract. See `ADR-002`.

| Node | Status | Note |
|---|---|---|
| `SPEC-001` | PASSED | human-approved 2026-08-17 |
| `REPO-001` | VERIFYING | this change: CI added, rest audited |
| `GRAPH-001` | PENDING | depends on `REPO-001`; owns graph infrastructure |
| `DATA-001` | UNVERIFIED-UNDER-GRAPH | 6 of 8 fixture categories exist |
| `RESEARCH-001` | PENDING | no target matrix exists |
| `EVIDENCE-001` | UNVERIFIED-UNDER-GRAPH | no Relationship/Evidence entity, no history |
| `GHIDRA-001` | UNVERIFIED-UNDER-GRAPH | adapter exists; no analysis-warnings field |
| `EVAL-STATIC-001` | PENDING | no harness, no results artifacts |
| `TOOLS-001` | PENDING | no bounded tool layer |
| `INTEGRATION-STATIC-001` | PENDING | |
| `GATE-STATIC-MVP` | PENDING | blocks all agent work |

Pre-graph code is *candidate implementation to verify and complete*, never
already-completed graph work. See `ADR-002`.

## Graph

```text
SPEC-001 → REPO-001 → GRAPH-001 → { DATA-001, RESEARCH-001, EVIDENCE-001 }
                                          │
                                   DATA-001 → GHIDRA-001 → EVAL-STATIC-001
                                          → TOOLS-001 → INTEGRATION-STATIC-001
                                          → GATE-STATIC-MVP
```

`GRAPH-001` owns `ecu-project.graph.yaml`, `graph/**`, `prompts/**`, and
`artifacts/**`. Nothing else may create them.

## NOW

- **Open blocker: `docs/MASTER_SPEC.md` is still absent.** Every foundation
  document cites it as authoritative. It must be added by a human rather than
  reconstructed from a conversation, so that what nodes cite is what was
  actually written.

## NEXT

In dependency order:

- `GRAPH-001` — minimum infrastructure to represent, inspect, and later execute
  the development graph. Executable only after `REPO-001` passes.
- `DATA-001` — add the two missing fixture categories: integer/bit-mask
  manipulation and timer-like counter logic.
- `RESEARCH-001` — produce `docs/research/ecu-target-matrix.{md,csv}`. Recommend
  candidates only; final architecture selection is a human gate.
- `EVIDENCE-001` — add `Relationship` and `Evidence` entities, the hypothesis
  status enum (`UNTESTED`, `SUPPORTED`, `WEAKENED`, `REJECTED`, `CONFIRMED`),
  migrations, and preserved hypothesis history.
- `GHIDRA-001` — reconcile against its contract, including analysis warnings.
- `EVAL-STATIC-001` — build the deterministic harness and produce
  `artifacts/evals/static-results.json` and `static-report.md`.
- `TOOLS-001` — bounded, schema-validated agent-facing tools; no LLM, no MCP.
- `INTEGRATION-STATIC-001` — end-to-end controlled flow plus full regression.
- `GATE-STATIC-MVP` — verification node.

After `GRAPH-001`, the `DATA-001` / `RESEARCH-001` / `EVIDENCE-001` fan-out may
run in parallel worktrees because their file ownership is disjoint
(`samples/` + `scripts/`, `docs/research/`, `src/ecu_recovery/evidence/`).
Maximum three parallel workers. Do not parallelize work that shares a bottleneck.

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

## Carried technical gaps

Recorded so they are not lost between nodes. Each belongs to a node above.

- Ghidra parses untrusted input in our own process with no sandbox, memory limit,
  or timeout. A blocker for real firmware; see `THREAT_MODEL.md`.
- Intake rejects extension-free files, which raw ROM dumps commonly are.
- `--base-address` is exercised only against Mach-O fixtures that carry their own
  base; it needs a raw-binary fixture before it can be called verified.
- Four of six fixtures are unscored, and constant detection, table detection,
  evidence validity, and calibration are defined but unmeasured.
