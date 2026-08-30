# Component: Binary analysis

**Status:** partly built — `src/ecu_recovery/analysis/`, `ghidra/`.
CFG-level facts exist. **Data-flow analysis is not built.**

## 1. Position in the architecture

The right branch out of Intake. It produces the **program representation** that
everything on that side depends on: Attack surface is derived from it, and the
Reachability engine traverses it.

It is **not** where automotive meaning is assigned. This component knows about
functions, blocks, edges and data movement. It does not know what UDS is. That
distinction is what keeps the next component replaceable.

## 2. Responsibility

Produce a faithful, deterministic program representation of the image:
functions, control-flow graph, call graph, cross-references, and data flow.

Faithful matters more than complete. Where the representation is incomplete —
an unresolved indirect call, an unreconstructed jump table, a region that failed
to disassemble — the incompleteness is **part of the output**, not an omission.
The Reachability engine cannot honestly return `NOT_REACHABLE` without knowing
where the graph it searched was blind.

## 3. Inputs

- Intake output: identified image, architecture, load address.

## 4. Outputs

- Function inventory with addresses and bounds.
- Control-flow graph, per function and across calls.
- Call graph, including call sites.
- Cross-references.
- Data-flow facts: definitions, uses, and propagation between them.
- Decompilation and disassembly, as citable evidence.
- **An explicit inventory of representation gaps** — unresolved indirect calls,
  unreconstructed dispatch, undisassembled regions.

## 5. Permitted dependencies

- **Intake** — for the identified image and address base.

Not permitted: the CVE branch, Attack surface, Reachability, Verdict,
Verification. This component is upstream of all of them.

**Not permitted: the LLM sidecar.** The program representation is the evidentiary
floor of the whole system. A model-suggested edge in the CFG would be
indistinguishable, downstream, from an edge the disassembler found — and a
verdict resting on it would be a model's opinion wearing the clothes of a
deterministic result. The sidecar may *read* this output and comment on it; it
may not contribute to it.

## 6. Verification and testing

- Function discovery measured against hidden ground truth in the synthetic lab
  (this already exists: `EVAL-STATIC-001`).
- Call-graph edges compared against known ground-truth edges.
- Data-flow facts checked against fixtures with known propagation.
- **The gap inventory is tested as a first-class output:** a fixture containing
  a deliberately unresolvable indirect call must report it. A component that
  silently omits what it could not resolve is the direct cause of a
  false-unreachable.
- Determinism: two runs over identical bytes produce an identical representation.
