# Evaluation Contract

Correctness is measured against **controlled ground-truth binaries** whose source
this repository compiled and hides from the analysis system. “The output looks
good” is not an acceptance criterion.

The project is successful only when it produces repeatable, evidence-backed
results against ground truth and saves expert time.

## Reachability benchmark

The reachability engine is benchmarked on **every meaningful change**. This is CI
and development infrastructure: it does not appear in the runtime architecture
and no production component may depend on it.

| Metric | Measures | Obligation |
|---|---|---|
| Reachable-path recall | Of genuinely reachable pairs, how many were found | tracked, target set per release |
| **False-unreachable rate** | Genuinely reachable pairs classified `NOT_REACHABLE` | **release blocker** |
| False-reachable rate | Paths claimed that do not exist | tracked |
| Inconclusive rate | Pairs the engine could not decide | tracked |
| Attack-surface identification | Recall and precision of automotive sources, per protocol class | tracked |
| Vulnerable-sink mapping | Recall and precision of CVE-to-sink location | tracked |
| Analysis runtime | Wall-clock per image | tracked |

### The false-unreachable release blocker

**A confirmed false-unreachable blocks release.** One is enough.

The three verdicts do not have symmetrical costs. A wrong `REACHABLE` wastes
engineering time and gets discovered by whoever investigates it. An
`INCONCLUSIVE` is honest about work remaining. A wrong `NOT_REACHABLE` tells a
security team that a live, exploitable defect is safe to deprioritise, and
nothing downstream is looking for it. It is the only error whose cost is paid
entirely by somebody who trusted the answer.

**This threshold is not to be relaxed to make a suite pass.** If a change
introduces a false-unreachable, the change is wrong or the analysis is
incomplete; either way the engine should have returned `INCONCLUSIVE`. Lowering
the bar converts a caught defect into a shipped one.

The inconclusive rate is tracked alongside it for the obvious reason: an engine
that answers `INCONCLUSIVE` to everything has a perfect false-unreachable rate
and no value. The pair has to be read together.

### Sidecar independence

A structural check rather than a metric, run over the same corpus: with every
sidecar annotation removed, verdicts must be **byte-identical**. This is the
testable form of "the model never decides", and it is the benchmark's most
load-bearing assertion about the architecture.

## Verification hierarchy

Use the highest level that can decide the property.

| Level | Method | Use for |
|---|---|---|
| 1 | Deterministic | test result, compiler result, schema validation, binary/call-graph/behavior comparison |
| 2 | Ground-truth comparison | hidden fixture data |
| 3 | Human expert | semantic engineering judgment |
| 4 | LLM judge | only when none of the above can reasonably evaluate it |

> If software can prove it, do not ask another model whether it looks correct.

## `EVAL-STATIC-001` gate targets

Starting thresholds for controlled synthetic fixtures — not immutable truths:

| Metric | Target |
|---|---|
| Binary import success | 100% |
| Serialization success | 100% |
| Function discovery recall | ≥ 95% |
| Function discovery precision | ≥ 95% |
| Call-edge recall | ≥ 90% |
| Unexpected crashes | 0 |

If observed baseline makes a threshold unrealistic, **do not quietly lower it**.
Record the observed baseline, the cause, the proposed new threshold, and the
human approval.

## Agent-phase targets

Applied only after `GATE-STATIC-MVP`:

| Metric | Target |
|---|---|
| Evidence references valid | 100% |
| Schema compliance | 100% |
| Unsupported factual claims | ≤ 5% |
| Tool hallucinations | 0 |
| Critical unsupported claims | 0 |

Semantic classification accuracy is baselined first and only then set as a formal
gate. Do not invent a flattering threshold before seeing performance.

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
[`docs/synthetic-lab.md`](docs/synthetic-lab.md). Any static-analysis run must
analyze only each `firmware.stripped` file, freeze its results, and only then
reveal symbols-on addresses and JSON ground truth. Function and call-edge scores use exact address matches;
behavior uses exact integer equality. Report raw counts with every rate.

## Pre-graph static-analysis measurement

**This is not `EVAL-STATIC-001`.** No evaluation harness exists, no
`artifacts/evals/` outputs exist, and no comparison against the gate targets
above has been run. These numbers come from assertions inside
`tests/test_analysis_ghidra.py`, recorded under the deprecated linear sequence.
They are evidence that the extraction path is wired correctly — not a gate result.

Engine: Ghidra 12.1.2 via PyGhidra 2.2.1, Zulu OpenJDK 21, macOS x86-64. Detected
language `x86:LE:64:default`. Input: `firmware.stripped` only; ground truth read
from the symbols-on build afterwards.

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
