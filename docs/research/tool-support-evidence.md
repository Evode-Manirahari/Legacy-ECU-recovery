# Tool support evidence

Machine-checkable facts underlying `ecu-target-matrix.md`. Everything in this
file is either (a) reproducible on this host with the command shown, or (b) a
direct quotation of a vendor/project document with a URL in
[`sources.md`](sources.md).

Claims are labelled:

- **FACT** — verified in this node, by the command or document cited.
- **INFERENCE** — reasoned from a FACT; the reasoning is stated so it can be
  attacked.
- **UNKNOWN** — not established here. Not to be treated as either good or bad.

Nothing in this file selects a target. See [`decision-brief.md`](decision-brief.md).

---

## 1. Ghidra processor support

**Environment.** Ghidra 12.1.2 PUBLIC, build 2026-06-05, installed via Homebrew
at `/usr/local/opt/ghidra`.

```bash
cat /usr/local/opt/ghidra/libexec/Ghidra/application.properties | head -8
ls /usr/local/opt/ghidra/libexec/Ghidra/Processors/
```

### 1.1 FACT — processor modules present

```text
6502     68000    8048     8051     8085     AARCH64  ARM      Atmel
BPF      CP1600   CR16     DATA     Dalvik   HCS08    HCS12    Hexagon
JVM      Loongarch M16C    M8C      MC6800   MCS96    MIPS     NDS32
PA-RISC  PIC      PowerPC  RISCV    Sparc    SuperH   SuperH4  TI_MSP430
Toy      V850     Xtensa   Z80      eBPF     tricore  x86
```

209 distinct language IDs across all modules.

### 1.2 FACT — language variants for candidate-relevant modules

```bash
cd /usr/local/opt/ghidra/libexec/Ghidra/Processors
for p in SuperH tricore PowerPC 68000 HCS12 MCS96 V850; do
  echo "### $p"
  find "$p" -name '*.ldefs' -exec grep -oh 'id="[^"]*"' {} \; \
    | sed 's/id="//;s/"//' | sort -u
done
```

| Module | Language IDs |
|---|---|
| SuperH | `SuperH:BE:32:SH-1`, `SuperH:BE:32:SH-2`, `SuperH:BE:32:SH-2A` |
| SuperH4 | `SuperH4:BE:32:default`, `SuperH4:LE:32:default` |
| tricore | `tricore:LE:32:default`, `:tc172x`, `:tc176x`, `:tc29x` |
| PowerPC | 21 IDs incl. `PowerPC:BE:32:default`, `:e500`, `PowerPC:BE:64:VLE-32addr`, `:VLEALT-32addr` |
| 68000 | `68000:BE:32:default`, `:MC68020`, `:MC68030`, `:Coldfire` |
| HCS12 | `HC-12:BE:16:default`, `HCS-12:BE:24:default`, `HCS-12X:BE:24:default` |
| MCS96 | `MCS96:LE:16:default` |
| V850 | `V850:LE:32:default` |
| M16C | `M16C/60:LE:16:default`, `M16C/80:LE:16:default` |
| HCS08 | `HC05:*`, `HC08:*`, `HCS08:*` |
| MC6800 | `6805:BE:16:default`, `6809:BE:16:default`, `H6309:BE:16:default` |

### 1.3 FACT — architectures with **no** language in Ghidra 12.1.2

```bash
find . -name '*.ldefs' -exec grep -ohi 'id="[^"]*"\|description="[^"]*"' {} \; \
  | grep -Ei 'hc11|68hc11|c16[67]|st10|\bh8\b|m32r|806[15]' | sort -u
# -> no output
```

Absent: **68HC11**, **68HC16**, **Infineon C166 / C167 / ST10**, **Hitachi
H8/300 / H8S**, **Renesas M32R**, **Intel 8061 / 8065**.

