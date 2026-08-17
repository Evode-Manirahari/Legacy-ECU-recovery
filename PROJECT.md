# Legacy ECU Recovery Agent

## Problem

Legacy embedded controllers can remain useful long after their source code,
build system, symbols, hardware documentation, and original engineering team
have disappeared. An engineer may possess an authorized firmware image but
still spend days manually determining its processor, memory layout, functions,
data tables, and behavior.

This project investigates whether a tool-using AI agent can shorten that work
while keeping every conclusion traceable to deterministic evidence.

## Intended user

The initial user is a skilled reverse engineer or embedded-systems engineer at
an ECU repair, remanufacturing, restoration, research, or legacy-product support
organization. The system supports that engineer; it does not replace their
judgment or certify recovered software.

## Initial scope

The first milestone is deliberately narrow:

> Given one known embedded binary on one supported architecture, automatically
> analyze it using Ghidra and correctly explain several important functions.

Development begins with synthetic programs whose source and behavior are known.
The analysis side will not receive their ground-truth source. Architecture
selection is explicit until automated detection can be evaluated honestly.

## Non-goals

The initial project will not implement:

- firmware flashing or modification of real ECUs;
- immobilizer, security-access, or key extraction bypasses;
- remote exploitation or vehicle-network attacks;
- CAN injection or live vehicle control;
- safety-critical deployment or certification;
- support for every ECU or processor architecture;
- whole-firmware source reconstruction;
- analysis of firmware without clear authorization.

## Milestones

1. **Engineering foundation:** reproducible Python project, diagnostic CLI,
   tests, linting, formatting, type checking, and environment documentation.
2. **Synthetic firmware laboratory:** known-source samples, reproducible builds,
   isolated ground truth, and machine-readable expectations.
3. **Deterministic static analysis:** one architecture through PyGhidra, mapped
   into provider-neutral Python records and serialized results.
4. **Bounded investigation tools:** narrow, validated, paginated queries over
   static-analysis results.
5. **Evidence-backed investigator:** one-function hypotheses with confidence,
   alternatives, uncertainties, and citations to tool results.
6. **Evaluation and reporting:** ground-truth scoring, regression fixtures, and
   an engineering report that separates known, inferred, and unknown claims.
7. **Controlled emulation:** synthetic binaries only, followed by approved,
   bounded experiments and one-function behavioral reconstruction.
8. **Real-firmware readiness:** a safety, legal, dataset, and architecture review
   before any authorized historical ECU image is introduced.

## Proposed repository structure

The structure will evolve incrementally. Prompt 1 should converge toward:

```text
Legacy-ECU-recovery/
├── README.md
├── pyproject.toml
├── PROJECT.md
├── ARCHITECTURE.md
├── DECISIONS.md
├── TODO.md
├── EVALS.md
├── THREAT_MODEL.md
├── RESEARCH_NOTES.md
├── docs/
├── samples/
│   └── synthetic/
├── scripts/
├── src/
│   └── ecu_recovery/
│       ├── binary/
│       ├── analysis/
│       ├── agent/
│       ├── evidence/
│       └── reports/
└── tests/
```

