# Architecture

This document describes only what exists in the repository today, plus what is
explicitly planned by an assigned node. Speculative components do not belong
here.

## Status note (2026-08-17)

Much of this code was built under a **deprecated linear prompt sequence**,
before `docs/MASTER_SPEC.md` became the authoritative specification. It is
present and its own tests pass, but most of it has **not** been verified against
a node contract.

Under the graph rule — *an edge means the prerequisite has been verified* —
that work is recorded as `UNVERIFIED-UNDER-GRAPH`, not `PASSED`, and it must be
re-verified in its own node rather than grandfathered in. `SPEC-001` and
`REPO-001` have since been executed and passed against their contracts; the
authoritative per-node status is `ecu-project.graph.yaml`.

## Runtime that exists

A Python 3.11+ package in a `src/` layout. The core has no mandatory
third-party runtime dependency; PyGhidra is an optional extra that only the
Ghidra engine imports.

Implemented commands:

```text
ecu-recovery doctor
ecu-recovery analyze <firmware> [--ghidra] [--decompile]
                                [--language ID] [--compiler-spec ID]
                                [--base-address ADDR]
```

uv resolves the environment and pins it in `uv.lock`. Ruff lints and formats,
mypy runs strict, pytest runs the suite. `uv sync --extra ghidra` installs
PyGhidra.

`.github/workflows/ci.yml` runs tests, lint, format, and types on Linux against
the frozen lockfile. It deliberately does **not** install Ghidra, so CI is the
standing proof that a missing Ghidra never breaks the repository: the
Ghidra-marked tests skip with a stated reason, and the x86-64 Mach-O fixture
tests skip through their own platform guards.

## Data flow that exists

```text
              allow-listed firmware file
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
 byte-only intake   Ghidra engine    pre-made Ghidra
        │           (PyGhidra)       JSON export
        ▼                 │                 │
  BinaryProfile           ▼                 │
        │           plain analysis records  │
        │                 │                 │
        │                 ├──► analysis.json
        │                 │                 │
        └────────┬────────┴─────────────────┘
                 ▼
      SQLite investigation store
                 │
                 ▼
          Markdown report
```

## Development-graph infrastructure

`graph/` is engineering scaffolding for *building* the product, not part of the
product. It is Graph A from the specification — the development graph — and it
neither launches agents, creates worktrees, schedules work, nor runs anything in
the background.

- `ecu-project.graph.yaml` — the eleven-node DAG, its dependencies, ownership,
  verification, and retry budgets. Authoritative over the tables in `TODO.md`.
- `graph/models.py` — `NodeStatus`, `Verification`, `Node`, `Graph`. Shape only.
- `graph/state.py` — what each status *means*: only `PASSED` satisfies a
  dependency, `UNVERIFIED-UNDER-GRAPH` is still executable, and `FAILED`,
  `BLOCKED`, and `NEEDS_HUMAN` obstruct everything downstream.
- `graph/loader.py` — reads the graph file. Parses a strict YAML subset rather
  than adding a dependency, since the repository has no mandatory third-party
  runtime dependency and `pyproject.toml` belongs to another node. Unsupported
  syntax raises instead of being guessed at.
- `graph/validator.py` — rejects cycles, duplicate ids, unknown dependencies,
  invalid statuses, and self-dependencies, reporting every problem at once.
- `graph/status.py` — the READY frontier, obstruction analysis, and
  `newly_ready_if_passed`. All queries are pure.
- `prompts/*.md` — one contract per node.

There is no `ecu-recovery graph` CLI subcommand: `src/` is outside `GRAPH-001`'s
ownership. The package is used from Python:

```python
import graph

g = graph.load_graph()
print(graph.render_status_table(g))
print(graph.ready_nodes(g))
```

## Modules that exist

- `ecu_recovery.intake` — validates a bounded local firmware file and computes
  hashes, Shannon entropy, fill-byte counts, and repeated 256-byte blocks. Treats
  input strictly as bytes; never executes it.
- `ecu_recovery.models` — binary, function, and hypothesis records plus the
  known/inferred/unknown certainty vocabulary.
- `ecu_recovery.store` — SQLite persistence for analyses, functions, and
  hypotheses.
- `ecu_recovery.analysis.models` — engine-free analysis vocabulary:
  `ArchitectureConfig`, `MemoryRegion`, `FunctionRecord`, `Instruction`,
  `DisassemblyResult`, `DecompilerResult`, `StringRecord`, `CrossReference`,
  `ConstantMatch`, `ByteWindow`, `ProgramSummary`, `AnalysisExport`. A function's
  identity is its entry address, the only property that survives stripping.
