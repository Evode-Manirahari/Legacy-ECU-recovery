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

