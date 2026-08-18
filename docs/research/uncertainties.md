# Uncertainties, assumptions and blockers

**Node:** `RESEARCH-001`

MASTER_SPEC.md §30 requires an agent to distinguish KNOWN, INFERRED and
UNKNOWN. This file is the UNKNOWN and assumption register for the target
matrix. It exists so that no downstream reader mistakes a gap for a finding.

Nothing here is presented as settled. Where an uncertainty is cheap to resolve,
the resolution method is stated.

---

## Open uncertainties

### U-1 — Ghidra decompiler quality per architecture · HIGH impact

**Unknown.** No decompiler output was produced or assessed for any candidate.

**Why it matters.** MASTER_SPEC.md §3.1 lists "C-like pseudocode where useful"
as a first-product output, and §24 requires `decompile_function`. If the
decompiler produces unusable output on the selected architecture, a core
product claim weakens on that target specifically.

**What is known.** Every candidate module with a language also ships a compiler
spec, so the decompiler will run. That is a floor, not a quality signal.

**Resolution.** The calibration experiment in
[`decision-brief.md`](decision-brief.md) §4. Cheap. Requires cross-compilers,
which are `DATA-001` territory, not this node's.

### U-2 — Mainline GCC PowerPC VLE emission · MEDIUM impact

**Unknown.** Whether mainline GCC can emit PowerPC VLE, or whether VLE fixture
production requires NXP's S32DS fork.

**Why it matters.** It decides whether C4 (MPC55xx/56xx) inherits C3's
excellent toolchain position or falls into C2's fork-dependent position. That
in turn decides whether the PowerPC option covers one ECU generation or two,
which materially changes its commercial relevance.

**What is known.** Ghidra ships VLE languages (verified). Binutils VLE support
is widely reported. GCC's own backend list includes `rs6000` but says nothing
about VLE specifically.

**Resolution.** Inspect GCC documentation or attempt a `powerpc-eabivle`
toolchain build. Cheap.

### U-3 — SH-2A as a substitute for SH-2E · HIGH impact on C1

**Unknown.** Whether `SuperH:BE:32:SH-2A` decodes SH-2E firmware correctly, or
whether its later-generation instructions cause **mis**-decodes.

**Why it matters.** C1's only verified structural weakness is that
`SuperH:BE:32:SH-2` omits the FPU. If SH-2A is a safe substitute, that weakness
largely disappears and C1's ranking rises. If SH-2A silently mis-decodes,
substituting it is worse than the original gap, because wrong instructions
produce confident wrong evidence rather than visible holes.

**Resolution.** Compile an SH-2E fixture using floating point with `sh-elf-gcc`,
import under both languages, compare. Cheap. Needs no real firmware.

### U-4 — V850 base-language coverage of V850E/ES/E2 firmware · HIGH impact on C7

**Unknown.** How badly `V850:LE:32:default` decodes V850E-series code.

**Why it matters.** C7 has arguably the highest commercial relevance of any
candidate (Denso volume), and this is the only thing blocking it from the
shortlist.

**Resolution.** Harder than U-3: mainline GCC has a `v850` backend, so a
synthetic test is possible, but confirming behaviour on *real* Denso firmware
would need a legally obtained sample, which this node may not seek. Partially
resolvable only.

### U-5 — ECU-to-part-number mappings · MEDIUM impact

**Unknown / low confidence.** Specific ECU model to silicon part-number
mappings were sourced from secondary material (community wikis, tuning-tool
documentation, encyclopaedic summaries) rather than from OEM service
documentation, which is generally not public.

**Confidence by candidate:**

| Candidate | Confidence | Basis |
|---|---|---|
| C2 TriCore in EDC17/MED17 | High | Consistent across many independent sources |
| C5 MC68332 in Trionic 5 | High | Multiple sources incl. a detailed public analysis document |
| C9 C167 in ME7.1/EDC15 | High | Multiple independent sources naming SAK-C167CR |
| C3 MPC561/565 in Delphi/GM | Medium-High | Reported in encyclopaedic summary of MPC5xx |
| C1 SH7055/SH7058 in Subaru/Nissan | Medium-High | Renesas confirms the parts; ECU fitment is community-sourced |
| C11 Intel 8061/8065 in EEC-IV/V | Medium-High | Consistent secondary sources |
| C7 V850 in Denso ECUs | **Medium** | Family-level only; no specific part numbers verified |
| C10 68HC11 in specific ECUs | **Low** | Family-level plausibility only; no specific model verified |
| C12 M32R in Mitsubishi/Denso | **Medium-Low** | Family-level only |

