# Research

## Record format

Every important external idea records: **source**, **date**, **claim**, **why it
matters**, **decision affected**, and **confidence**. Do not copy trendy
architectures blindly.

Experiment entries record: date, question, sources or experiment identifiers,
observations, decision impact, unresolved uncertainty, and the next falsifiable
test. Never store questionable proprietary firmware in this repository.

---

## 2026-08-17 — Research basis for the graph process

**Source:** `docs/MASTER_SPEC.md` §7, citing Andrew Ng's *Agentic AI* course,
Anthropic's long-running-agent and parallel-compiler engineering work, Claude
Code worktree isolation, LoopsBench, AgentFlow, and Karpathy's *Software Is
Changing (Again)*.

**Claim:** Long-horizon agent builds work better as dependency DAGs of separately
testable units with structured handoffs than as one autonomous loop; parallelism
helps for independent work and hurts on a shared bottleneck; evaluation should
precede scaling autonomy.

**Why it matters:** This project chains static analysis, agents, emulation,
peripheral modeling, and reconstruction. Errors propagate — bad binary analysis
yields bad hypotheses, bad experiments, and bad reconstruction. Decomposition
plus verification on the edges is what stops silent propagation.

**Decision affected:** `ADR-001`, `ADR-002`. Graph outside, loops inside, tests
on the edges. Evals before autonomy.

**Confidence:** Medium-high as an engineering method; deliberately held as a
hypothesis rather than doctrine. The specification itself warns that harness
assumptions go stale as models improve, and directs review of the graph after
every major gate.

**Unresolved:** The primary sources are cited in the master specification and have
not been independently read and verified in this repository. Treat the summary
above as second-hand until they are.

---

## 2026-08-17 — Symbolic execution as a deterministic evidence source

**Source:** project orchestrator, proposing a candidate `SYMBOLIC-001` node.
Candidate engine: `angr` (https://angr.io).

**Claim:** A symbolic executor can mechanically recover a function's input
partitions, path constraints, and observable effects — for example that
`temp < 80 → 0`, `80 ≤ temp < 100 → 1`, `temp ≥ 100 → 2` — from a stripped
binary, without executing it and without asking a model to infer it.

**Why it matters:** It sits in the gap between static structure and full
emulation. Static analysis says a function exists and what it references;
emulation says what it does but needs a modelled environment, which the
specification already identifies as the hardest engineering problem. Symbolic
analysis could supply behavioral evidence for the subset of functions that are
self-contained, at far lower cost, and it produces facts a solver can defend
rather than prose a model produced.

It also strengthens an existing rule: do not ask an LLM to rediscover what
deterministic analysis can establish. Every partition a solver recovers is one
fewer claim resting on interpretation.

**Decision affected:** None yet. Recorded in `TODO.md` under candidate nodes,
deliberately kept out of `ecu-project.graph.yaml` so it cannot be mistaken for
scheduled work. It would attach after `GATE-STATIC-MVP` as an optional branch
alongside `AGENT-001`, never as a mandatory dependency.

**Confidence:** Medium on value, low on coverage. Symbolic execution is mature
and `angr` is well established, but the fraction of *real ECU* functions it can
handle is unknown and probably small: interrupt-driven code, memory-mapped
peripherals, timing dependence, and path explosion each defeat it, and legacy
automotive firmware has all four. The synthetic fixtures would likely flatter
it, since they were written to be self-contained.

**Unresolved:** Whether coverage on real firmware is high enough to justify a
second analysis engine. Also unverified from here: `angr`'s support for
whichever architecture `RESEARCH-001` recommends — a hard prerequisite that
should be checked before assignment, not after.

**Next falsifiable test:** if assigned, run it blind against the synthetic
fixtures and measure recovered-condition accuracy and equivalence-class
precision/recall against hidden ground truth. Report the unsupported rate as a
headline number, not a footnote.

## 2026-08-17 — Source material reviewed (pre-graph)

The supplied project brief defines the product thesis as an autonomous embedded-
software investigation system following:

> observe → hypothesize → experiment → compare → document → repeat

The supplied step-by-step build prompts ordered delivery as static analysis,
agent investigation, evidence, evaluation, emulation, experimentation,
reconstruction, and only then productization.

> **Superseded.** That linear prompt document is deprecated; see `ADR-001`.
> References to numbered "Prompts" in entries below are history. The delivery
> ordering it described survives — the graph encodes the same ordering with
> verified edges.

## Open research question: first architecture

No architecture has been selected. Candidate evaluation must consider:

- availability of a reproducible C compiler and binutils;
- mature Ghidra processor support through PyGhidra;
- suitability for six small synthetic fixtures;
- emulator availability for the later controlled-execution milestone;
- accessible processor manuals and memory-map documentation;
- relevance to a narrow legacy ECU family;
- legally usable firmware and expert access after synthetic validation.

Do not select based on vehicle-brand recognition. Under the graph this is
`RESEARCH-001`, which produces a scored candidate matrix and *recommends* only —
final architecture selection is a human gate.

## Technical observations (historical — superseded 2026-08-17)

The three observations below were true when written and have since been overtaken
by work in the repository. They are kept as history. For the current state, read
`ARCHITECTURE.md`, which is authoritative on what exists.

- Byte intake, SQLite storage, the JSON import boundary, and Markdown output now
  exist, and environment diagnosis is implemented as `ecu-recovery doctor`.
- PyGhidra integration now exists in `ecu_recovery.analysis.ghidra`, so the third
  observation below no longer applies to the whole analysis layer — only to
  `ecu_recovery.ghidra.bridge`, which remains a JSON import boundary.

Original entries:

- The repository began empty and now contains a dependency-free Python proof of
  safe byte intake, SQLite storage, a JSON import boundary, and Markdown output.
- That proof predates the step-by-step prompt contract. Prompt 1 should preserve
  working behavior while establishing the requested package boundaries and
  developer tooling.
- Ghidra and Java availability have not yet been diagnosed by a repository
  command. That is explicitly Prompt 1 work.
- The existing Ghidra bridge is not PyGhidra integration and must not be described
  as such.

## Research log format

Future entries should record date, question, sources or experiment identifiers,
observations, decision impact, unresolved uncertainty, and the next falsifiable
test. Never store questionable proprietary firmware in this repository.

## 2026-08-17 — Synthetic architecture selected

**Question:** Which architecture minimizes uncertainty for the ground-truth lab?

**Observation:** The active host is x86-64 macOS and includes Apple Clang 16,
`strip`, and `nm`. It does not include an ARM cross-linker, ARM binutils, QEMU, or
Ghidra. Ghidra's official processor-support FAQ includes x86-64, and Unicorn's
official architecture list includes x86-64.

**Decision:** Use x86-64 Mach-O for dataset v1. This is not the real ECU target.
It lets the project validate compilation, stripping, symbol-address ground truth,
and native behavior now. Revisit the target only through a versioned new dataset.

**Sources:**

- https://github.com/NationalSecurityAgency/ghidra/wiki/Frequently-asked-questions
- https://github.com/NationalSecurityAgency/ghidra/blob/master/GhidraDocs/GettingStarted.md
- https://www.unicorn-engine.org/

**Next falsifiable test:** import one `firmware.stripped` artifact through
PyGhidra and recover expected function starts without access to source or
ground-truth metadata.

**Outcome (2026-08-17):** performed under the deprecated sequence and recorded in
`EVALS.md` → "Pre-graph static-analysis measurement". The test passed on two of
six fixtures. It is not a gate result; `EVAL-STATIC-001` has not run.
