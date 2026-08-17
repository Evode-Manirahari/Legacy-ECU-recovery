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
- Ghidra static analysis through PyGhidra behind an engine-independent interface:
  functions, call graph, disassembly, decompilation, cross-references, strings,
  memory regions, bounded byte reads, and constant search.
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

### Static analysis with Ghidra

```bash
brew install ghidra            # or set GHIDRA_INSTALL_DIR
uv sync --extra ghidra
uv run ecu-recovery analyze \
  samples/synthetic/binaries/multi_function_pipeline_v1/firmware.stripped \
  --ghidra --decompile \
  --analysis-json artifacts/analysis.json
```

That discovers functions, the call graph, strings, and memory regions, and writes
the full serialized result to `artifacts/analysis.json`. For a raw dump with no
load address, add `--language` and `--base-address`.

Ghidra tests run by default and skip with a stated reason when it is missing.
Skip the slow JVM path with `uv run pytest -m "not ghidra"`.

See [docs/ghidra-integration.md](docs/ghidra-integration.md) for the layering,
discovery order, response bounds, and what has actually been measured.

`uv.lock` pins the complete development environment. Ruff provides linting and
formatting, while mypy runs strict static type checks:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

The doctor command reports missing Ghidra or PyGhidra as warnings, so the rest of
the toolchain stays usable without them.

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
src/ecu_recovery/analysis/models.py  engine-free analysis vocabulary
src/ecu_recovery/analysis/base.py    engine interface, bounds, typed errors
src/ecu_recovery/analysis/ghidra.py  the only module that touches Java
docs/               architecture, research decisions, experiments
samples/synthetic/  known-source firmware laboratory and generated artifacts
scripts/            reproducible dataset builder
tests/              automated tests
```

## Next milestone

Wrap the analysis session in narrowly scoped, validated agent tools with
documented input, output, failure cases, and output-size limits — still with no
model attached. After that, the investigator agent explains five functions and
each explanation cites inspectable evidence.

See [docs/architecture.md](docs/architecture.md) and
[docs/experiments.md](docs/experiments.md) for the execution plan.
