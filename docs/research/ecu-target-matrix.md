# ECU target matrix

**Node:** `RESEARCH-001` · **Status:** VERIFYING, awaiting human gate
**Machine-readable companion:** [`ecu-target-matrix.csv`](ecu-target-matrix.csv)
**Evidence:** [`tool-support-evidence.md`](tool-support-evidence.md) ·
**Sources:** [`sources.md`](sources.md)

This matrix **recommends candidates**. It does not select a target.
MASTER_SPEC.md §41 makes first architecture selection a human gate, and the node
contract repeats it. Nothing here should be read as a decision.

## How to read this

Every cell is one of:

- **FACT** — verified in this node against a vendor document or a command run
  on this host. Cells that say "(verified locally)" are reproducible with the
  commands in [`tool-support-evidence.md`](tool-support-evidence.md).
- **INFERENCE** — reasoned from a fact, with the reasoning stated.
- **UNKNOWN / UNMEASURED** — not established. Deliberately *not* rendered as a
  neutral-looking grade, because a missing measurement and a mediocre
  measurement are different things.

The single most important UNMEASURED cell is **decompiler quality**, which is
blank for every candidate. No decompiler output was measured in this node. See
[`decision-brief.md`](decision-brief.md) for the bounded experiment that would
fill it in.

## Column set

The contract requires fifteen columns. They appear first, in the order the
contract lists them, in both the CSV and the tables below:

```text
ECU family · manufacturer · approximate era · processor · architecture ·
endianness · firmware size range · processor documentation · Ghidra support ·
emulator availability · peripheral difficulty · sample-data availability ·
commercial relevance · estimated difficulty · notes
```

Thirteen further columns were added because the assignment named criteria the
contract's fifteen do not carry: `decompiler_quality`,
`toolchain_availability`, `interrupt_timing_complexity`,
`public_technical_references`, `legal_example_availability`,
`synthetic_fixture_difficulty`, `behavioral_emulation_difficulty`,
`expert_availability`, `symbolic_native_angr_lifter`,
`hard_disqualifier_first_target`, `evidence_confidence`, plus `candidate_id`
and `tier`.

---

## Summary table

| ID | ECU family | Processor | Arch | Ghidra | Toolchain | Emulator | Commercial | Tier |
|---|---|---|---|---|---|---|---|---|
| C1 | Subaru/Nissan/Mitsubishi SH-2E | SH7055 / SH7058 | SuperH SH-2E | Partial (FPU gap) | Good (GCC `sh`) | None for SH-2 | High (aftermarket) | 1 |
| C2 | Bosch EDC17 / MED17 | Infineon TC17xx | TriCore | **Yes** | Poor (fork only) | **Yes** (both) | **Very High** | 1 |
| C3 | Delphi / GM MPC5xx | MPC555/561/565 | PowerPC BE32 | **Yes** | **Excellent** | **Yes** (both) | High | 1 |
| C4 | MPC55xx / 56xx powertrain | MPC5554 etc. | PowerPC e200 VLE | **Yes** (VLE) | Uncertain | Partial | High | 2 |
| C5 | Saab Trionic 5 / 7 | MC68332 | 68k CPU32 | Partial (no CPU32) | **Excellent** | Partial | Low-Medium | 2 |
| C6 | MegaSquirt / FreeEMS / body | MC9S12(X) | HCS12 / X | **Yes** | Poor (GCC dropped) | None | Medium | 2 |
| C7 | Denso engine ECUs | V850 / E / ES / E2 | V850 | Partial (base only) | Good (GCC `v850`) | None | **Very High** | 2 |
| C8 | rusEFI / Speeduino / later OEM | Cortex-M, ARM7 | ARM | **Excellent** | **Excellent** | **Excellent** | Low *as legacy* | Control |
| C9 | Bosch ME7.x / EDC15 | C167 / ST10 | C166 | **None** | None | None | High | 3 |
| C10 | 1980s-90s controllers | MC68HC11 | 68HC11 | **None** | None | Simulators | Low-Medium | 3 |
| C11 | Ford EEC-IV / EEC-V | Intel 8061 / 8065 | MCS-96 relative | **None** | None | None | Low-Medium | 3 |
| C12 | Mitsubishi / Denso M32R | M32R | M32R | **None** | Fair (GCC `m32r`) | None | Medium | 3 |

**Tier 3 is disqualified as a *first* target for one reason only: no Ghidra
processor language exists.** Implementing processor support is forbidden by the
node contract and by the assignment. This is a statement about sequencing, not
about the families' worth — C9 in particular has high commercial relevance and
is a strong re-entry candidate once the pipeline is proven.

---

## The three structural findings

### 1. No candidate is strong on every axis

