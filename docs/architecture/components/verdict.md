# Component: Verdict

**Status:** not built

## 1. Position in the architecture

Directly below the Reachability engine. It has two outgoing arrows: one to the
Evidence Pack, and one to Verification — the side branch, taken only when the
verdict is `INCONCLUSIVE` or a customer asks.

It is not a second decision. The engine decides; this component *represents* the
decision, carries its justification, and routes it.

## 2. Responsibility

Express the reachability result in exactly three buckets, carry the justification
that supports it, and route inconclusive findings toward optional verification.

### The three buckets

| Verdict | Means | Requires |
|---|---|---|
| `REACHABLE` | A path exists from an automotive source to the vulnerable sink | The concrete path, with per-hop evidence |
| `NOT_REACHABLE` | No path exists | A justification for the *absence*: what was searched, and why the search was complete enough to conclude |
| `INCONCLUSIVE` | The analysis could not decide | A specific statement of what blocked it |

There is no fourth bucket. There is no "likely", no "probably not", and no
percentage — see invariant 10.

### The asymmetry

`NOT_REACHABLE` carries a heavier burden of proof than the other two, on purpose.

A wrong `REACHABLE` costs engineering time and gets discovered. An
`INCONCLUSIVE` is honest about work remaining. A wrong `NOT_REACHABLE` tells a
security team a live defect is safe to deprioritise, and nothing downstream is
looking for it — the cost is paid entirely by whoever trusted the answer.

So `NOT_REACHABLE` may only be emitted when the absence of a path is
*justified*: the regions searched were complete, and no reported representation
gap sits between the source and the sink. If a gap does, the verdict is
`INCONCLUSIVE`. **Preferring `INCONCLUSIVE` is the designed behaviour, not a
degraded mode.**

## 3. Inputs

- The reachability result for a (source, sink) pair.
- Its supporting path or absence justification.
- Unresolved assumptions.
- Optionally, a customer request for verification regardless of bucket.

## 4. Outputs

- The verdict, as one of exactly three values.
- Its justification.
- A routing decision: to Verification, or straight to the Evidence Pack.
- Unresolved assumptions, carried forward intact.

## 5. Permitted dependencies

- **Reachability engine** — the result it represents.

Not permitted: Binary analysis, Attack surface, the CVE branch — reaching back
into those would mean deciding something the engine did not.

**Not permitted: the LLM sidecar.** In the diagram there is no arrow from the
sidecar to this box, and that absence is the architecture's sharpest line. A
sidecar able to influence the wording, the bucket, or the routing of a verdict is
a sidecar that decides.

## 6. Verification and testing

- The verdict type admits exactly three values; a fourth fails to construct.
- No confidence field exists on a verdict — asserted structurally, so it cannot
  be added without a test failing.
- `NOT_REACHABLE` cannot be constructed without an absence justification.
- A representation gap between source and sink yields `INCONCLUSIVE`; a fixture
  proves it never yields `NOT_REACHABLE`.
- Routing: `INCONCLUSIVE` offers verification, other buckets do not, and a
  customer request routes any bucket.
- Both routes reach the Evidence Pack.
