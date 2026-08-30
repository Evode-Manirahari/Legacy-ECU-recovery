# Component: Reachability engine

**Status:** not built — this is the core of the product

## 1. Position in the architecture

The join. Both branches converge here: vulnerable sinks from the CVE branch,
automotive sources from the attack-surface branch. The sidecar feeds in from the
side and the verdict flows out the bottom.

This is the component the product is named after, and the only one permitted to
decide anything.

## 2. Responsibility

Determine, **deterministically**, whether a path exists from an automotive source
to a vulnerable sink — and produce the evidence for whichever answer it gives.

Three properties define it:

**Deterministic.** Same inputs, same answer, every time. No sampling, no
model call, no time-dependent behaviour. A verdict that could differ between two
runs over the same firmware is not a verdict.

**Path-based.** The answer is a path or the justified absence of one. Not a
score, not a heuristic similarity, not a plausibility argument.

**Gap-aware.** The engine consumes the representation gaps that Binary analysis
and Attack surface report. An unresolved indirect call between a source and a
sink means the engine does not know — and `INCONCLUSIVE` is the honest output.
An engine that searched an incomplete graph and reported `NOT_REACHABLE` has
produced the one error this system treats as release-blocking.

## 3. Inputs

- Vulnerable sinks, with locations and their unlocated cases.
- Automotive sources, with entry points, influenced data, and their unconfirmed
  candidates.
- The program representation: CFG, call graph, data flow.
- **The gap inventory** from both upstream branches.
- Optionally, sidecar annotations — clearly marked as suggestions.

## 4. Outputs

For each (source, sink) pair under consideration:

- A verdict: `REACHABLE`, `NOT_REACHABLE`, or `INCONCLUSIVE`.
- For `REACHABLE`: the concrete path, source to sink, with the CFG and data-flow
  steps that support each hop.
- For `NOT_REACHABLE`: the justification for the absence — what was searched,
  what was complete, and why no path exists.
- For `INCONCLUSIVE`: precisely what blocked the decision, named specifically
  enough to act on.
- Unresolved assumptions, in every case.

**No confidence percentage.** See the verdict contract.

## 5. Permitted dependencies

- **Components/CVEs** — sinks.
- **Attack surface** — sources.
- **Binary analysis** — the representation to traverse.

**The LLM sidecar is an input, not a dependency.** The engine may read sidecar
annotations as hints about *where to look*. It may not use one as a step in a
path, as a reason to conclude no path exists, or as any part of a justification.
Remove every sidecar annotation and the verdict must not change. That is the
testable form of "never decides", and it is the property this whole architecture
is arranged to protect.

Not permitted: Verdict, Verification, Evidence pack — all downstream.

## 6. Verification and testing

Against a benchmark corpus with known reachable and unreachable pairs:

- **Reachable-path recall** — of the genuinely reachable pairs, how many found.
- **False-reachable rate** — paths claimed that do not exist.
- **False-unreachable rate — a release blocker.** A single confirmed
  false-unreachable blocks release. This threshold is not negotiable and must
  not be relaxed to make a suite pass.
- **Inconclusive rate** — tracked, because an engine that answers
  `INCONCLUSIVE` to everything is trivially safe and useless.
- **Analysis runtime.**

And structurally:

- **Sidecar-independence:** the same corpus run with all sidecar annotations
  removed produces byte-identical verdicts. This is the load-bearing test of the
  architecture.
- **Determinism:** repeated runs produce identical verdicts and identical paths.
- **Gap propagation:** a fixture with an unresolved indirect call on the only
  route between source and sink yields `INCONCLUSIVE`, never `NOT_REACHABLE`.
