# Component: Evidence pack

**Status:** foundations built — `src/ecu_recovery/evidence/schema.py`,
`reports/`

## 1. Position in the architecture

The terminal box, and the deliverable. Both Verdict and Verification converge
here, so a pack exists whether or not verification ran.

It is drawn at the system boundary, like `Firmware image` at the top: this is
what leaves the system and reaches a person.

## 2. Responsibility

Assemble the complete chain that supports a verdict, in a form a security
engineer can check without re-running the analysis.

**The pack is the product.** A verdict without its evidence is a claim, and this
system's entire value proposition is being checkable — a security team acting on
"not reachable" needs to see why, or they are trusting a black box about
something that matters.

The pack is also where the system is honest about what it does not know.
Unresolved assumptions are a required field, not an appendix.

## 3. Inputs

- The verdict and its justification, from Verdict.
- The path (for `REACHABLE`) or the absence justification (for `NOT_REACHABLE`)
  or the blocking reason (for `INCONCLUSIVE`).
- Sink details from the CVE branch.
- Source details from Attack surface.
- CFG, data-flow, disassembly and decompilation excerpts from Binary analysis.
- Verification evidence, when verification ran.
- Sidecar explanations, **clearly marked as interpretation**.

## 4. Outputs

Nine required fields:

1. **Vulnerability / CVE** — the identifier, component, and version.
2. **Vulnerable sink** — function, address, and how it was located.
3. **Automotive source / entry point** — the entry, its protocol class, and the
   externally influenced data.
4. **Source-to-sink path** — the concrete route, or the justified absence.
5. **CFG and data-flow evidence** — the analysis facts supporting each hop.
6. **Binary / disassembly evidence** — the citable ground the analysis rests on.
7. **Verification evidence** — when performed; explicitly absent when not.
8. **Unresolved assumptions** — what the analysis could not establish.
9. **The verdict** — one of exactly three values.

**No confidence percentage.** The chain is what supports the verdict; a number
beside it would invite readers to average across findings whose missing pieces
are not comparable.

Model-authored content is **labelled as interpretation** wherever it appears, so
that no reader has to guess which parts of a pack a machine asserted and which a
model suggested.

## 5. Permitted dependencies

- **Verdict** — the finding.
- **Verification** — evidence, when it ran.
- Read access to the upstream artifacts it cites.

**It may not compute anything.** No re-deriving a path, no re-checking
reachability, no filling a gap in a field by inference. The Evidence Pack reports
what other components established. A pack that computes is a second engine with
no tests.

**The sidecar may contribute explanation only**, marked as such, and never a
field that carries a fact.

## 6. Verification and testing

- All nine fields are present, or explicitly marked absent with a reason. A pack
  with a silently missing field fails.
- Every claim in the pack cites an upstream artifact that exists.
- Unresolved assumptions are populated from upstream and never dropped.
- Model-authored content is labelled; an unlabelled model claim fails.
- No confidence percentage appears on a verdict — asserted structurally.
- A pack is produced for an unverified finding, complete on its own.
- Determinism: the same finding produces the same pack.

The `known` / `inferred` / `unknown` discipline already implemented in
`evidence/schema.py` and the report layer predates this architecture and is the
foundation this component builds on.