**INFERENCE.** This does not undermine the matrix's conclusions, because the
tier assignments are driven by *architecture-level* tool support (verified
locally) rather than by which ECU contains which chip. A wrong fitment claim
would misattribute an ECU family, not change whether Ghidra supports the
architecture.

### U-6 — Firmware size ranges · LOW impact

**Partially known.** On-chip flash sizes come from vendor data (SH7055 512 KB,
SH7058 1 MB, TC1797 4 MB, MPC5xx 448 KB–1 MB). Ranges for external-flash
designs are approximate and community-sourced.

**Why it matters little.** Size affects analysis runtime and memory budgets,
not target viability. Recorded for completeness.

### U-7 — Real-firmware decode behaviour · HIGH impact, deliberately unresolved

**Unknown, by contract.** No candidate's language was tested against real ECU
firmware, because no firmware was obtained.

**This is a correct outcome, not a shortfall.** MASTER_SPEC.md §40 and the node
contract forbid it. Resolution belongs to Phase 7 under the authorisation gate.

### U-8 — pypcode/angr maturity on candidate architectures · LOW impact

**Unknown.** How well the `ArchPcode` path actually performs on SuperH,
TriCore, m68k or V850.

**Why it matters little now.** `SYMBOLIC-001` is candidate-only and unscheduled.
Recorded because the assignment asked for symbolic coverage per architecture,
and because it would matter if that node were ever scheduled.

---

## Assumptions

Stated explicitly so they can be attacked rather than inherited silently.

**A-1.** The locally installed **Ghidra 12.1.2** is representative of the
version the project will use. If `GHIDRA-001` pins a different version, the
processor and language findings must be re-verified. The commands to do so are
in [`tool-support-evidence.md`](tool-support-evidence.md).

**A-2.** Processor support means **base-distribution** support. Community
SLEIGH modules exist for several unsupported architectures (C166 and H8 among
them) and were not evaluated, because adopting a third-party processor module
is an architecture decision outside this node's authority. This assumption is
what places C9 in Tier 3; relaxing it would move C9 up.

**A-3.** The first target should be **one** architecture, per §4.1. The matrix
does not evaluate multi-architecture strategies. The C6-as-fixture-source and
C8-as-control proposals are the closest this node comes to suggesting one, and
both are put to the gate rather than assumed.

**A-4.** "Commercial relevance" is judged by **installed base and remaining
service life**, not by revenue evidence. No customer discovery has occurred
(§43). Real customer evidence should override this column entirely.

**A-5.** Emulator availability is weighted as **future risk**, not as a present
blocker, because §32 puts emulation behind two gates. A gate that expects to
reach emulation sooner should reweight D7 upward.

**A-6.** Decompiler quality is assumed to **correlate** with how heavily a
Ghidra processor module is exercised in general use. This is the weakest
assumption in the document, it is the reason U-1 is ranked highest, and no
candidate's ranking rests on it alone.

---

## Blockers

**None blocking completion of `RESEARCH-001`.** The node's deliverables are
complete and its verification is human review.

Blockers that apply to **downstream** work, recorded for the gate:

**B-1 — Human gate is required before any architecture-dependent work.**
`GHIDRA-001` targeting and `DATA-001` fixture architecture both depend on a
decision this node may not make. Neither is blocked *today* — `DATA-001` can
proceed on the existing x86-64 proxy — but both will produce
architecture-specific output that a later decision could invalidate.

**B-2 — No authorised real firmware exists for any candidate.** Phase 7 cannot
begin regardless of which architecture is chosen. This is expected at this
stage, not a failure.

**B-3 — Four candidate families are unattemptable without processor-module
work** (C9, C10, C11, C12). Out of scope by contract. If the gate wants any of
them, that is new graph work requiring its own node and its own decision.

**B-4 — `ruff` and `mypy` were absent from the environment** when this node
began; `uv run ruff check .` failed with "Failed to spawn: ruff". Resolved
non-destructively with `uv sync --extra dev`, which installed the declared
`[project.optional-dependencies] dev` group. No project file was modified. Noted
because any worker who runs the regression commands on a fresh checkout will
hit the same thing.
