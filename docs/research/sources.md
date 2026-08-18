# Source list

**Node:** `RESEARCH-001` · compiled 2026-08-17

Sources are graded by authority, because the matrix mixes vendor documentation
with community material and the difference must stay visible. MASTER_SPEC.md
§45 requires research records to carry source, claim and confidence.

| Tier | Meaning | Weight given |
|---|---|---|
| **P** | Primary — vendor documentation, or a project's own repository/docs | Load-bearing claims may rest on these alone |
| **L** | Local — reproducible on this host by a stated command | Strongest tier; independently checkable |
| **S** | Secondary — encyclopaedic or scholarly summaries of primary material | Corroboration; acceptable for historical/fitment context |
| **C** | Community — enthusiast wikis, forums, RE project documentation | Context and leads only; never the sole basis for a tier assignment |
| **V** | Vendor-commercial — tuning-tool marketing and product listings | Weakest; used only to corroborate part-number lists, never cited alone |

---

## L — Local, reproducible on this host

The strongest evidence in this node. Every claim below can be re-checked with
the commands in [`tool-support-evidence.md`](tool-support-evidence.md).

| Ref | Artifact | Claims supported |
|---|---|---|
| L-1 | Ghidra 12.1.2 PUBLIC (build 2026-06-05), `/usr/local/opt/ghidra` | Full processor module list; 209 language IDs; exact variants per module |
| L-2 | `Processors/*/data/languages/*.ldefs` | Language IDs for SuperH, tricore, PowerPC, 68000, HCS12, MCS96, V850, M16C, HCS08, MC6800 |
| L-3 | `Processors/SuperH/data/languages/superh.sinc`, `sh-2.slaspec`, `sh-2a.slaspec` | SH-2 built without the FPU block; SH-2A defines `FPU` |
| L-4 | `Processors/68000/data/languages/*.sinc`, `*.slaspec` | No CPU32 variant; `TBLS`/`TBLU`/`LPSTOP`/`BGND` absent |
| L-5 | Negative grep across all `.ldefs` | No 68HC11, 68HC16, C166/C167/ST10, H8, M32R, 8061/8065 language |

## P — Primary: tool and compiler projects

| Ref | Source | URL | Claims supported |
|---|---|---|---|
| P-1 | Unicorn Engine repository | https://github.com/unicorn-engine/unicorn | Supported architectures: ARM, AArch64, M68K, MIPS, Sparc, PowerPC, RISC-V, S390x, TriCore, x86 |
| P-2 | Unicorn project site | https://www.unicorn-engine.org/ | Architecture list corroboration |
| P-3 | QEMU, "Emulation" support table | https://www.qemu.org/docs/master/about/emulation.html | SH-4 system+user; m68k/ColdFire; PowerPC; TriCore system-only; RX; AVR |
| P-4 | QEMU, "System Emulator Targets" | https://www.qemu.org/docs/master/system/targets.html | Documented system targets; SuperH absent from that page |
| P-5 | archinfo API documentation | https://api.angr.io/projects/archinfo/en/latest/api.html | Native architecture classes; `ArchPcode` definition |
| P-6 | angr `pypcode` | https://github.com/angr/pypcode | SLEIGH bindings, built for angr, p-code symbolic execution |
| P-7 | GCC backend list | https://gcc.gnu.org/backends.html | Backends present: `sh`, `m68k`, `rs6000`, `v850`, `rx`, `m32c`, `m32r`, `h8300`, `avr`; absent: m68hc11/m68hc12, tricore, c166 |
| P-8 | GCC 4.6 release changes | https://gcc.gnu.org/gcc-4.6/changes.html | m68hc11/m68hc12 targets obsoleted in GCC 4.6 |
| P-9 | GCC installation, target-specific notes | https://gcc.gnu.org/install/specific.html | Target configuration notes; `rx`, `powerpc-*-eabi`, `avr` |
| P-10 | GNU 68HC11/68HC12 development chain | https://www.gnu.org/software/m68hc11/ | Historical HC11/HC12 GNU toolchain status |
| P-11 | Ghidra repository | https://github.com/NationalSecurityAgency/ghidra | Upstream for the locally verified processor modules |

