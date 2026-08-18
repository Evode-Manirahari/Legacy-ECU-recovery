# Synthetic Firmware Laboratory

## Purpose

The laboratory provides ground truth before any AI or Ghidra integration is
added. Each sample has known source, two analysis builds, a callable behavior
artifact, machine-readable expectations, and a reproducible compiler record.

The investigator must receive only:

```text
samples/synthetic/binaries/<sample_id>/firmware.stripped
```

It must not receive `source/`, `ground_truth/`, `firmware.symbols`,
`behavior.dylib`, or `build.json` during a blinded evaluation.

## Architecture choice

Dataset v1 targets `x86_64-apple-darwin`, little-endian, 64-bit Mach-O. This is a
laboratory architecture, not the selected legacy ECU architecture.

Reasons:

1. The checked development host includes an x86-64 Apple Clang toolchain, `nm`,
   and `strip`, so every artifact can be compiled and executed now.
2. Ghidra lists x86-64 among its supported processor families and imports Mach-O
   executables.
3. Unicorn supports x86-64, preserving a controlled route to the later emulation
   milestone.
4. Native behavior execution lets the project verify semantic ground truth
   before trusting a decompiler or model.
5. Selecting a historical ECU target without authorized samples and specialist
   input would conflate the laboratory decision with the product decision.

This choice is intentionally host-specific. A later dataset version may add a
bare-metal cross target after its compiler and linker are pinned.

## Known limitation: the fixtures only execute on x86-64 macOS

Everything that *runs* a fixture is gated on `x86_64` Darwin:

- `scripts/build_synthetic.py` refuses to build on any other host;
- behaviour probes load `behavior.dylib` through `ctypes`;
- self-test and reproducibility checks execute the Mach-O binaries directly;
- constant recovery reads Mach-O disassembly through `otool`.

**CI runs on Linux, so those tests skip there** — currently 13 skips. What still
runs everywhere is the metadata layer: ground-truth completeness, artifact
hashes, category coverage, and the contract-field checks. A fixture regression
that changes behaviour would therefore be caught on a developer's macOS machine,
not by CI.

`DATA-001` was explicitly ruled *not* to solve this. Making the laboratory
portable means choosing a second architecture, and `RESEARCH-001` has not yet
recommended the first one; rebuilding before that recommendation exists would
mean choosing twice. The options when it is addressed are an x86-64 macOS CI
runner, a portable cross-compiled target, or accepting the gap deliberately.

## Dataset layout

```text
samples/synthetic/
├── manifest.json
├── source/                 known C source; hidden during evaluation
├── ground_truth/           expected functions, calls, constants, and behavior
└── binaries/
    └── <sample_id>/
        ├── firmware.symbols
        ├── firmware.stripped
        ├── behavior.dylib
        └── build.json
```

`firmware.stripped` is copied from `firmware.symbols` and then stripped. This
keeps machine code and function addresses aligned while removing the semantic
function names used for ground-truth mapping. Mach-O retains the generic `main`
entry symbol; scoring includes it as an expected function but excludes it from
semantic classification. `behavior.dylib` exports only the uniform three-
argument `sample_invoke` test entry point.

## Rebuild

```bash
uv run python scripts/build_synthetic.py
```

The build requires an x86-64 macOS host with Clang, `strip`, and `nm` on `PATH`.
It fixes the target, minimum macOS version, optimization level, code-generation
flags, locale, linker UUID behavior, and dynamic-library install name. Every
`build.json` records commands, compiler version, source hash, and artifact hashes.

## Samples

All eight fixture categories required by the `DATA-001` contract:

| # | Category | Sample |
|---|---|---|
| 1 | temperature threshold controller | `temperature_controller_v1` |
| 2 | RPM-like calculation | `rpm_calculation_v1` |
| 3 | one-dimensional lookup table | `lookup_1d_v1` |
| 4 | two-dimensional lookup table | `lookup_2d_v1` |
| 5 | state machine | `state_machine_v1` |
| 6 | multi-function call graph | `multi_function_pipeline_v1` |
| 7 | integer/bit-mask manipulation | `bitmask_manipulation_v1` |
| 8 | timer-like counter logic | `timer_counter_v1` |

1. strict temperature threshold controller;
2. pulse-period to RPM calculation with invalid-input guards;
3. clamped one-dimensional table with integer interpolation;
4. clamped three-by-four calibration table;
5. four-state controller with RPM and fault transitions;
6. sensor normalization, gain, and clamping call pipeline;
7. nibble-field extraction, flag counting, and mask clearing over a packed
   status word;
8. sixteen-bit free-running counter with rollover-correct elapsed time, a fixed
   stale threshold, and a caller-supplied clamp.

## What `expected_constants` means

A constant is recoverable if the compiler emitted it either as an instruction
operand or as data. Which one happens is the compiler's choice, not the fixture
author's:

- small values become one-byte immediates (`rpm_calculation_v1`'s `60`);
- table entries land in `__TEXT,__const` as int32 data (`lookup_1d_v1`'s axis
  and output tables);
- some values survive as neither.

`test_expected_constants_are_actually_recoverable` checks both encodings for
every sample. It exists because a claimed-but-absent constant would score as a
tool failure during evaluation when the fault is really in the fixture.

Two constants are deliberately **not** claimed, and each sample records why in
a `constant_notes` field:

- `timer_counter_v1` does not claim its `65536` modulus. The compiler proves the
  wrap is a sixteen-bit truncation and emits `movzwl` with no operand.
- `bitmask_manipulation_v1` does not claim `28`; the range check compiles to an
  unsigned comparison against `29`.

Zero is not claimed by the two fixtures added under `DATA-001`, because it is
materialised with `xor` rather than an operand. The six earlier fixtures do
claim it, which is a discrepancy `EVAL-STATIC-001` will need to settle when it
defines the constant-discovery metric.

## Exact scoring for Prompt 3 and later

Run analysis against `firmware.stripped` only. After the run is immutable, use
the matching `firmware.symbols` symbol addresses to reveal ground truth.

- **Function discovery true positive:** a reported function starts at the exact
  ground-truth address of an `expected_functions` entry.
- **Function discovery precision:** true-positive expected functions divided by
  all reported functions within the sample's own text range. Report compiler
  startup functions separately rather than counting them as false positives.
- **Function discovery recall:** true-positive expected functions divided by all
  expected functions.
- **Call-edge precision/recall:** exact address-pair comparison after mapping
  names through `firmware.symbols`. Repeated calls to the same callee count once.
- **Function classification:** score only `classification_functions`, which
  excludes the generic self-test harness and probe adapter. Two reviewers,
  blinded to each other's scores, compare an explanation with
  `expected_function_roles`: `1` for the correct role and input/output
  relationship, `0.5` for a materially incomplete but non-conflicting
  explanation, and `0` for wrong or unsupported semantics. Reconcile
  disagreements and retain both raw scores.
- **Behavior:** call `sample_invoke` with every ordered metadata input. Score is
  exact integer matches divided by total cases. No tolerance is used in v1.
- **Evidence validity:** each cited address must resolve to the claimed function,
  instruction, constant, or call edge. Valid citations divided by all citations.
- **Confidence calibration:** group claims into ten confidence buckets and
  compare mean confidence with empirical classification accuracy.

Always publish numerators, denominators, tool versions, and failures alongside
percentages. Do not use an LLM as the only evaluator.
