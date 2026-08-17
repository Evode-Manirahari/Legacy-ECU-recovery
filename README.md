# Legacy ECU Recovery

Legacy ECU Recovery is an evidence-first investigation system for undocumented
automotive firmware. The long-term loop is:

> binary → understanding → reconstruction → behavioral validation

The current scope is deliberately smaller: safely inventory a firmware image,
persist analysis facts and hypotheses, and produce an auditable engineering
report. Firmware is treated as data and is never executed by the intake path.

## Current vertical slice

- Raw binary intake with SHA-256/SHA-1/MD5 fingerprints, byte entropy, fill-byte
  statistics, and repeated-block detection.
- Explicit processor selection; architecture guessing is not presented as fact.
- SQLite investigation store for functions, evidence, and hypotheses.
- Markdown engineering report with clear `known`, `inferred`, and `unknown`
  distinctions.
- A narrow adapter boundary for importing future Ghidra analysis.
- Six reproducible synthetic firmware fixtures with isolated ground truth,
  symbols-on/stripped builds, behavior probes, and artifact hashes.

## Quick start

Python 3.11 or newer is required. The checked-in `.python-version` selects 3.11
for tools that support it.

```bash
uv sync --extra dev
uv run ecu-recovery doctor
uv run ecu-recovery analyze path/to/firmware.bin \
  --processor ST10F269 \
  --database artifacts/investigations.sqlite3 \
  --report artifacts/report.md
uv run pytest
```

`uv.lock` pins the complete development environment. Ruff provides linting and
formatting, while mypy runs strict static type checks:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

The doctor command reports missing Ghidra as a warning during initial
development. Ghidra is not required until the static-analysis integration
milestone.

Rebuild and verify the synthetic laboratory:

```bash
uv run python scripts/build_synthetic.py
uv run pytest tests/test_synthetic_lab.py
```

See [docs/synthetic-lab.md](docs/synthetic-lab.md) for the visibility boundary,
architecture rationale, metadata contract, and exact evaluation formulas.

Only analyze firmware you are authorized to possess and inspect. Do not use a
generated conclusion as a basis for flashing a vehicle or controlling hardware.

## Project map

```text
src/ecu_recovery/   core library and CLI
src/ecu_recovery/binary/  firmware intake public boundary
src/ecu_recovery/analysis/ deterministic analysis public boundary
src/ecu_recovery/agent/   reserved agent boundary; no AI integration yet
src/ecu_recovery/evidence/ evidence model public boundary
src/ecu_recovery/reports/ reporting public boundary
docs/               architecture, research decisions, experiments
samples/synthetic/  known-source firmware laboratory and generated artifacts
scripts/            reproducible dataset builder
tests/              automated tests
```

## Next milestone

Choose one processor family, compile a small known embedded program for it, and
export Ghidra's functions/call relationships/decompiler output into the adapter.
The milestone succeeds when the system explains five important functions and
each explanation cites inspectable evidence.

See [docs/architecture.md](docs/architecture.md) and
[docs/experiments.md](docs/experiments.md) for the execution plan.