The criteria pull against each other, and they do so systematically:

```text
                 commercial      tool support     legal samples
                 relevance       (Ghidra+GCC)     (source available)
TriCore   C2     ##########      ####             #
V850      C7     #########       #####            #
MPC5xx    C3     #######         ##########       ##
SH-2E     C1     #######         #######          ###
HCS12     C6     #####           #####            ##########
ARM       C8     ##              ##########       ##########
```

The families with the largest installed base have the weakest tooling and the
worst sample legality. The families where legal source-matched firmware exists
are commercially marginal. **There is no candidate that is simultaneously the
commercial target and the easy target.** Any selection is a decision about
which of those two to buy first, and that is exactly why it is a human gate.

### 2. Ghidra support and toolchain support are near-independent

Four distinct combinations occur, and three of them are traps:

| | Ghidra language | Mainline GCC | Example | Consequence |
|---|---|---|---|---|
| Both | yes | yes | C3 PowerPC, C5 68k | Fixtures buildable *and* analysable |
| Analyse-only | yes | no | C2 TriCore, C6 HCS12 | Can analyse real firmware; cannot cheaply manufacture hidden-ground-truth fixtures |
| Build-only | no | yes | C12 M32R | Can build fixtures that nothing can read |
| Neither | no | no | C9 C166, C11 EEC | Blocked at both ends |

`DATA-001` and `EVAL-STATIC-001` need the *both* row. A target from the
analyse-only row means the project's evaluation ladder (MASTER_SPEC.md §14
Level 2, hidden ground truth) cannot be built on the real target architecture,
and would have to stay on a proxy architecture indefinitely.

### 3. "Ghidra supports it" is not a binary, and the gaps are load-bearing

Three candidates are listed as **Partial**, and in each case the specific
missing piece lands on the code the product most wants to read:

- **C1 SH-2E** — the SH-2 language is compiled without the FPU block, verified
  from the SLEIGH source. SH7055/SH7058 are SH-2E parts *with* an FPU. Fuel and
  ignition maths is exactly where floating point appears.
- **C5 MC68332** — no CPU32 variant, and `TBLS`/`TBLU` (table lookup and
  interpolate) are absent from the SLEIGH source. Those instructions exist on
  this part *because* it was designed for engine control table interpolation.
- **C7 V850** — only the base `V850:LE:32:default` language, against firmware
  that is generally V850E/ES/E2.

A matrix that scored these as a plain "yes" would have hidden the three risks
most likely to sink the first real-firmware attempt.

---

## Per-candidate detail

Full field values are in the CSV. This section records what the summary cannot.

### C1 — Subaru / Nissan / Mitsubishi SH-2E (SH7055 / SH7058) · Tier 1

Renesas publishes complete hardware manuals and an SH-2E software manual, and
the reverse-engineering community around these ECUs is the largest and most
open of any candidate: RomRaider is GPL, and definition corpora publish table
addresses and scaling as legally distributable metadata.

**The decisive risk is verified and cheap to test.** `SuperH:BE:32:SH-2` is
built without floating point; `SuperH:BE:32:SH-2A` has it but is a later ISA
generation. Whether SH-2A mis-decodes SH-2E code, and whether SH-2 leaves
material holes, is a one-afternoon experiment that would move this candidate up
or down decisively.

Emulation is the long-term problem: QEMU's SuperH target is SH-4, a different
generation, and Unicorn has no SuperH at all. Phase 3 on this target likely
means building an SH-2 execution model.

### C2 — Bosch EDC17 / MED17 (Infineon TriCore) · Tier 1

The strongest commercial case in the set and the only candidate with Ghidra,
Unicorn *and* QEMU support simultaneously. Ghidra ships `tc172x`, `tc176x` and
`tc29x` variants covering the common ECU parts.

Two things hold it back. First, TriCore is not in mainline GCC or binutils;
support lives in a HighTec fork. That collides with `DATA-001`'s requirement to
record compiler identity and flags reproducibly for every fixture. Second, this
is the candidate where the legal-sample position is weakest: the surrounding
tooling ecosystem is commercial and of mixed standing, and the project's own
§40 boundary forbids firmware of uncertain provenance.

Peripheral and interrupt complexity are the highest in the set.

### C3 — Delphi / GM MPC5xx · Tier 1

The best-balanced candidate on tooling: mature Ghidra PowerPC module, mainline
`powerpc-eabi` GCC, QEMU and Unicorn both support PowerPC, NXP publishes full
reference manuals, and PowerPC 32-bit is **the only architecture in the entire
candidate set with real legacy-ECU presence and a native angr lifter**.

Commercial relevance is genuine, not theoretical — MPC5xx became close to
universal in GM North America powertrain controllers.

