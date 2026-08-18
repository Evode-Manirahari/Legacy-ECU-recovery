"""Evidence and hypothesis domain contracts.

The vocabulary the project reasons about, gathered in one place so the
epistemic distinctions stay visible:

- a *mechanically observed fact* is `Evidence` with `mechanically_observed`
  set, meaning a deterministic tool produced it and a rerun should reproduce it;
- *evidence* is that observation once it is cited for or against a claim, which
  is what `EvidenceStance` records;
- a *hypothesis* is a claim under test, carrying `Certainty` (what kind of
  statement it is) and `HypothesisStatus` (what testing has done to it);
- *confidence* is the numeric weight, and *uncertainty* is the named unknown
  that would change the belief if it were resolved;
- *revision/history* is `HypothesisRevision`, one immutable moment per row;
- a *relationship* is a subject-predicate-object claim with its own evidence;
- *unknown* is first class: `Certainty.UNKNOWN`, a `status` of `UNTESTED`, and
  the `uncertainty` field all keep an admitted gap from reading as knowledge.
"""

from ..models import (
    Binary,
    Certainty,
    Evidence,
    EvidenceKind,
    EvidenceStance,
    Hypothesis,
    HypothesisRevision,
    HypothesisStatus,
    MemoryRegion,
    Relationship,
)
from .schema import migrate

__all__ = [
    "Binary",
    "Certainty",
    "Evidence",
    "EvidenceKind",
    "EvidenceStance",
    "Hypothesis",
    "HypothesisRevision",
    "HypothesisStatus",
    "MemoryRegion",
    "Relationship",
    "migrate",
]
