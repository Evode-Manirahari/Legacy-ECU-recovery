# Evaluation Contract

The project is successful only when it produces repeatable, evidence-backed
results against ground truth and saves expert time. “The output looks good” is
not an acceptance criterion.

## Evaluation dataset

Begin with synthetic firmware for which the repository preserves:

- original source and compiler settings;
- symbols-on and symbols-stripped builds;
- architecture and memory configuration;
- expected functions, addresses or stable identifiers, constants, and calls;
- executable input/output examples;
- ground-truth behavior unavailable to the investigator during analysis.

Split fixtures into development and held-out evaluation sets before tuning agent
prompts. Record compiler and optimization variants to avoid memorizing one binary
layout.

## Static-analysis metrics

- **Function discovery precision:** matched expected functions / all reported
  functions.
- **Function discovery recall:** matched expected functions / all expected
  functions.
- **Call-edge precision and recall:** exact comparison with ground-truth caller
  and callee relationships.
- **Constant and table detection:** precision and recall for declared fixture
  values, excluding compiler-generated constants by documented rule.
- **Serialization fidelity:** deterministic analysis records survive a JSON
  round trip without information loss.

## Investigator metrics

- **Function classification accuracy:** exact or rubric-scored functional role
  against ground truth.
- **Evidence validity:** percentage of citations that resolve to the stated
  address/tool result and actually support the claim.
- **Calibration:** confidence buckets compared with empirical correctness.
- **Uncertainty quality:** unsupported claims are marked inferred or unknown;
  fabricated evidence is a critical failure.
- **Alternative coverage:** plausible competing explanations are preserved when
  evidence does not distinguish them.

An LLM may assist qualitative grading, but deterministic checks and human review
remain authoritative. Evaluation must never rely only on an LLM judge.

## Behavioral metrics for later milestones

- input/output agreement between original and reconstructed functions;
- branch and boundary-case coverage;
- mismatch rate across generated test vectors;
- deterministic replay of emulator experiments;
- regression rate after a candidate reconstruction changes.

Textual similarity to original source is not the primary measure. Observable
behavior is.

## Product metric

Measure the same investigation manually and with the system. The first target is
at least a 50% reduction in median expert time to a correct, evidence-supported
explanation of an unfamiliar function, without reducing accuracy.

## Baseline policy

Record the first complete run before prompt optimization. Store tool versions,
configuration, inputs, outputs, duration, failures, and scorer version. Never
silently replace a failed result.

## Synthetic dataset v1 protocol

The binding scoring rules for the current six fixtures are documented in
[`docs/synthetic-lab.md`](docs/synthetic-lab.md). Prompt 3 must analyze only each
`firmware.stripped` file, freeze its results, and then reveal symbols-on addresses
and JSON ground truth. Function and call-edge scores use exact address matches;
behavior uses exact integer equality. Report raw counts with every rate.

## Prompt 3 static-analysis baseline

First recorded measurement. Engine: Ghidra 12.1.2 via PyGhidra 2.2.1, Zulu
OpenJDK 21, macOS x86-64. Detected language `x86:LE:64:default`. Input:
`firmware.stripped` only; ground truth read from the symbols-on build afterwards.
Asserted in `tests/test_analysis_ghidra.py`.

| Metric | Fixture | Result | Counts |
|---|---|---|---|
| Function discovery recall | `temperature_controller_v1` | 100% | 3 / 3 |
| Function discovery precision | `temperature_controller_v1` | 100% | 3 / 3 |
| Function discovery recall | `multi_function_pipeline_v1` | 100% | 6 / 6 |
| Call-edge recall | `multi_function_pipeline_v1` | 100% | 5 / 5 |
| Call-edge precision | `multi_function_pipeline_v1` | 100% | 5 / 5 |
| Serialization fidelity | both | pass | JSON round trip, no Java objects |

Scope limits on this baseline, stated so the number is not over-read:

- Two of six fixtures are covered. `rpm_calculation_v1`, `lookup_1d_v1`,
  `lookup_2d_v1`, and `state_machine_v1` are not yet scored.
- These are unstripped-prologue, compiler-generated x86-64 Mach-O binaries at
  `-O1` with `-fno-inline` and frame pointers retained. Function boundaries are
  close to the easiest case a disassembler can be given.
- Constant and table detection, function classification, evidence validity, and
  calibration are defined but unmeasured. `search_constant` is exercised for
  correctness, not scored for precision and recall.
- No model is involved yet, so none of the investigator metrics apply.

Read this as evidence that the extraction path is wired correctly and matches
ground truth, not as a prediction about real ECU firmware.