Its weakness is the same as C2's and C7's: no legally available firmware with
matching source. And the TPU3 is a microcoded timer processor that behaves as a
second programmable CPU — the hardest part of any eventual emulation, and not
something QEMU's PowerPC support addresses.

### C4 — MPC55xx / MPC56xx (e200, VLE) · Tier 2

A successor to C3 rather than an alternative. Ghidra ships VLE languages. The
open question is whether a mainline toolchain can emit VLE, or whether fixture
production requires NXP's fork — which would convert this from a C3-like
position into a C2-like one. Recorded as U-2 in
[`uncertainties.md`](uncertainties.md); resolving it is cheap and would either
promote or demote this candidate.

### C5 — Saab Trionic 5 / 7 (MC68332) · Tier 2

The best-documented real-world reverse-engineering precedent available. A
detailed public analysis document exists, the flashing and tuning tools are open
source, and the MC68332 datasheet and CPU32 reference manual are public.

It also supplies a concrete, well-documented intake problem the product will
eventually face regardless of target: Trionic 5 stores even bytes in one chip
and odd bytes in another, so a raw dump must be de-interleaved before any
analysis means anything.

Against it: the CPU32 table-lookup gap described above, a microcoded TPU, and
low commercial relevance — Saab is defunct, so this is a classic-vehicle and
remanufacture niche rather than a repeatable commercial vertical.

### C6 — HCS12 / S12X (MegaSquirt, FreeEMS, body modules) · Tier 2

**Unique on one axis and weak on the rest.** This is the only ECU-relevant
architecture where the project can legally obtain *real engine-control firmware
together with its source code*: FreeEMS targets the S12XDP512, and MegaSquirt
MS2 firmware is open source. That is a stronger fixture than anything
`DATA-001` can synthesise — real control structure, real table lookups, real
interrupt-driven timing, ground truth by construction.

Ghidra covers HC-12, HCS-12 and HCS-12X. But GCC dropped the m68hc11/m68hc12
backends in 4.6, there is no QEMU or Unicorn target, and OEM powertrain
relevance is limited.

This candidate's value may be as a **fixture source for whichever target is
chosen**, not as the target itself. That option is put to the human gate in
[`decision-brief.md`](decision-brief.md).

### C7 — Denso V850 · Tier 2

Very high commercial relevance — Denso's production volume across Toyota,
Nissan and Honda is enormous. Mainline GCC has a `v850` backend and Renesas
publishes architecture manuals.

Ghidra ships only `V850:LE:32:default`. Real Denso ECUs are generally
V850E/ES/E2. How badly a base-variant language decodes E-series firmware is
**unquantified**, and unlike C1's FPU gap this one cannot be checked cheaply
without a legally obtained sample. Confidence in the ECU-to-part-number mapping
is also lower here than elsewhere in the matrix — specific Denso part numbers
were not verified in this node.

### C8 — ARM Cortex-M / ARM7 · Control candidate, not a target

Best-in-class on every tooling axis and effectively worthless as a *legacy ECU*
vertical. It is listed because it is the natural **calibration control**: if
the static pipeline underperforms on ARM with rusEFI or Speeduino firmware —
open source, GPL, real engine management — the fault is in the pipeline, not the
architecture. Without such a control, a poor `EVAL-STATIC-001` result on a hard
architecture is uninterpretable.

Recommending it as the commercial target would be a category error and is not
what this row does.

### C9-C12 — no Ghidra language · Tier 3

C9 (Bosch ME7/EDC15 on C167/ST10) is the painful one: high commercial
relevance, a very large European installed base, good public Infineon
documentation — and no SLEIGH language, no GCC backend, no emulator. It should
be revisited after `GATE-STATIC-MVP`, when the cost of a processor module can be
judged against a working pipeline rather than guessed at.

C10 (68HC11) has the simplest instruction set in the entire set and is still
disqualified, which shows how completely the tooling constraint dominates ISA
complexity at this stage. Note the specific shape of Ghidra's coverage: HC05,
HC08, HCS08, HC12, HCS12 and HCS12X all have languages; HC11 and HC16 do not.

C11 (Ford EEC-IV/EEC-V) is a semi-custom Intel derivative with no vendor
architecture manual. C12 (M32R) is the mirror image of C6 — a compiler with
nothing to read its output.

---

## What this matrix does not establish

- Which candidate to choose. Human gate.
- Ghidra decompiler quality on any of them. Not measured.
- Function-recovery accuracy on any of them. That is `EVAL-STATIC-001`.
- Whether any specific firmware image may lawfully be obtained. Case by case,
  under MASTER_SPEC.md §40 and the human authorisation gate.