**INFERENCE.** For any of these, this project would have to author a SLEIGH
processor module before any analysis is possible. The RESEARCH-001 contract and
the assignment both forbid implementing processor support, and MASTER_SPEC.md
§4.2 keeps early scope narrow. Treat "no Ghidra language" as a hard
disqualifier for *first* target, not as a permanent judgement on the family.

### 1.4 FACT — SuperH SH-2 language omits the SH-2E floating-point unit

`superh.sinc` gates all floating-point instruction definitions:

```bash
grep -n '^@if\|^@endif' \
  /usr/local/opt/ghidra/libexec/Ghidra/Processors/SuperH/data/languages/superh.sinc
```

```text
32:@if defined(FPU)      51:@endif
116:@if defined(FPU)    162:@endif
1983:@if defined(FPU)   2202:@endif      <- FADD/FMUL/FMOV/FLDI0/FTRC block
2205:@if defined(FPU)   2264:@endif
```

The per-variant specs are:

```text
sh-1.slaspec   @define SH_VERSION "1"
sh-2.slaspec   @define SH_VERSION "2"                  <- FPU not defined
sh-2a.slaspec  @define SH_VERSION "2A"  @define FPU "1"
```

**FACT.** `SuperH:BE:32:SH-2` is built without the FPU block.

**FACT (vendor).** Renesas publishes the SH7055S and SH7058 hardware manuals
under the title "SH-2E ... F-ZTAT Hardware Manual"; the SH7058 is described as
having an SH-2E core *including a floating-point unit*.

**INFERENCE (high confidence).** Loading SH7055/SH7058 firmware as
`SuperH:BE:32:SH-2` will fail to decode any SH-2E FPU instruction the firmware
contains. Consequences: undecoded bytes inside otherwise-valid functions,
truncated function bodies, missing call edges, degraded decompilation — exactly
the metrics `EVAL-STATIC-001` gates on.

**INFERENCE (medium confidence).** `SuperH:BE:32:SH-2A` does define `FPU` and
would decode those instructions, but SH-2A is a later ISA generation that adds
instructions in encoding space SH-2E does not use. Substituting it may trade
missing decodes for *wrong* decodes, which is worse for an evidence-based
system. Which of the two is better on real SH-2E firmware is **UNKNOWN** and is
listed as a required experiment in [`decision-brief.md`](decision-brief.md).

### 1.5 FACT — 68000 module has no CPU32 variant or CPU32 instructions

```bash
cd /usr/local/opt/ghidra/libexec/Ghidra/Processors/68000/data/languages
grep -rn 'TBLS\|TBLU\|LPSTOP\|BGND' *.sinc *.slaspec    # -> no output
```

Variants shipped are 68000/68020/68030/68040 and ColdFire. There is no CPU32
language, and the CPU32-specific `TBLS`/`TBLU` (table lookup and interpolate),
`LPSTOP` and `BGND` instructions are not in the SLEIGH source.

**FACT (vendor/literature).** The MC68332's CPU32 core is described as a 68020
instruction set without bitfield instructions, plus table lookup and interpolate
instructions and a low-power stop mode.

**INFERENCE (high confidence).** MC68332 firmware analysed as
`68000:BE:32:MC68020` will decode the bulk of the code but not `TBLS`/`TBLU`.
This matters more than the instruction count suggests: table lookup and
interpolation is precisely the operation an ECU calibration-map analysis is
trying to recover, so the gap lands on the highest-value code.

---

## 2. Emulator availability

### 2.1 FACT — Unicorn Engine

The project's own repository title states the supported set: **ARM, AArch64,
M68K, MIPS, Sparc, PowerPC, RISC-V, S390x, TriCore, x86**.

No SuperH. No C166. No HCS12. No V850 (an RH850 pull request is described as
pending and is therefore **UNKNOWN** for planning purposes).

### 2.2 FACT — QEMU

QEMU's `about/emulation.html` support table lists, among others:

