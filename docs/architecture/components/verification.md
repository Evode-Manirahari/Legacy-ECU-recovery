# Component: Verification

**Status:** not built

## 1. Position in the architecture

A **side branch off Verdict**, drawn in its own colour, rejoining at the Evidence
Pack. It is deliberately not on the line between Verdict and Evidence Pack.

That placement is the contract. Verification is optional, and the system produces
its deliverable without it.

## 2. Responsibility

Provide runtime or emulation evidence for a finding the static analysis could not
decide, when it is worth the cost.

**Triggered by exactly two things:**

1. An `INCONCLUSIVE` verdict, where runtime evidence could resolve what static
   analysis could not.
2. An explicit customer request, for any verdict.

It is never triggered automatically for `REACHABLE` or `NOT_REACHABLE`, and it is
never a prerequisite for an Evidence Pack.

### Why it stays off the critical path

Emulating ECU firmware is expensive, partial, and hardware-dependent. A pipeline
that required it would answer far fewer questions, far more slowly, and would
degrade to unusable on any target without a working emulation environment —
while the static path could have answered most of those questions already.

The failure mode this guards against is specific and common: an optional
component becomes a de-facto requirement because something upstream starts
assuming its output. Verification produces *additional* evidence for a verdict
that already exists.

**This component does not exploit anything.** It observes whether a path is
exercised. It does not develop, weaponise, or execute an exploit for a
vulnerability, and it does not run against a vehicle.

## 3. Inputs

- A finding routed from Verdict: the verdict, its justification, the path or the
  blocking reason.
- The firmware image and its Intake metadata.
- A verification environment — emulator or instrumented harness.

## 4. Outputs

- Verification evidence: what was executed, under what conditions, and what was
  observed.
- Whether the observation supports, contradicts, or fails to resolve the static
  finding.
- Its own limitations — what the environment could not model, which is often the
  most important part.
- **A verification that fails to resolve anything is still an output.** An
  `INCONCLUSIVE` that survives verification is more informative than one that was
  never examined.

Verification evidence **does not silently overwrite a static verdict.** A
contradiction between static and runtime results is reported as a contradiction,
and resolving it is engineering judgement, not an automatic rule.

## 5. Permitted dependencies

- **Verdict** — the finding to verify.
- **Intake** — the image and its metadata.

Not permitted: the Reachability engine — verification does not re-run the
decision, and must not become a second engine with a different answer.

**Not permitted: the LLM sidecar** in any deciding capacity. It may help
interpret a trace after the fact; it may not determine whether verification
succeeded.

## 6. Verification and testing

- Verification is never invoked for `REACHABLE` or `NOT_REACHABLE` without an
  explicit customer request — tested, because this is exactly how an optional
  component becomes mandatory.
- An Evidence Pack is produced for a finding with no verification, and a test
  proves the unverified path is complete on its own.
- A contradiction between static and runtime results is reported as a
  contradiction and does not silently rewrite the verdict.
- Environment limitations appear in the output.
- No exploit is generated or executed; no path targets a physical vehicle.
