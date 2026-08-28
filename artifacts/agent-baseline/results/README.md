# Baseline results

## `subject-manifest.json`

One subject per fixture for `BASELINE-AGENT-001`, frozen 2026-08-28 — before any
model was called, any transcript existed, or anything was spent.

**The rule:** the subject is the single function invoked by that fixture's
`sample_probe`. It is deterministic, and it settles the cases where a fixture
designates several classification functions: `sample_probe` invokes exactly one.

**Identity:** `manifest_id = "M-" + canonical_digest(body)`, where the body is
this file with `manifest_id` removed — a value cannot be part of the digest that
produces it. The identity covers content rather than bytes, so reindenting the
file or reordering its keys does not change it, while changing any subject does.
The expected value is recorded in `tests/agent_baseline/capture_harness.py`
rather than beside the manifest, because a file carrying its own expected digest
attests to nothing.

**Contents are deliberately bare.** Fixture ids, addresses, the selection rule,
the weighting, and the exclusion statement. No function names, semantic roles,
expected labels, claims, or answers — what a function does is what the model is
being measured on, and it arrives from `REVIEW-AGENT-BASELINE-001` after the
freeze.

## A superseded identity

An earlier identity for this manifest,
`M-c940a1336f8af121ae6ba26e4a422de67bfaf7466b573dc0f88a666d8352515f`, was
recorded during experiment-design review, outside this repository.

It could not be reproduced. 1,981 candidate serializations were tried across
every degree of freedom that does not touch the mapping — field sets, key names,
orderings, address representations, nesting layouts, and rule wordings — and
none matched. A SHA-256 match cannot occur by accident, so a search finding
nothing means the canonical body behind that value contains something not
reconstructible from what was written down.

It was therefore superseded rather than worked around, and the manifest was
frozen again with a body stated explicitly enough that anyone can recompute its
identity from this file alone.

**What was superseded is the digest, not the decision.** The subject mapping is
byte-for-byte the one that was frozen, and it was verified independently of any
digest: each address is the function that fixture's `sample_probe` invokes,
resolved from the unstripped binaries with `nm` and `otool`, outside the harness
that must never read them. All eight matched.

The supersession happened before any model call, which is the only point at
which it could have happened honestly. Afterwards it would have meant re-deriving
the provenance of transcripts that already existed.
