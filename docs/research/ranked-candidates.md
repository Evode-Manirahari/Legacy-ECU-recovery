# Ranked candidates

**Node:** `RESEARCH-001` · recommendation only. Selection is a human gate
(MASTER_SPEC.md §41). Nothing in this file constitutes a decision, and no
downstream node should treat it as one.

Evidence behind every claim: [`tool-support-evidence.md`](tool-support-evidence.md).
Full field data: [`ecu-target-matrix.csv`](ecu-target-matrix.csv).

---

## The ranking depends on what is being optimised

There is no single ordering, because the criteria conflict (see
[`ecu-target-matrix.md`](ecu-target-matrix.md), "The three structural
findings"). Three defensible orderings exist. Presenting one and hiding the
others would be presenting a decision disguised as research.

### Ordering A — optimise for pipeline verifiability

*"Pick the target that lets `DATA-001`, `GHIDRA-001` and `EVAL-STATIC-001`
produce trustworthy numbers soonest."*

1. **C3 — MPC5xx (PowerPC BE32)**
2. **C5 — MC68332 (68k CPU32)**
3. **C1 — SH-2E (SH7055/SH7058)**
4. C4 — MPC55xx VLE *(conditional on U-2)*
5. C7 — V850

Rationale: mainline compiler plus mature Ghidra language plus emulator coverage.
C3 and C5 are the only candidates in the "both" row of the Ghidra/toolchain
table. C5 ranks second rather than first only because of the verified CPU32
table-instruction gap.

### Ordering B — optimise for commercial relevance

*"Pick the target with the largest population of ECUs a paying customer will
actually bring us."*

1. **C2 — TriCore EDC17/MED17**
2. **C7 — Denso V850**
3. **C3 — MPC5xx**
4. C9 — C167/ST10 ME7/EDC15 *(blocked: no Ghidra language)*
5. C1 — SH-2E

Rationale: installed base and remaining service life. Note that the top two
both carry unresolved decode or toolchain risk, and C9 — arguably third on pure
installed base — cannot be attempted at all without authoring a processor
module.

### Ordering C — optimise for legally usable examples

*"Pick the target where we can obtain real firmware **with source** and never
touch anything of uncertain provenance."*

1. **C8 — ARM (rusEFI, Speeduino)** — but not a legacy ECU vertical
2. **C6 — HCS12 / S12X (FreeEMS, MegaSquirt)**
3. C5 — MC68332 *(literature, not firmware)*
4. C1 — SH-2E *(metadata, not firmware)*
5. everything else — no legal source-matched firmware

Rationale: MASTER_SPEC.md §40 and the node contract forbid firmware of
uncertain provenance. Only C8 and C6 have real engine-management firmware
published under a licence that permits use.

---

## Recommended shortlist for the human gate

**RECOMMENDATION.** Put three candidates to the gate, not one:

| Rank | Candidate | What choosing it buys | What it costs |
|---|---|---|---|
| 1 | **C3 — MPC5xx** | Fastest path to trustworthy `EVAL-STATIC-001` numbers; mainline GCC; both emulators; native angr lifter; genuine GM/Delphi installed base | No legal source-matched firmware; TPU3 is a second programmable processor at the emulation gate |
| 2 | **C1 — SH-2E** | Best expert-community and metadata access; excellent vendor documentation; strong aftermarket demand | Verified SH-2 FPU decode gap; no SH-2 emulator anywhere (QEMU is SH-4) |
| 3 | **C2 — TriCore** | Largest installed base; only candidate with Ghidra + Unicorn + QEMU | No mainline toolchain; weakest legal-sample position; highest peripheral and interrupt complexity |

**RECOMMENDATION.** Two further candidates should be adopted in *support*
roles regardless of which of the three is chosen, because they are cheap and
they de-risk the others:

- **C8 (ARM) as a calibration control.** rusEFI and Speeduino are real,
  GPL-licensed engine-management firmware. Running the static pipeline against
  them establishes what "good" looks like on an architecture where tooling is
  known-excellent. Without that baseline, a weak `EVAL-STATIC-001` score on a
  hard target cannot be attributed to the target rather than to the pipeline.
- **C6 (HCS12) as a fixture source.** FreeEMS and MegaSquirt MS2 give real
  automotive control firmware *with source* on an architecture Ghidra supports.
  That is a Level-2 hidden-ground-truth fixture (MASTER_SPEC.md §14) with real
  control structure, which no synthetic fixture can match.

Both are proposals for the human gate to accept or reject. Neither is scheduled
by this node, and neither is within `RESEARCH-001`'s ownership to implement.

---

## Why the shortlist is ordered this way

**INFERENCE, medium-high confidence.** The project's own sequencing argues for
weighting verifiability above installed base *at this specific gate*:

- §4.1 says start narrow: one architecture, one synthetic family, one ECU
  family, one authorised firmware case.
- §29 says make the information pipeline measurable *before* adding reasoning,
  precisely so error can be attributed.
- §14 puts deterministic verification and hidden ground truth above expert and
  model judgement — and hidden ground truth requires a compiler for the target
  architecture.
- §49 lists "AI static analysis adds little over existing tools" as a stop
  condition. Detecting that early requires clean measurements, which requires
  the tooling to not be the confounder.

Under those constraints a target with no mainline compiler makes the project's
primary evaluation mechanism unbuildable on the real architecture. That is why
C2 — the strongest commercial candidate — is ranked third rather than first.

**This reasoning is contestable and the gate may reject it.** The counter-case
is straightforward and should be weighed: the first *authorised real firmware*
milestone is Phase 7, many gates away (§36). Choosing the commercially dominant
architecture now and accepting a proxy architecture for fixtures in the interim
is a coherent alternative strategy. It trades measurement fidelity for market
alignment. That trade is a business judgement, not a technical one, which is
why this node does not make it.

---

## What would change the ranking

Stated as falsifiable conditions, so the gate can see what evidence is worth buying:

| If this turns out to be true | Then |
|---|---|
| Ghidra SH-2A decodes SH-2E firmware cleanly, or the SH-2 FPU holes prove immaterial | **C1 rises to first.** Its community, documentation and metadata access are the best in the set; the FPU gap is its only verified structural weakness. |
| Mainline GCC can emit PowerPC VLE (U-2) | **C4 merges into C3** and the PowerPC option covers two ECU generations instead of one, materially raising its commercial relevance. |
| The gate's actual first customer brings EDC17-class ECUs | **C2 rises to first** and the toolchain gap becomes a cost to absorb rather than a reason to defer. Customer evidence outranks this matrix. |
| A HighTec-equivalent TriCore toolchain proves easy to pin reproducibly | **C2 rises**, since its main technical objection is fixture reproducibility rather than analysis capability. |
| Legally obtainable MPC5xx firmware with authorisation appears | **C3's position strengthens further**; it is currently the best-tooled candidate with the thinnest sample story. |
| Decompiler quality on 16/32-bit big-endian targets proves poor across the board | The whole ranking compresses, and the gate should reconsider whether the first product's value is decompilation-shaped at all (§49). |

---

## Candidates explicitly not recommended as first target

**C9 (C167/ST10), C10 (68HC11), C11 (EEC-IV/V), C12 (M32R)** — all four lack a
Ghidra processor language (verified). The node contract and the assignment both
forbid implementing processor support, so they are not attemptable now.

This is a sequencing judgement, not a dismissal. **C9 in particular deserves
re-examination after `GATE-STATIC-MVP`**: it has high commercial relevance and
good public Infineon documentation, and once a working pipeline exists the cost
of a SLEIGH module can be estimated against measured benefit instead of
guessed. Recording that as a future graph question is `TODO.md`'s business, not
this node's — `RESEARCH-001` owns `docs/research/**` only, so it is raised here
for the human gate to route.
