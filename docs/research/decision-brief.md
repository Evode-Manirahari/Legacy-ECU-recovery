# Architecture decision brief — for the human gate

**Node:** `RESEARCH-001` · **Verification type:** human · **Retry budget:** 2
**Agent status:** VERIFYING. An agent must not self-approve this node.

This file states what the human decision actually is, what evidence exists,
what evidence is missing, and what it would cost to get it. It does not choose.

---

## 1. The decision

> Which processor/ECU family becomes the project's **first supported
> architecture**, per MASTER_SPEC.md §4.1 and §22?

Downstream consequences, so the gate can see the blast radius:

- `DATA-001` — whether synthetic fixtures stay on the x86-64 proxy or move to
  the selected architecture, and which cross-compiler enters the build.
- `GHIDRA-001` — which Ghidra language ID the analysis path targets and which
  processor-specific warnings it must surface.
- `EVAL-STATIC-001` — whether hidden-ground-truth fixtures can exist on the
  real target architecture at all.
- Phase 3 emulation — whether an execution engine exists or must be written.
- Phase 7 — which authorised real firmware is even relevant to seek.

The decision is **reversible but expensive**: it does not invalidate the graph,
but it does invalidate fixture builds and any architecture-specific analysis
tuning.

## 2. What this node established

**FACT, verified locally on Ghidra 12.1.2:**

- Which processor languages exist, and their exact variants.
- Four candidate architectures have **no** language at all: C166/C167/ST10,
  68HC11 (and 68HC16), H8, M32R, and the Ford 8061/8065 derivatives.
- `SuperH:BE:32:SH-2` is compiled **without** the FPU instruction block, while
  SH7055/SH7058 are SH-2E parts that have an FPU.
- The 68000 module has **no CPU32 variant** and no `TBLS`/`TBLU`/`LPSTOP`/`BGND`.
- Ghidra ships PowerPC VLE languages, TriCore `tc172x`/`tc176x`/`tc29x`, and
  HCS12/HCS12X.

**FACT, from vendor and project documentation:**

- Unicorn supports TriCore, PowerPC, M68K, ARM — not SuperH, C166, HCS12, V850.
- QEMU supports SH-**4** (not SH-2), m68k/ColdFire, PowerPC, TriCore
  (system-only), RX, AVR.
- Mainline GCC has `sh`, `m68k`, `rs6000`, `v850`, `m32r`, `h8300`, `rx`, `avr`
  — and has **no** `tricore`, **no** `c166`, and dropped `m68hc11`/`m68hc12` in
  GCC 4.6.
- TriCore GCC/binutils exist only as a HighTec fork.
- angr's native lifters cover PPC32/PPC64, ARM/Cortex-M, x86/AMD64, MIPS,
  RISC-V, S390X — and reach anything else only through the less mature
  `ArchPcode`/pypcode path.
- Real, legally usable, source-matched engine-management firmware exists for
  **HCS12/S12X** (FreeEMS, MegaSquirt) and **ARM** (rusEFI, Speeduino), and for
  no other candidate.

## 3. What this node did **not** establish

**The largest gap: no decompiler output was measured for any candidate.** The
matrix's `decompiler_quality` column is UNMEASURED across the board. Presence
of a SLEIGH language and a compiler spec guarantees the decompiler will *run*;
it says nothing about whether the output helps a human or an agent.