- `ecu_recovery.analysis.base` — `StaticAnalysisEngine` and
  `StaticAnalysisSession`, shared response bounds (`MAX_READ_BYTES`,
  `MAX_INSTRUCTIONS`, `MAX_RESULTS`), typed errors, shared validators, and a
  single `export()` so every engine serializes the same shape.
- `ecu_recovery.analysis.ghidra` — the PyGhidra implementation and the only
  module permitted to import Java. Supports `analyze_binary`, `list_functions`,
  `function_count`, `get_function`, `get_disassembly`, `decompile_function`,
  `get_callers`, `get_callees`, `get_cross_references`, `list_strings`,
  `list_memory_regions`, `read_bytes`, `search_constant`.
- `ecu_recovery.ghidra.bridge` — validates a JSON function export produced out of
  process; retained for importing an analysis someone else ran.
- `ecu_recovery.report` — renders a stored investigation as Markdown.
- `ecu_recovery.cli` — connects intake, optional Ghidra analysis, optional JSON
  import, storage, and report generation.
- `ecu_recovery.doctor` — checks Python version, required directories,
  `pyproject.toml`, Java, Ghidra discovery, and PyGhidra. Missing Ghidra,
  PyGhidra, or Java is a warning; broken project configuration is a failure.
- `scripts/build_synthetic.py` — compiles six x86-64 Mach-O fixtures with pinned
  flags, runs their embedded self-tests, strips investigator-visible copies,
  checks expected symbols, and records hashes and compiler provenance.
- `samples/synthetic/` — separates C source, JSON ground truth, and compiled
  artifacts. The only investigator-visible artifact is each `firmware.stripped`.

## Measured behavior

Against two stripped fixtures, Ghidra 12.1.2 recovers every expected function at
its exact ground-truth entry address with no extras, and reproduces the
`multi_function_pipeline_v1` call graph exactly. Asserted in
`tests/test_analysis_ghidra.py`; counts recorded in `EVALS.md`.

This is a laboratory result on compiler-generated x86-64 with intact prologues.
It predicts nothing about real ECU firmware, and it is not `EVAL-STATIC-001` —
no evaluation harness, results artifact, or gate comparison exists yet.

## Known gaps against the master specification

These are stated here because this document must not overstate what exists.

| Node | Gap |
|---|---|
| `DATA-001` | Specification lists eight fixture categories; six exist. Integer/bit-mask manipulation and timer-like counter logic are missing. |
| `EVIDENCE-001` | No `Relationship` or `Evidence` entity, no hypothesis `status` enum, no hypothesis history. The store overwrites rather than revising. |
| `GHIDRA-001` | CLI output carries no `analysis warnings` field. |
| `EVAL-STATIC-001` | No harness, no `artifacts/evals/` outputs, no gate-target comparison. |
| `TOOLS-001` | No agent-facing tool layer with input/output schemas. |
| `RESEARCH-001` | No `docs/research/ecu-target-matrix.{md,csv}`. |
| `GRAPH-001` | Implemented. Remaining: no `ecu-recovery graph` CLI subcommand (`src/` is another node's ownership), `graph/` is outside mypy's configured `files`, and `artifacts/` is gitignored so generated baselines are not tracked. |
| CI coverage | CI runs on Linux only, so the x86-64 Mach-O fixture tests never execute there. Covering them needs an x86-64 macOS runner or a portable fixture target — a `DATA-001` decision. |

## Components that do not exist

No agent tool layer, MCP server, AI model integration, autonomous loop, emulator,
peripheral model, experiment engine, reconstruction pipeline, real ECU fixture,
or graphical interface.

## Boundaries

Firmware stays local and is read as untrusted data. Intake accepts a small
extension allowlist up to 64 MiB; the extension is a usability guard, and the
controls that carry weight are the regular-file check, the size cap, and the rule
that intake only ever reads bytes.

Ghidra currently runs **in the same process** through PyGhidra's JVM, so an
untrusted binary is parsed by Ghidra inside our process with no sandbox, memory
limit, or timeout. See `THREAT_MODEL.md`.

Java objects must not escape `ecu_recovery.analysis.ghidra`. Model providers must
remain replaceable and must receive only bounded analysis data.
