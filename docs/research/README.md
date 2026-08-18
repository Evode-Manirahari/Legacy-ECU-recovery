# `docs/research/` — RESEARCH-001 artifacts

First ECU architecture research. Produced by node `RESEARCH-001`
(`prompts/RESEARCH-001.md`), which owns `docs/research/**` and nothing else.

**Status: VERIFYING — awaiting the human gate.** `ecu-project.graph.yaml`
records `RESEARCH-001` as `verification: human` with a note that this node
"recommends candidates only; target selection is a human gate". No architecture
has been selected here, and an agent must not self-approve this node.

## Contents

| File | Purpose |
|---|---|
| [`ecu-target-matrix.md`](ecu-target-matrix.md) | **Required deliverable.** The candidate matrix, structural findings, and per-candidate detail |
| [`ecu-target-matrix.csv`](ecu-target-matrix.csv) | **Required deliverable.** Machine-readable matrix: 12 candidates × 28 columns |
| [`ranked-candidates.md`](ranked-candidates.md) | Three defensible orderings, the recommended shortlist, and what would change it |
| [`decision-brief.md`](decision-brief.md) | What the human gate must decide, and the experiment that would resolve most of the uncertainty |
| [`tool-support-evidence.md`](tool-support-evidence.md) | The verifiable evidence base, with reproduction commands |
| [`uncertainties.md`](uncertainties.md) | UNKNOWNs, assumptions, and blockers |
| [`sources.md`](sources.md) | Source list, graded by authority |

## Reading order

- **Deciding the target?** [`decision-brief.md`](decision-brief.md), then
  [`ranked-candidates.md`](ranked-candidates.md).
- **Checking the work?** [`tool-support-evidence.md`](tool-support-evidence.md)
  — every claim there is reproducible or cited — then
  [`uncertainties.md`](uncertainties.md).
- **Consuming the data?** [`ecu-target-matrix.csv`](ecu-target-matrix.csv). The
  fifteen contract-required columns come first, in contract order; thirteen
  extended columns follow.

## Epistemic convention

Every claim in these files is labelled:

- **FACT** — verified here, against a vendor document or a command run on this
  host. Cells marked "(verified locally)" are reproducible.
- **INFERENCE** — reasoned from a fact, with the reasoning stated so it can be
  attacked. Confidence is given.
- **RECOMMENDATION** — a proposal for the human gate. Never a decision.
- **UNKNOWN / UNMEASURED** — not established. Recorded as absent evidence, not
  softened into a neutral-looking grade.

This follows MASTER_SPEC.md §30's requirement that an agent distinguish KNOWN,
INFERRED and UNKNOWN, and §52's rule that no important claim exists without
traceable evidence.

## Headline results

1. **Four candidate families have no Ghidra processor language at all** —
   C166/C167/ST10, 68HC11/68HC16, the Ford 8061/8065 derivatives, and M32R.
   Since implementing processor support is out of scope, they are not
   attemptable as a first target. Verified locally against Ghidra 12.1.2.

2. **Three more have *partial* support whose gaps land on the most valuable
   code.** Ghidra's SH-2 language is compiled without the FPU, and
   SH7055/SH7058 are SH-2E parts that have one. The 68000 module has no CPU32
   variant and lacks the table lookup/interpolate instructions the MC68332
   carries specifically for engine-control interpolation. V850 ships only the
   base variant against E-series firmware. All verified from SLEIGH source.

3. **Ghidra support and compiler support are near-independent**, producing three
   trap combinations — analyse-but-cannot-build (TriCore, HCS12),
   build-but-cannot-analyse (M32R), and neither (C166, EEC). `EVAL-STATIC-001`
   needs both.

4. **No candidate is simultaneously the commercial target and the easy target.**
   The families with the largest installed base have the weakest tooling and the
   worst sample legality. That tension is the decision, and it is why the gate
   is human.

5. **The largest gap is that decompiler quality was measured for nobody.**
   [`decision-brief.md`](decision-brief.md) §4 proposes a bounded, cheap
   experiment that would fill it in — for the gate to route, not for this node
   to run.

## Scope boundaries observed

- No firmware was downloaded, requested, or linked as obtainable.
- No processor support was implemented.
- `ecu-project.graph.yaml` was not modified.
- `SYMBOLIC-001` was not scheduled; angr was not installed; no symbolic
  execution was implemented. Symbolic-tooling coverage is *recorded* per
  architecture because it may affect future feasibility, and for no other
  reason.
- No files outside `docs/research/**` were created or modified.
- No downstream node was started.
