# Architecture Decisions

Decisions are append-only. If a choice changes, add a superseding entry instead
of rewriting history.

## 2026-08-17 — Begin with evidence-backed understanding

**Status:** accepted

The product begins with binary understanding, not flashing, vehicle control, or
whole-firmware reconstruction. Semantic conclusions must retain confidence,
evidence, and uncertainty.

## 2026-08-17 — Use Python for orchestration

**Status:** accepted

Python 3.11+ provides a practical interface to analysis tools and supports fast
experimentation. Performance-sensitive emulation may use another language later,
but that need has not been demonstrated.

## 2026-08-17 — Use synthetic ground truth before real ECU firmware

**Status:** accepted

Known-source samples allow objective comparison of discovered functions,
constants, call relationships, and behavior. The source will be stored separately
from artifacts made available to the investigator.

## 2026-08-17 — Select one architecture explicitly

**Status:** accepted

Automatic architecture detection is deferred. The first architecture will be
chosen using toolchain availability, Ghidra support, emulation prospects,
documentation, legal sample availability, and access to expert validation.

## 2026-08-17 — Keep reverse-engineering internals behind plain models

**Status:** accepted

Ghidra-specific Java objects must not escape the analysis adapter. Core and agent
layers will consume serializable Python records so analysis engines and model
providers remain replaceable.

## 2026-08-17 — Use SQLite for early investigation state

**Status:** provisional

SQLite is sufficient for a local, single-investigator prototype and requires no
service. Revisit only after concurrency or scale creates a measured limitation.

## 2026-08-17 — Lock the Python environment with uv

**Status:** accepted

The repository uses standard `pyproject.toml` metadata and commits `uv.lock` for
repeatable local and automated installations. Ruff owns linting and formatting;
mypy runs in strict mode; pytest runs the test suite. Runtime code remains free
of third-party dependencies in Prompt 1.

## 2026-08-17 — Treat Ghidra and Java as optional during scaffolding

**Status:** accepted

The doctor command detects both dependencies but returns success with a clear
warning when either is unavailable. Prompt 3 may strengthen these checks after
Ghidra becomes an implemented execution path.

## 2026-08-17 — Use x86-64 Mach-O for synthetic dataset v1

**Status:** accepted for the laboratory only

The first fixtures target little-endian `x86_64-apple-darwin`. The current host
can build, strip, inspect, and execute this target without an unpinned external
cross-toolchain. Ghidra and Unicorn both support x86-64. This does not select the
eventual legacy ECU family or processor; that remains gated on authorized real
samples, documentation, tool support, emulator feasibility, and expert input.

## 2026-08-17 — Separate evaluation truth from investigator input

**Status:** accepted

The investigator receives only `firmware.stripped`. Source, JSON ground truth,
symbols-on binaries, callable behavior libraries, and build records are evaluator
assets. Symbols-on and stripped executables originate from the same compiled file
so expected functions can be matched by exact start address after a blinded run.
