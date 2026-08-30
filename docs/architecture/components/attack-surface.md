# Component: Attack surface → automotive sources

**Status:** not built

## 1. Position in the architecture

**Downstream of Binary analysis**, not parallel to it. This is the shape of the
diagram and it is not incidental: an attack surface cannot be identified without
the program representation that shows the handlers and what they reach.

It produces the other half of what the Reachability engine joins.

## 2. Responsibility

Identify the points in the program where **externally influenced data enters** —
the automotive sources: CAN frame handlers, UDS service dispatch, DoIP endpoints,
OTA update paths.

"Externally influenced" is the operative test, and it is narrower than "input".
A value read from an internal calibration table is an input. A value an attacker
can place on a bus is a source. Only the second one starts a path this system
cares about.

**This component is the only source of automotive entry points in the system.**

## 3. Inputs

- The program representation from Binary analysis: functions, CFG, call graph,
  cross-references, data flow.
- Intake metadata, for addressing.

## 4. Outputs

For each identified source:

- The entry point: function and address.
- Its protocol class — CAN, UDS, DoIP, OTA, or another named surface.
- The specific data that is externally influenced at that point, since a path
  matters only if attacker-controlled data flows along it.
- The evidence that identified it — matched dispatch structure, handler
  signature, register or peripheral access, referenced constants.
- **Candidate sources that could not be confirmed**, reported explicitly. An
  unconfirmed source is a reason for `INCONCLUSIVE`, never a reason for silence.

## 5. Permitted dependencies

- **Binary analysis** — for the program representation.
- **Intake** — for image metadata.
- **LLM sidecar** — *advisory only*. Recognising that a dispatch table looks like
  UDS service routing is exactly the kind of pattern a model is useful for. Every
  such suggestion must be confirmed against a deterministic artifact — the
  dispatch structure, the constants, the peripheral access — before it is emitted
  as a source. A suggestion that cannot be confirmed becomes an unconfirmed
  candidate, not a source.

Not permitted: the CVE branch, Reachability, Verdict.

## 6. Verification and testing

- Against fixtures with known entry points: recall and precision of source
  identification, measured per protocol class.
- A source emitted with no deterministic confirming evidence fails, including
  when the sidecar suggested it.
- An unconfirmed candidate is never promoted to a confirmed source, and a test
  asserts it survives into the output as a candidate.
- **Missed-source recall is tracked as a benchmark metric,** because a missed
  source is a direct route to a false-unreachable: no source, no path, and the
  engine concludes there is nothing to find.
- Determinism: identical representation in, identical sources out.
