# NODE: REPOSITION-001

**Title:** Reachability positioning and system architecture of record
**Depends on:** `SPEC-001`, `GRAPH-001`
**Verification:** commands
**Retry budget:** 2

## Why this node exists

The product question changed. The documentation still answers the old one.

The repository currently describes an evidence-first investigation system for
undocumented firmware: `binary -> understanding -> reconstruction -> behavioral
validation`. That is a real capability and most of it is built. It is no longer
the product.

The product question is now:

> **Is this vulnerability actually reachable?**

and the product statement is:

> A tool that tells automotive security teams which vulnerabilities in their ECU
> firmware are actually reachable, not just present.

The distinction is the whole business case. A firmware image may contain a
hundred CVEs in vendored components; the ones that matter are the ones an
attacker can drive from CAN, UDS, DoIP, or OTA. Presence is a scanner's answer.
Reachability requires a path.

## The engineering principle

Every component boundary in this node exists to protect one sentence:

> **The model can suggest. The analysis engine decides. The evidence proves.**

## Goal

Make the repository describe the system actually being built, and record the
architecture as a source of truth that later implementation must map back to.

**This is a documentation node.** It writes no code. That separation is the
point rather than a scoping convenience: a system design that arrives through an
implementation diff is a design nobody reviewed.

## The architecture of record

`docs/architecture/ecu-reachability-architecture.png` is the source of truth for
system design, committed verbatim. The written architecture restates it; where
the two disagree, the diagram wins and the prose is wrong.

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

Three details of the diagram are load-bearing and must survive into the prose:

1. **Attack surface is downstream of binary analysis**, not parallel to it. The
   sources are a *result* of CFG and data-flow analysis, not an input beside it.
2. **The LLM sidecar is drawn in a different colour from everything it touches.**
   It feeds Reachability and is never fed by it, and it carries no arrow to
   Verdict. It is a different trust class, and the drawing says so before any
   text does.
3. **Verification hangs off Verdict as a side branch.** Both Verdict and
   Verification converge on the Evidence pack, so a pack exists whether or not
   verification ran. Emulation is not on the critical path.

## Component contracts

Write one file per component under `docs/architecture/components/`, each
answering these six questions **in this fixed order**:

1. **Position** - where it sits in the diagram, and what it is not.
2. **Responsibility** - the single thing it owns.
3. **Inputs** - what it receives, and from which component.
4. **Outputs** - what it produces, and in what shape.
5. **Permitted dependencies** - the explicit list of components it may call. A
   component not on this list is a violation, not an oversight.
6. **How it is tested** - the property that would fail if the boundary eroded.

The fixed order matters. A missing answer becomes visible instead of absorbed
into prose, and question 5 turns "the LLM must not decide reachability" from an
intention into a list something can check.

Nine components: `intake`, `cve-sinks`, `binary-analysis`, `attack-surface`,
`reachability-engine`, `llm-sidecar`, `verdict`, `verification`, `evidence-pack`.

## Fixed decisions

1. **Three verdicts, no fourth.** `REACHABLE`, `NOT_REACHABLE`, `INCONCLUSIVE`.
2. **Prefer `INCONCLUSIVE` to a wrong `NOT_REACHABLE`.** A false-unreachable
   tells a security team a live vulnerability is safe to ignore. It is the one
   failure whose cost is paid by somebody who trusted the answer.
3. **No confidence percentages on a verdict.** The evidence chain is what
   supports it. A number invites the reader to average away a missing path.
4. **The sidecar never decides.** It may interpret, label, explain, and
   propose lines of investigation. It may not emit or influence a verdict.
5. **Verification is optional and off the critical path.** It runs for
   `INCONCLUSIVE`, or when a customer asks. It is never a prerequisite for an
   Evidence Pack.
6. **Benchmarking is CI infrastructure, not production architecture.** It does
   not appear in the diagram and must not appear in the runtime system.

## The Evidence Pack

Nine fields, and the pack is the product:

vulnerability/CVE, vulnerable sink, automotive source/entry point,
source-to-sink path, CFG and data-flow evidence, binary/disassembly evidence,
verification evidence if performed, unresolved assumptions, and the verdict.

## Benchmark obligations (recorded here, built elsewhere)

Benchmark the reachability engine on every meaningful change:
reachable-path recall, false-reachable rate, inconclusive rate, analysis
runtime, attack-surface identification, vulnerable-sink mapping, and
**false-unreachable rate - a release blocker.**

## What must be preserved

Reframed, not deleted. Four boxes in the diagram already exist in this
repository and the documentation must say which:

- **Intake** - `intake.py`, hashing, entropy, fill-byte and repeated-block
  analysis.
- **Binary analysis** - `analysis/`, `ghidra/`, PyGhidra behind an
  engine-independent interface.
- **Evidence pack** - `evidence/schema.py`, the `known`/`inferred`/`unknown`
  discipline, and the report layer.
- **LLM sidecar** - `agent/`, `providers/openai/`, and the provenance and
  capture chain that already makes a model claim checkable.

Legacy ECU recovery becomes a **use case**, documented as such: the same call
graph and data-flow machinery answers "what does this undocumented function do".
It is not the identity of the product.

## What must be reframed or removed

- `C reconstruction` and `replacement firmware` leave the roadmap headline.
- `behavioral validation` as the end of the loop becomes optional verification.
- Confidence percentages are removed **from verdicts**. The sidecar's own
  self-reported claim confidence in `models.py` is a property of a suggestion,
  not of a verdict, and stays; say so explicitly rather than leaving the
  contradiction for a reader to find.

## Claims that must not appear

Do not state or imply that this system exploits vulnerabilities, flashes
vehicles, controls vehicles, or guarantees regulatory compliance. It reads
firmware and reports reachability with evidence.

## MVP

Narrow, and stated as the first technical goal:

> Given one supported ECU firmware image, a known vulnerable function, and an
> identified automotive entry point, determine deterministically whether a valid
> path exists from the source to the vulnerable sink, and output the evidence
> supporting that verdict.

Do not describe the whole final system as though it exists.

## Ownership

Documentation only:

```text
README.md
PROJECT.md
ARCHITECTURE.md
THREAT_MODEL.md
EVALS.md
RESEARCH.md
DECISIONS.md
docs/MASTER_SPEC.md
docs/architecture/**
docs/architecture.md
TODO.md
```

`src/**`, `tests/**`, `samples/**` and `artifacts/**` are
deliberately excluded: no component may be built under this node, and no
existing behaviour may be changed to match the new description. Where
documentation and code now disagree, record the gap as unbuilt rather than
quietly closing it.

## Acceptance

- The diagram is committed under `docs/architecture/` and referenced from the
  README above the fold.
- Nine component contracts exist, each answering all six questions in order.
- README, `PROJECT.md`, `ARCHITECTURE.md` and `docs/MASTER_SPEC.md` §1-4 state
  the reachability product, the three verdicts, and the MVP.
- Legacy recovery appears as a use case, not an identity.
- No prohibited claim appears anywhere.
- `uv run --frozen pytest` green and `git diff --exit-code uv.lock` clean -
  evidence that a documentation node changed no behaviour.
- Every changed file inside this node's allowed paths; no `src/`, `tests/`,
  `samples/` or `artifacts/` file in the diff.

## Stop

At the implementation PR's merge boundary. Building any component named in the
architecture requires its own node, and its own authorization.