| Guest | System | User |
|---|---|---|
| SH-4 ("32 bit RISC embedded CPU developed by Hitachi") | Yes | Yes |
| m68k ("Motorola 68000 variants and ColdFire") | Yes | Yes |
| PowerPC / ppc64 | Yes | Yes |
| TriCore ("32 bit RISC/uController/DSP developed by Infineon") | Yes | No |
| RX ("32 bit micro controller developed by Renesas") | Yes | No |
| AVR | Yes | No |

**FACT.** QEMU's SuperH support is **SH-4**, not SH-2.

**INFERENCE (high confidence).** SH-4 is a later, different SuperH generation.
QEMU's SH-4 target is not a usable stand-in for an SH-2E ECU: the peripheral
set, memory map and privileged model differ. For SH7055/SH7058 the project
would face writing its own SH-2 execution model at the Phase-3 emulation gate.

### 2.3 INFERENCE — emulator support is a *later*-gate criterion

MASTER_SPEC.md §32 puts emulation behind `GATE-AGENT-MVP`, which is behind
`GATE-STATIC-MVP`. Emulator availability should therefore be weighted as
*future risk*, not as a present blocker. It is scored separately in the matrix
for exactly that reason.

---

## 3. Compiler / toolchain availability

Relevant because `DATA-001` and `EVAL-STATIC-001` need **known-source, hidden
ground truth** fixtures. Without a compiler for the chosen architecture the
project cannot manufacture the fixtures its own evaluation ladder depends on.

### 3.1 FACT — GCC backends (from the GCC project's backend list)

Present: `sh`, `m68k`, `rs6000` (PowerPC), `v850`, `rx`, `m32c`, `m32r`,
`h8300`, `avr`, `arm`, `aarch64`, and others.

Absent: **m68hc11 / m68hc12**, **tricore**, **c166**.

### 3.2 FACT — 68HC11/68HC12 removed from GCC

The `m68hc11-*-*`, `m6811-*-*`, `m68hc12-*-*`, `m6812-*-*` targets were
obsoleted in **GCC 4.6**. There is no modern mainline GCC for HC11/HC12/HCS12.

### 3.3 FACT — TriCore is not in mainline GCC or binutils

TriCore GCC/binutils support exists as a HighTec-maintained fork (sources
published for GPL compliance), not as an official GNU branch.