Also unmeasured: function-recovery accuracy (that is `EVAL-STATIC-001`'s job),
and any property of real firmware, since none was obtained.

## 4. The experiment that would resolve most of the uncertainty

**RECOMMENDATION.** Before deciding, buy the missing measurement. It is cheap
and bounded, and it converts the three largest open risks from opinion into
data.

**Proposed calibration experiment — not scheduled by this node.**

```text
For each of: PowerPC BE32, SuperH SH-2, SuperH SH-2A, m68k MC68020, ARM Cortex-M

  1. cross-compile the SAME small C fixture set
     (threshold controller, 1-D table lookup, 2-D table lookup,
      state machine, timer counter)
  2. strip symbols
  3. import through the existing Ghidra path
  4. measure: function recall/precision, call-edge recall,
     decompiler output usability, undecoded-byte count
```

What each comparison answers:

| Comparison | Resolves |
|---|---|
| SH-2 vs SH-2A on an FPU-using fixture | Whether C1's verified FPU gap is fatal, tolerable, or fixable by variant substitution — the single highest-value unknown in the matrix |
| m68k with a `TBLS`/`TBLU` fixture | How badly C5 degrades on table-interpolation code |
| PowerPC vs ARM | Whether C3's decompiler output is close to the known-good baseline |
| ARM as control | What "good" looks like at all; without it every other number is uninterpretable |

**Ownership note.** This experiment would create cross-compiler dependencies
and fixture builds, which belong to `DATA-001` (`samples/**`, `scripts/**`) and
`GHIDRA-001` (`src/ecu_recovery/analysis/**`). `RESEARCH-001` owns
`docs/research/**` only and therefore **proposes** it rather than performing
it. Routing it is the gate's call.

**Sequencing caution.** `DATA-001` and `EVIDENCE-001` are currently READY and
may already be running in parallel worktrees. If the gate wants this
experiment, it should be routed deliberately rather than bolted onto a node
already in flight.

## 5. Decision factors, weighted for the gate

| # | Factor | Why it matters now | Discriminates between |
|---|---|---|---|
| D1 | **Ghidra language exists** | Hard gate — no analysis without it, and authoring one is out of scope | Eliminates C9, C10, C11, C12 |
| D2 | **Mainline compiler exists** | `EVAL-STATIC-001` needs hidden ground truth on the target architecture | Separates C3/C5/C1/C7 from C2/C6 |
| D3 | **Decode completeness on real parts** | Partial language support silently corrupts every downstream metric | C1 (FPU), C5 (CPU32), C7 (V850E) |
| D4 | **Legal source-matched firmware** | §40 boundary; also the strongest possible fixture | Only C6 and C8 |
| D5 | **Commercial relevance** | §3 first customer, §49 stop conditions | Favours C2, C7, C3 |
| D6 | **Expert availability** | §14 Level 3 review; §43 pilot needs a specialist | Favours C1 strongly |
| D7 | **Emulator exists** | Phase 3 risk, not a present blocker | Favours C2, C3; penalises C1 |
| D8 | **Peripheral / interrupt complexity** | Dominates eventual rehosting cost | Penalises C2, C7; C3's TPU3 and C5's TPU are real costs |
| D9 | **Symbolic tooling reach** | Optional future branch only — see §7 | Mild tiebreak to C3 |

**INFERENCE.** D1 and D2 are gates; the rest are weights. Applying D1 and D2
strictly leaves C3, C5, C1 and C7. Adding D5 promotes C3 and C1 over C5.
That is how the shortlist in [`ranked-candidates.md`](ranked-candidates.md) was
derived, and the gate is free to reweight — particularly D5 against D2, which
is the real fork in the road.

## 6. The question the gate should answer first

**RECOMMENDATION.** One prior question determines everything else, and it is
not a technical question:

> Is the first architecture chosen to **prove the method**, or to **serve the
> first customer**?

- **Prove the method** → C3 (MPC5xx). Mainline toolchain, mature Ghidra
  module, both emulators, native angr lifter, real GM/Delphi installed base.
  Accept a thin legal-sample story for now.
- **Serve the first customer** → C2 (TriCore) or C1 (SH-2E), depending on
  whether the customer is a diesel/European ECU specialist or a
  Japanese-performance specialist. Accept toolchain or decode risk.

MASTER_SPEC.md §43 says to find a specialist and an authorised firmware problem
before locking the product shape. **If a candidate first customer already
exists, their ECUs should outrank this entire matrix.** This research cannot see
that, and says so rather than pretending the technical criteria settle it.

## 7. Explicit scope statements

- **SYMBOLIC-001 remains candidate-only.** It is deliberately absent from
  `ecu-project.graph.yaml`. This node did not schedule it, did not install angr,
  and did not implement symbolic execution. Symbolic-tooling coverage was
  *recorded* per architecture — as the assignment asked — because it may affect
  future feasibility, and for no other purpose.
- **No processor support was implemented**, and none is proposed as part of the
  first target.
- **No firmware was downloaded.** No image of uncertain authorisation or
  provenance was obtained, requested, or linked as obtainable.
- **`ecu-project.graph.yaml` was not modified.** `RESEARCH-001` remains
  `PENDING` in the graph and only the human gate may change that.
- **No downstream node was started**, and no files outside `docs/research/**`
  were created or modified.