## P — Primary: silicon vendor documentation

| Ref | Source | URL | Claims supported |
|---|---|---|---|
| P-12 | Renesas, *SH-2E SH7055S F-ZTAT Hardware Manual* | https://www.renesas.com/en/document/mah/sh-2e-sh7055s-hardware-manual | SH7055S core is SH-2E |
| P-13 | Renesas, *SH-2E SH7058 F-ZTAT Hardware Manual* | https://www.renesas.com/en/document/mah/sh-2e-sh7058-f-ztat-tm-hardware-manual | SH7058 core is SH-2E |
| P-14 | Renesas, *SH-2E SH7059 / SH7058S Hardware Manual* | https://www.renesas.com/en/document/mah/sh-2e-sh7059-f-ztattm-sh7058s-f-ztattm-hardware-manual | SH-2E family scope |
| P-15 | Renesas SH7058 product page | https://www.renesas.com/en/products/sh7058 | SH-2E core **including an FPU**; 1 MB ROM |
| P-16 | Renesas SH7055 product page | https://www.renesas.com/en/general-parts/sh7055-32-bit-microcontrollers | 512 KB ROM; SH-2 family part |
| P-17 | Renesas, *SH-2E Software Manual* REJ09B0316 | (Renesas document; a public mirror exists at evoecu.logic.net) | SH-2E instruction set incl. floating point. **Mirror, not the vendor URL — treat as P-with-caveat** |
| P-18 | Motorola/NXP, *MC68332 Technical Summary* MC68332TS/D | https://www.nxp.com/docs/en/data-sheet/MC68332TS.pdf | MC68332 CPU32 core, TPU |
| P-19 | NXP MPC5554 data sheet | https://www.nxp.com/docs/en/data-sheet/MPC5554.pdf | MPC5554 specification, eTPU/eQADC/eMIOS/FlexCAN |
| P-20 | NXP MPC5554 product page | https://www.nxp.com/products/MPC5554 | Powertrain positioning |
| P-21 | HighTec development platform | https://hightec-rt.com/products/development-platform | GCC- and LLVM-based TriCore compilers |

## P — Primary: open-source ECU firmware (legal example candidates)

| Ref | Source | URL | Claims supported |
|---|---|---|---|
| P-22 | rusEFI | https://github.com/rusefi/rusefi | GPL engine-management firmware on STM32/ARM |
| P-23 | FreeMS2 | https://github.com/fredcooke/FreeMS2 | Open-source MegaSquirt 2 firmware, HCS12 |
| P-24 | DIYEFI / FreeEMS projects | http://www.diyefi.org/projects.htm | FreeEMS targets Freescale S12X |
| P-25 | RomRaider | https://www.romraider.com/ | GPL Subaru/Nissan tuning and logging suite |
| P-26 | SubaruDefs | https://github.com/Merp/SubaruDefs | Public Subaru ECU definition corpus |
| P-27 | NissanDefinitions | https://github.com/Pytrex/NissanDefinitions | SH7055/SH7058 Nissan/Infiniti definitions, RomRaider-compatible |
| P-28 | FastECU | https://github.com/miikasyvanen/FastECU | Open tuning software; supports HC16/SH7055/SH7058 ROMs |

**Note.** P-22 through P-28 are cited as evidence that *legally usable material
exists*. No firmware was downloaded from any of them during this node.

## S — Secondary summaries

