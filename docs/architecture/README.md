# System architecture

> **Is this vulnerability actually reachable?**

That question is the product. Everything below exists to answer it with evidence
a security engineer can check, and to refuse to answer when the evidence does not
support one.

![Automotive Firmware Reachability Engine architecture](ecu-reachability-architecture.png)

**The diagram is the source of truth for system design.** Where this prose and
the diagram disagree, the prose is wrong. When the architecture changes, the
diagram and these contracts change first — a system design that arrives through
an implementation diff is a design nobody reviewed.

## The principle

> **The model can suggest. The analysis engine decides. The evidence proves.**

Three sentences, three different components, and no overlap between them. Most of
the boundaries documented here exist to keep that sentence true under pressure.

## Why the question is hard

A firmware image may carry a hundred known CVEs in vendored components. A
scanner will list all hundred. That list is nearly useless to the team that has
to decide what to fix before the next release, because it answers *presence*.

The question that allocates engineering time is different: can an attacker
actually drive this defect from somewhere they can touch — CAN, UDS, DoIP, OTA?
Answering that requires a **path** through the binary, from a source an attacker
influences to the sink where the vulnerability lives.

Presence is a lookup. Reachability is an analysis, and it either has a path or
it does not.

## The pipeline

```text
                        Firmware image
                              |
                           Intake  (arch, load address)
                        /                        \
        Components, CVEs                    Binary analysis
        (vulnerable sinks)                  (Ghidra, CFG, dataflow)
                        \                          |
                         \                   Attack surface
                          \                  (CAN, UDS, DoIP, OTA)
                           \                      /
                            \                    /
    LLM sidecar  ------->     Reachability  <----
    (never decides)          (sinks meet sources)
                                    |
                                 Verdict  ------->  Verification
                              (three buckets)      (for inconclusive)
                                    |                    |
                                    +--------+-----------+
                                             |
                                       Evidence pack
```

Three shapes in the diagram carry meaning that is easy to lose in a rewrite.

**Attack surface sits below binary analysis, not beside it.** The automotive
sources are a *result* of control-flow and data-flow analysis, not a separate
input that happens to arrive at the same time. You cannot know that a function
is reachable from a UDS handler until you have the program representation that
shows the handler and what it calls. Only the CVE branch runs independently of
binary analysis, because a component inventory needs no CFG.

**The sidecar is the only box drawn in a different colour.** It feeds
Reachability and is never fed by it. It has no arrow to Verdict. The drawing
states its trust class before any sentence does, and that is deliberate: the
single most likely way this system decays is the sidecar quietly acquiring a
vote.

**Verification hangs off Verdict as a side branch.** Both Verdict and
Verification converge on the Evidence Pack, so a pack exists whether or not
verification ran. Emulation is never a prerequisite for an answer.

## The components

| Component | Owns | Contract |
|---|---|---|
| Intake | Establishing what the image is before anything reads it as code | [intake.md](components/intake.md) |
| Components, CVEs | Mapping known vulnerabilities to vulnerable sinks | [cve-sinks.md](components/cve-sinks.md) |
| Binary analysis | The program representation: functions, CFG, data flow | [binary-analysis.md](components/binary-analysis.md) |
| Attack surface | Identifying externally influenced automotive sources | [attack-surface.md](components/attack-surface.md) |
| Reachability engine | Deciding whether a source reaches a sink | [reachability-engine.md](components/reachability-engine.md) |
| LLM sidecar | Interpretation and labelling. Never a verdict | [llm-sidecar.md](components/llm-sidecar.md) |
| Verdict | The three-bucket result and its justification | [verdict.md](components/verdict.md) |
| Verification | Optional runtime evidence for inconclusive findings | [verification.md](components/verification.md) |
| Evidence pack | The deliverable: the chain a reader can check | [evidence-pack.md](components/evidence-pack.md) |

Each contract answers six questions in a fixed order — position, responsibility,
inputs, outputs, permitted dependencies, verification. The order is fixed so a
missing answer is visible rather than absorbed into prose, and the dependency
list is what turns "the sidecar must not decide" into something checkable.

## Invariants

