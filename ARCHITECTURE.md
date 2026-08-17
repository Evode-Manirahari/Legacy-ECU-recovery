# Current Architecture

This document describes only code that exists in the repository today. Planned
components belong in `TODO.md`, not here.

## Runtime

The project is a Python 3.11+ package using a `src/` layout. The core has no
mandatory runtime third-party dependencies; PyGhidra is an optional extra that
only the Ghidra engine imports. The `ecu-recovery` console entry point and
`python -m ecu_recovery` both route to the same `argparse` CLI.

The implemented commands are:

```text
ecu-recovery doctor
ecu-recovery analyze <firmware> [--ghidra] [--decompile]
                                [--language ID] [--compiler-spec ID]
                                [--base-address ADDR]
```

The development environment is resolved by uv and pinned in `uv.lock`. Pytest,
Ruff, and mypy are development-only dependencies. `uv sync --extra ghidra`
installs PyGhidra.

Synthetic fixture generation is a development workflow, not a CLI command. The
builder is invoked as `uv run python scripts/build_synthetic.py`.

## Current data flow

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
        │           (models.py)             │
        │                 │                 │
        │                 ├──► analysis.json (serialized export)
        │                 │                 │
        └────────┬────────┴─────────────────┘
                 ▼
      SQLite investigation store
                 │
                 ▼
          Markdown report
```

Ghidra runs in-process through PyGhidra's JVM. Only `analysis/ghidra.py` touches
Java objects; it converts everything to plain records before returning.

## Components that exist

- `ecu_recovery.intake` validates a bounded local firmware file and calculates
  hashes, Shannon entropy, fill-byte counts, and exact repeated 256-byte blocks.
  It treats input exclusively as bytes and never executes it.
- `ecu_recovery.models` defines binary, function, and hypothesis records plus
  the known/inferred/unknown certainty vocabulary.
- `ecu_recovery.store` persists profiles, function records, and hypotheses in
  SQLite.
- `ecu_recovery.ghidra.bridge` validates a small JSON function export produced
  out of process. It remains supported for importing an analysis someone else
  ran.
- `ecu_recovery.analysis.models` defines the engine-free analysis vocabulary:
  `ArchitectureConfig`, `MemoryRegion`, `FunctionRecord`, `Instruction`,
  `DisassemblyResult`, `DecompilerResult`, `StringRecord`, `CrossReference`,
  `ConstantMatch`, `ByteWindow`, `ProgramSummary`, and `AnalysisExport`. A
  function's identity is its entry address, the only property that survives
  stripping.
- `ecu_recovery.analysis.base` declares `StaticAnalysisEngine` and
  `StaticAnalysisSession`, the shared response bounds (`MAX_READ_BYTES`,
  `MAX_INSTRUCTIONS`, `MAX_RESULTS`), the typed error hierarchy, and the shared
  validators. `export()` is implemented once here so every engine serializes the
  same shape.
- `ecu_recovery.analysis.ghidra` implements that interface with PyGhidra and is
  the only module permitted to import Java. It discovers a Ghidra installation,
  starts the JVM lazily, opens each program in a throwaway project directory, and
  supports `analyze_binary`, `list_functions`, `function_count`, `get_function`,
  `get_disassembly`, `decompile_function`, `get_callers`, `get_callees`,
  `get_cross_references`, `list_strings`, `list_memory_regions`, `read_bytes`,
  and `search_constant`.
- `ecu_recovery.report` renders the stored investigation as Markdown.
- `ecu_recovery.cli` connects intake, optional Ghidra analysis, optional JSON
  import, storage, and report generation. `--ghidra` writes the full serialized
  export to `analysis.json` and persists each discovered function.
- `ecu_recovery.doctor` checks the active Python version, required repository
  directories, `pyproject.toml`, Java, Ghidra discovery, and PyGhidra. Missing
  Ghidra, PyGhidra, or Java is a warning; malformed project configuration or
  missing required directories is a failure. Ghidra discovery requires a real
  application root containing `Ghidra/application.properties`, because a launcher
  script alone is not something PyGhidra can start.
- `binary`, `analysis`, `agent`, `evidence`, and `reports` provide stable package
  boundaries for later prompts. The first four public boundaries re-export only
  implemented domain behavior. The agent package is intentionally empty.
- `scripts/build_synthetic.py` compiles six x86-64 Mach-O fixtures with pinned
  flags, executes their embedded self-tests, strips investigator-visible copies,
  checks expected symbols, and records hashes plus compiler provenance.
- `samples/synthetic` separates C source, JSON ground truth, and compiled
  artifacts. The only investigator-visible artifact in a blinded evaluation is
  each sample's `firmware.stripped` executable.

## Components that do not exist

There is currently no agent tool layer, MCP server, AI model integration,
autonomous loop, emulator, peripheral model, experiment engine, reconstruction
pipeline, real ECU fixture, or graphical interface.

## Measured behavior

Against the stripped synthetic fixtures, Ghidra 12.1.2 recovers every expected
function at its exact ground-truth entry address with no extras, and recovers the
`multi_function_pipeline_v1` call graph exactly. These are asserted in
`tests/test_analysis_ghidra.py` rather than claimed here. This is a laboratory
result on compiler-generated x86-64, not a prediction about real ECU firmware.

## Boundaries

Firmware remains local and is read as untrusted data. Intake accepts a small
extension allowlist up to 64 MiB; the extension is a usability guard, and the
real controls are the regular-file check, the size cap, and the rule that intake
only ever reads bytes.

Ghidra runs in the same process through PyGhidra's JVM, which means an untrusted
binary is parsed by Ghidra inside our process. Ghidra's loaders and analyzers are
the trust boundary here, and there is no sandbox around them yet; hardening that
is Prompt 16's job and is recorded in `THREAT_MODEL.md`.

Java objects must not escape `analysis/ghidra.py`. Model providers must remain
replaceable and must receive only bounded analysis data.