**INFERENCE (medium-high).** A TriCore fixture pipeline is possible but adds a
third-party toolchain dependency with its own licensing, platform and
reproducibility burden — which cuts against MASTER_SPEC.md §9 ("reproducible
Python engineering infrastructure") and against the `DATA-001` requirement to
record compiler identity and flags for every fixture.

### 3.4 UNKNOWN — PowerPC VLE in mainline GCC

Ghidra ships VLE languages (§1.2). Whether **mainline** GCC can emit PowerPC
VLE (as opposed to NXP's S32DS fork) was not verified in this node. This is the
one open toolchain question that separates MPC5xx (classic PowerPC, no VLE)
from MPC55xx/56xx (e200 core, VLE-encoded). Recorded in
[`uncertainties.md`](uncertainties.md).

---

## 4. Symbolic-analysis tooling coverage — record only

Recorded because the assignment asks whether likely symbolic tooling supports
each candidate, since that may affect future feasibility.

`SYMBOLIC-001` is **candidate-only**. It is deliberately absent from
`ecu-project.graph.yaml`, it is not scheduled by this node, no symbolic
execution was implemented, and angr was not installed. This section is
literature review, nothing more.

### 4.1 FACT — architectures with a native angr/VEX lifter

`archinfo` defines: `ArchX86`, `ArchAMD64`, `ArchARM`, `ArchARMEL`,
`ArchARMHF`, `ArchARMCortexM`, `ArchAArch64`, `ArchMIPS32`, `ArchMIPS64`,
`ArchPPC32`, `ArchPPC64`, `ArchRISCV64`, `ArchS390X`, `ArchSoot`, and
`ArchPcode`.

SuperH, TriCore, C166, m68k and V850 do **not** appear as native classes.

### 4.2 FACT — `ArchPcode` / pypcode fallback

`ArchPcode` is documented as "archinfo interface to pypcode architectures".
`pypcode` provides Python bindings to Ghidra's SLEIGH library and exists
primarily for use with angr, which provides analyses and symbolic execution of
p-code.

**INFERENCE (medium).** Any architecture with a Ghidra SLEIGH language is in
principle reachable by angr through p-code, so Ghidra support and *potential*
symbolic support largely coincide. But the p-code path is materially less
mature than the native VEX lifters — known rough edges include address-space
naming assumptions in emulation — so "reachable" is not "supported".

**INFERENCE (medium-high), decision-relevant.** Among architectures with real
legacy-ECU presence, **PowerPC 32-bit is the only one with a native angr
lifter.** If symbolic analysis ever becomes a required evidence source rather
than an optional branch, that asymmetry is large. It is recorded as a
tiebreaker in [`decision-brief.md`](decision-brief.md), not as a primary
criterion — weighting a candidate node's convenience above the product's
commercial target would invert the project's priorities.

---

## 5. Legally usable examples

MASTER_SPEC.md §40 and the node contract both forbid acquiring firmware of
uncertain provenance. **No firmware was downloaded during this node.**

### 5.1 FACT — open-source ECU firmware with real automotive semantics

| Project | Licence | Target processor | Relevance |
|---|---|---|---|
| MegaSquirt MS2 / FreeMS2 | Open source | Freescale HCS12 | Real fuel/ignition control, full source |
| FreeEMS | Open source | Freescale S12XDP512 | Real engine management, full source |
| rusEFI | GPL | STM32 (ARM Cortex-M) | Real engine management, full source |
| Speeduino | Open source | ATmega2560 / Teensy (ARM) | Real engine management, full source |

**INFERENCE (high).** These are the only candidates where the project can
legally obtain *engine-control firmware with matching source code*. That is a
much stronger fixture than a synthetic benchmark: it provides real automotive
control structure, real table lookups and real interrupt-driven timing, with
ground truth available by construction. Note the architectures involved are
HCS12/S12X and ARM — **not** the high-commercial-relevance families.

### 5.2 FACT — public definition/metadata corpora (not firmware)

RomRaider is GPL, and community definition repositories (`SubaruDefs`,
`NissanDefinitions`) publish table locations and scaling for SH7055/SH7058
ECUs in RomRaider-compatible XML.

**INFERENCE (high).** Definitions are legally distributable metadata and are a
legitimate *evaluation oracle*: they assert "a table of this shape lives at this
address". They are not firmware and do not authorise obtaining firmware. Their
provenance is community-contributed, so they are Level-3-ish evidence
(expert-asserted), not hidden ground truth in the MASTER_SPEC.md §14 Level-2
sense.

### 5.3 FACT — public reverse-engineering literature

Saab Trionic 5 has an unusually detailed public analysis document (T5Suite
documentation), and open-source flashing/tuning tools exist for Trionic 5/7/8.
The same document records that Trionic 5 splits program memory across two
chips, even bytes in one and odd bytes in the other.

**INFERENCE (high).** That storage layout is a concrete, well-documented
example of a real-firmware intake problem the product will face (an image that
must be de-interleaved before any analysis is meaningful) and would be a good
early test of the binary-intake layer regardless of which target is chosen.

---

## 6. What was *not* measured here

- **Ghidra decompiler output quality per architecture.** Presence of a `.cspec`
  means the decompiler will run; it says nothing about whether the output is
  useful. Not measured. This is the single largest gap in the matrix and the
  basis for the calibration experiment proposed in
  [`decision-brief.md`](decision-brief.md).
- **Function-recovery accuracy** on any candidate architecture. `EVAL-STATIC-001`
  exists to measure this and has not run.
- **Real firmware of any kind.** None obtained, by contract.
