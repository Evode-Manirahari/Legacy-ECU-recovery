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

## Quick start

Python 3.11 or newer is required.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
ecu-recovery analyze path/to/firmware.bin \
  --processor ST10F269 \
  --database artifacts/investigations.sqlite3 \
  --report artifacts/report.md
pytest
```

Only analyze firmware you are authorized to possess and inspect. Do not use a
generated conclusion as a basis for flashing a vehicle or controlling hardware.

## Project map

```text
src/ecu_recovery/   core library and CLI
src/ecu_recovery/ghidra/  Ghidra integration boundary
docs/               architecture, research decisions, experiments
samples/            local samples (firmware files are git-ignored)
tests/              automated tests
```

## Next milestone

Choose one processor family, compile a small known embedded program for it, and
export Ghidra's functions/call relationships/decompiler output into the adapter.
The milestone succeeds when the system explains five important functions and
each explanation cites inspectable evidence.

See [docs/architecture.md](docs/architecture.md) and
[docs/experiments.md](docs/experiments.md) for the execution plan.