These do not change without an architecture change, documented first.

1. **Components/CVEs produce vulnerable sinks.** Nothing else may introduce one.
2. **Binary analysis produces the program representation** used to discover
   automotive sources.
3. **Attack surface is downstream of binary analysis.**
4. **Reachability deterministically joins sources to sinks.** Same inputs, same
   verdict, every time.
5. **The LLM sidecar never decides a verdict**, and never influences one.
6. **Verdicts are exactly `REACHABLE`, `NOT_REACHABLE`, `INCONCLUSIVE`.** There
   is no fourth bucket and no "probably".
7. **Prefer `INCONCLUSIVE` over an unjustified `NOT_REACHABLE`.**
8. **Verification is optional**, triggered by an `INCONCLUSIVE` finding or an
   explicit customer request, and is not on the normal critical path.
9. **Verified and unverified findings both produce an Evidence Pack.**
10. **No confidence percentage belongs on the reachability verdict.** The
    evidence chain is what supports it.

### Why 7 is stated as a preference rather than a tolerance

The three verdicts do not have symmetrical costs.

A wrong `REACHABLE` wastes engineering time: someone investigates a path that
turns out not to exist, and finds that out. An `INCONCLUSIVE` is honest about
work remaining. A wrong `NOT_REACHABLE` tells a security team that a live,
exploitable defect is safe to deprioritise — and unlike the other two, nothing
downstream is looking for it. It is the only error whose cost is paid entirely
by somebody who trusted the answer.

So the engine is built to be *unable* to say `NOT_REACHABLE` without a
justification for the absence of a path, and a **false-unreachable is a release
blocker** in the benchmark. See [../../EVALS.md](../../EVALS.md).

### Why 10 is an invariant and not a preference

A confidence percentage on a verdict invites the reader to average. Two findings
at "70%" are not interchangeable if one is missing an indirect-call resolution
and the other is missing a loop bound — and the number hides exactly that
difference. The Evidence Pack lists what was established and what was assumed,
which is the same information without the false arithmetic.

This does not touch the sidecar's own self-reported confidence in its claims.
That is a property of a *suggestion*, and it is useful precisely because a
suggestion is not a verdict. See [components/llm-sidecar.md](components/llm-sidecar.md).

## What exists today

The architecture describes the target system. Four boxes are substantially
built, and this section says which so that the diagram is not read as a
description of finished software.

| Box | Status | Where |
|---|---|---|
| Intake | **Built** | `src/ecu_recovery/intake.py`, `binary/`, `models.py` |
| Binary analysis | **Built for CFG-level facts** | `src/ecu_recovery/analysis/`, `ghidra/` — functions, call graph, xrefs, decompilation. Data-flow analysis is **not** built |
| LLM sidecar | **Built** | `src/ecu_recovery/agent/`, `providers/openai/`, and the capture/provenance chain in `evaluation/agent/` |
| Evidence pack | **Foundations built** | `src/ecu_recovery/evidence/schema.py`, `reports/` — the `known`/`inferred`/`unknown` discipline predates this architecture and survives it |
| Components, CVEs | **Not built** | — |
| Attack surface | **Not built** | — |
| Reachability engine | **Not built** | — |
| Verdict | **Not built** | — |
| Verification | **Not built** | — |

Nothing in this table is closed by this document. Each unbuilt component
requires its own node, its own authorization, and its own evidence.

## Reading the repository against the diagram

The Python package is still named `ecu_recovery` and the repository is still
`Legacy-ECU-recovery`. Both names predate this architecture and are kept for now:
renaming touches every import across work that is already verified, which is a
large diff to change a string. The names are historical, not a statement of
scope.

New components are expected to live under a path that names the box they
implement, so that an engineer can hold the diagram beside the source tree and
see the correspondence.

## Related

- [components/](components/) — the nine contracts
- [../MASTER_SPEC.md](../MASTER_SPEC.md) — the authoritative specification and
  the graph-engineering process
- [../../EVALS.md](../../EVALS.md) — benchmark obligations, including the
  false-unreachable release blocker
- [../../THREAT_MODEL.md](../../THREAT_MODEL.md) — what this system does not do