| Ref | Source | URL | Claims supported |
|---|---|---|---|
| S-1 | *Motorola MC68332: One of the First True SoCs*, IEEE | https://ieeexplore.ieee.org/document/9623409/ | MC68332 designed for engine control; microcoded TPU |
| S-2 | Wikipedia, *Freescale 683XX* | https://en.wikipedia.org/wiki/Freescale_683XX | CPU32 ≈ 68020 without bitfield instructions, plus table lookup/interpolate and low-power stop |
| S-3 | Wikipedia, *MPC5xx* | https://en.wikipedia.org/wiki/MPC5xx | Delphi used MPC561/MPC565 in GM engine controllers; MPC5xx prevalence by 2009 |
| S-4 | Wikipedia, *C166 family* | https://en.wikipedia.org/wiki/C166_family | Infineon 16-bit family, 1990; ST10 is a derivative |
| S-5 | Wikipedia, *Motorola 68HC12* | https://en.wikipedia.org/wiki/Motorola_68HC12 | MC9S12XDP512 specification; XGATE coprocessor |
| S-6 | Wikipedia, *Motorola 68HC11* | https://en.wikipedia.org/wiki/Motorola_68HC11 | 8-bit family, 1984, automotive use |
| S-7 | Wikipedia, *Intel 8061* | https://en.wikipedia.org/wiki/Intel_8061 | 8061 used in Ford EEC-IV; close relative of 8096; HSI/HSO and 10-bit ADC |
| S-8 | Wikipedia, *Intel MCS-96* | https://en.wikipedia.org/wiki/Intel_MCS-96 | MCS-96 family context |
| S-9 | Wikipedia, *Ford EEC* | https://en.wikipedia.org/wiki/Ford_EEC | EEC-V uses Intel 8065; ~192 KB flash, bank-switched space |
| S-10 | Wikipedia, *Trionic T5.5* / *T5.2* | https://en.wikipedia.org/wiki/Trionic_T5.5 | Trionic 5 built around MC68332 |
| S-11 | Wikipedia, *Qorivva* | https://en.wikipedia.org/wiki/Qorivva | MPC55xx/56xx family positioning |

## C — Community and reverse-engineering project material

Used for context and leads. **No tier assignment in the matrix rests on this
tier alone.**

| Ref | Source | URL | Claims supported |
|---|---|---|---|
| C-1 | *Analyzing Trionic 5 with T5Suite* | http://smartexpert.free.fr/saab/NG900/doc/Trionic%205.pdf · http://4saab.com/T5Suite/Trionic5.pdf | Trionic 5 splits even/odd program bytes across two chips |
| C-2 | TxSuite | https://txsuite.org/ | Open-source Trionic 5/7/8 flashing and tuning tools |
| C-3 | S4wiki, *Bosch ME7.1* | https://s4wiki.com/wiki/Bosch_ME7.1 | ME7.1 uses Infineon SAK-C167CR-class parts |
| C-4 | Nissan ECU RE wiki, *SH docs* | https://nissanecu.miraheze.org/wiki/Sh_docs | SH7055/SH7058 documentation index; REJ09B0316 reference |
| C-5 | ErikaWiki, *Infineon Tricore* | http://erika.tuxfamily.org/wiki/index.php?title=Infineon_Tricore | ERIKA uses the HighTec GCC toolchain for TriCore |
| C-6 | wrongbaud, *Tricore Basics* | https://wrongbaud.github.io/posts/hightec-tricore-linux-ghidra/ | HighTec toolchain plus Ghidra workflow in practice |
| C-7 | `binutils-tricore` | https://github.com/Cheb57/binutils-tricore | TriCore binutils exists only as a fork of GNU sources |
| C-8 | pcmhacking, LS1 PCM reverse engineering | https://pcmhacking.net/forums/viewtopic.php?t=7920 | GM PCM RE is an active community using Ghidra |

## V — Vendor-commercial (lowest weight)

Encountered during research and recorded for transparency. Used only as weak
corroboration of TriCore part-number lists in C2, never as a sole basis.

- Alientech, PCMFlash, BitBox and similar tuning-tool product and module
  listings enumerating supported TC17xx variants (TC1724 … TC1798).

**INFERENCE.** These sources have a commercial interest in claiming broad
support, and some of the surrounding ecosystem operates in legally contested
territory. They were not used for any capability claim, only to corroborate that
the TC17xx part range appears across many ECU applications — which P-21 and C-5
already support independently.

---

## Sources deliberately not used

- **No firmware image repositories.** No ROM archive, tuning-file database or
  firmware download was accessed, and none is linked as obtainable. This is
  required by MASTER_SPEC.md §40 and by the node contract.
- **No paywalled or leaked OEM service documentation.**
- **No third-party Ghidra processor modules** were downloaded or evaluated;
  see assumption A-2 in [`uncertainties.md`](uncertainties.md).
