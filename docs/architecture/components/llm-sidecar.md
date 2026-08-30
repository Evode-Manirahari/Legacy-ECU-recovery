# Component: LLM sidecar

**Status:** built — `src/ecu_recovery/agent/`, `providers/openai/`,
`evaluation/agent/`

## 1. Position in the architecture

Beside the pipeline, not in it. In the diagram it is the only box in a different
colour, it feeds Reachability and is never fed by it, and it has **no arrow to
Verdict**. The drawing states its trust class before any sentence does.

It is not a stage. Remove it entirely and the system still produces verdicts —
fewer labels, less explanation, the same answers.

## 2. Responsibility

Interpretation, labelling, explanation, and proposing lines of investigation.

Useful work it may do: suggest that a function looks like a UDS service handler;
propose a name for an unnamed routine; explain a decompiled fragment in
engineering terms; summarise an Evidence Pack for a human reader; suggest where
an analyst might look next.

**What it may never do:** emit a verdict, influence a verdict, contribute an edge
to the program representation, or have any of its output treated as a fact.

Every sidecar output is a **suggestion**, and every suggestion must either be
confirmed against a deterministic artifact before use or carried forward marked
as unconfirmed.

## 3. Inputs

- Deterministically gathered facts: the program representation, disassembly,
  decompilation, strings, cross-references.
- The specific question being asked of it.

It receives facts. It does not gather them, and it has no tool that reaches past
the bounded surface it is given.

## 4. Outputs

- Suggested labels, interpretations, and explanations.
- Its own self-reported confidence in each claim.
- Citations to the facts it was shown.

### On the sidecar's confidence

Invariant 10 removes confidence percentages from *verdicts*. It does not remove
the sidecar's self-reported confidence in its own claims, and the distinction is
worth being explicit about rather than leaving as an apparent contradiction.

A verdict is a deterministic result about a program. Attaching a percentage to it
invites averaging and hides which specific evidence is missing. A sidecar claim
is a *suggestion*, and how sure the model is about a suggestion is genuinely
useful information for the human deciding whether to chase it. The two numbers
would mean entirely different things, which is why only one of them exists.

## 5. Permitted dependencies

- **Read access** to Binary analysis output and Intake metadata.

**Nothing depends on the sidecar for a fact.** Components may consult it for
hypotheses; none may treat its output as established.

Explicitly forbidden:

- Contributing to the program representation (see `binary-analysis.md`).
- Emitting a sink or a source without deterministic confirmation.
- Participating in a reachability decision in any form.

## 6. Verification and testing

Much of this already exists and predates the repositioning:

- **Claims are checked against gathered facts.** A claim citing something the
  tools did not return is caught (`AGENT-001`).
- **Provenance is derived, not asserted.** A transcript claiming a real model
  produced it must be backed by a content-addressed capture record that exists,
  matches its own contents, and belongs to that transcript (`PROVENANCE-001`).
- **The call record is frozen**: provider, returned model identity, response id,
  usage, truncation state — so what produced any suggestion is auditable.
- **No credential ever reaches an artifact**, enforced by an allowlist rather
  than a redactor.

And the boundary test that matters most for this architecture:

- **Removing every sidecar annotation must not change a single verdict.** Owned
  by the reachability engine's suite, listed here because it is the property
  that keeps this component a sidecar.
