# Current Architecture

This document describes only code that exists in the repository today. Planned
components belong in `TODO.md`, not here.

## Runtime

The project is a Python 3.11+ package using a `src/` layout. It has no runtime
third-party dependencies. The `ecu-recovery` console entry point and
`python -m ecu_recovery` both route to the same `argparse` CLI.

The implemented commands are:

```text
ecu-recovery doctor
ecu-recovery analyze <firmware>
```

The development environment is resolved by uv and pinned in `uv.lock`. Pytest,
Ruff, and mypy are development-only dependencies.

Synthetic fixture generation is a development workflow, not a CLI command. The
builder is invoked as `uv run python scripts/build_synthetic.py`.

## Current data flow

```text
allow-listed firmware file
          │
          ▼
deterministic byte-only intake ──────┐
          │                          │
          ▼                          ▼
   BinaryProfile              optional Ghidra JSON export
          │                          │
          └────────────┬─────────────┘
                       ▼
               SQLite investigation store
                       │
                       ▼
                Markdown report
```

## Components that exist

- `ecu_recovery.intake` validates a bounded local firmware file and calculates
  hashes, Shannon entropy, fill-byte counts, and exact repeated 256-byte blocks.
  It treats input exclusively as bytes and never executes it.
- `ecu_recovery.models` defines binary, function, and hypothesis records plus
  the known/inferred/unknown certainty vocabulary.
- `ecu_recovery.store` persists profiles, function records, and hypotheses in
  SQLite.
- `ecu_recovery.ghidra.bridge` validates a small JSON function export. It is a
  data adapter only; the repository does not currently invoke Ghidra or
  PyGhidra.
- `ecu_recovery.report` renders the stored investigation as Markdown.
- `ecu_recovery.cli` connects intake, optional JSON import, storage, and report
  generation.
- `ecu_recovery.doctor` checks the active Python version, required repository
  directories, `pyproject.toml`, Java, and optional Ghidra discovery. Missing
  Ghidra or Java is a warning at this stage; malformed project configuration or
  missing required directories is a failure.
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

There is currently no PyGhidra integration, complete static-analysis interface,
agent tool layer, MCP server, AI model integration, autonomous loop, emulator,
peripheral model, experiment engine, reconstruction pipeline, real ECU fixture,
or graphical interface.

## Boundaries

Firmware remains local and is read as untrusted data. The current CLI accepts
only `.bin`, `.img`, and `.rom` files up to 64 MiB. Any future Ghidra process must
remain outside the core domain layer and return plain structured records. Model
providers must remain replaceable and must receive only bounded analysis data.
