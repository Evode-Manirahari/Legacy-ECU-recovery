# Legacy ECU Recovery

## Problem

Legacy embedded software routinely outlives its source repository, compiler
toolchain, design documents, debugging symbols, test suites, hardware
documentation, and original engineering team. The controller itself often still
matters — in vehicles, industrial equipment, and discontinued products.

An engineer may hold an authorized firmware image, partial manuals, and old
diagnostics, and still spend days determining the processor, memory layout,
function inventory, calibration data, and behavior by hand.

## Target user

The first user is a skilled engineer who already performs this work: an embedded
reverse engineer, ECU remanufacturer, automotive electronics repair specialist,
engineering consultant, or supplier maintaining a discontinued product.

The system augments that engineer. It does not replace engineering judgment and
it does not certify recovered software.

## Initial value proposition

Reduce the repetitive part of legacy firmware investigation — structural
analysis, cross-referencing, hypothesis generation, experimentation, and
documentation — while keeping every conclusion traceable to inspectable evidence.

Value exists before perfect source reconstruction does.

## Initial technical goal

> Take a stripped embedded binary whose source is hidden from the analysis
> system and recover useful structural information through deterministic static
> analysis, measured against hidden ground truth.

Deterministic retrieval must be reliable and measured **before** any AI agent is
introduced. Until static analysis is measurable, an error cannot be attributed
among Ghidra, the parser, the tool layer, the context, the model, and the prompt.

## Central principle

The system does not optimize for confident answers. It optimizes for testable
claims:

```text
OBSERVE → HYPOTHESIZE → TEST → COLLECT EVIDENCE → UPDATE BELIEF → VERIFY
```

Every conclusion distinguishes `KNOWN`, `INFERRED`, and `UNKNOWN`.

## Non-goals

This project does not implement:

- firmware flashing or modification of any real ECU;
- live vehicle control or vehicle-network attacks, including CAN injection;
- immobilizer bypass, security-access bypass, or credential/key extraction;
- arbitrary host execution on behalf of a model;
- analysis of firmware without documented authorization;
- support for every processor architecture;
- whole-firmware source reconstruction or "perfect" C recovery;
- safety-critical deployment or certification;
- a frontend, a complete ECU emulator, or enterprise infrastructure at this stage.

Analysis is not certification. Research, reconstruction, and deployment stay
separate.

## Development method

Work is organized as a directed acyclic **development graph** of bounded nodes,
not as one long autonomous coding loop. An edge means *the prerequisite has been
verified*, not *an agent reported done*.

Three graphs are kept distinct and must not be conflated:

| Graph | Purpose | Status |
|---|---|---|
| A — Development graph | Build the product | active |
| B — Firmware investigation graph | How the finished system investigates | not started |
| C — Firmware knowledge graph | Accumulated understanding of one firmware | not started |

Verification prefers, in order: deterministic checks, ground-truth comparison,
human expert judgment, and only then an LLM judge. If software can prove a
property, an LLM is not asked whether it looks correct.

## Milestones

Phase boundaries are gates. A gate is a verification node, not a feeling.

1. **Static MVP** — `SPEC-001` → `REPO-001` → {`DATA-001`, `RESEARCH-001`,
   `EVIDENCE-001`} → `GHIDRA-001` → `EVAL-STATIC-001` → `TOOLS-001` →
   `INTEGRATION-STATIC-001` → `GATE-STATIC-MVP`.
2. **Investigator agent** — only after `GATE-STATIC-MVP`.
3. **Emulation** — only after `GATE-AGENT-MVP`.
4. **Experimentation** — controlled, validated, human-approved.
5. **Reconstruction** — one function, verified behaviorally.
6. **Real authorized ECU firmware** — only after every prior gate, a security
   review, documented authorization, and human approval.

## Commercial question

The metric that matters is not tokens, tool calls, or hypothesis count. It is:

> How much expensive expert engineering time does the system save while
> maintaining trust?

The aspirational early target is a 50% reduction in investigation time for a
bounded firmware-analysis task. That must not be claimed until measured with a
real specialist on an authorized problem.

## Authoritative specification

`docs/MASTER_SPEC.md` is the authoritative engineering specification. Where any
other document conflicts with it, the master specification wins.

> **Blocker (2026-08-17):** `docs/MASTER_SPEC.md` is not present in this
> repository. See `TODO.md` → NOW.
