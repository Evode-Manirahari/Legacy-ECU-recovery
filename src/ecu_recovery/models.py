"""Domain models shared across intake, storage, and reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Certainty(StrEnum):
    """How strongly an investigation statement is supported."""

    KNOWN = "known"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class HypothesisStatus(StrEnum):
    """Where a belief sits in the observe-test-update cycle.

    Orthogonal to `Certainty`. `Certainty` answers "what kind of statement is
    this" (mechanically known, inferred, or admittedly unknown). `status`
    answers "what has testing done to it so far". A claim can be INFERRED and
    SUPPORTED at the same time; collapsing the two axes would lose the
    distinction between a fact and a well-tested guess.

    No transition is forbidden. A CONFIRMED belief may later be REJECTED,
    because being able to overturn a confirmed belief is the point of the
    model. The revision chain, not a transition table, is what records how a
    belief moved.
    """

    UNTESTED = "untested"
    SUPPORTED = "supported"
    WEAKENED = "weakened"
    REJECTED = "rejected"
    CONFIRMED = "confirmed"


class EvidenceKind(StrEnum):
    """The observable classes named in MASTER_SPEC section 5."""

    DECOMPILATION = "decompilation"
    DISASSEMBLY = "disassembly"
    CALL_GRAPH = "call_graph"
    CROSS_REFERENCE = "cross_reference"
    MEMORY_ACCESS = "memory_access"
    CONSTANT = "constant"
    TABLE_ACCESS = "table_access"
    EXECUTION_TRACE = "execution_trace"
    EXPERIMENT_RESULT = "experiment_result"
    EXPERT_REVIEW = "expert_review"
    STATIC_PROPERTY = "static_property"


class EvidenceStance(StrEnum):
    """How one piece of evidence bears on one claim.

    MASTER_SPEC section 39 reports supporting and contradicting evidence
    separately, so the stance belongs on the link rather than on the evidence:
    the same observation can support one hypothesis and contradict another.
    """

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXT = "context"


@dataclass(frozen=True)
class RepeatedRegion:
    first_offset: int
    second_offset: int
    length: int


@dataclass(frozen=True)
class BinaryProfile:
    path: str
    filename: str
    size: int
    sha256: str
    sha1: str
    md5: str
    entropy: float
    byte_order: str | None
    processor: str | None
    fill_bytes: dict[int, int] = field(default_factory=dict)
    repeated_regions: tuple[RepeatedRegion, ...] = ()


@dataclass(frozen=True)
class FunctionRecord:
    address: int
    name: str
    size: int | None = None
    decompilation: str | None = None


@dataclass(frozen=True)
class Hypothesis:
    subject: str
    claim: str
    certainty: Certainty
    confidence: float
    evidence: tuple[str, ...] = ()
    uncertainty: str | None = None
    # Appended last, and defaulted, so every existing positional construction
    # keeps its meaning. A freshly stated belief has not been tested yet.
    status: HypothesisStatus = HypothesisStatus.UNTESTED

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if self.certainty is Certainty.KNOWN and self.confidence < 1.0:
            raise ValueError("known claims must have confidence 1.0")


@dataclass(frozen=True)
class Binary:
    """A persisted firmware image. Identity is its SHA-256."""

    id: int
    sha256: str
    filename: str
    source_path: str
    size: int
    entropy: float
    processor: str | None
    byte_order: str | None


@dataclass(frozen=True)
class MemoryRegion:
    """A persisted address range belonging to one binary.

    Mirrors `analysis.models.MemoryRegion`, which is the engine-facing record
    produced during a run. This is the stored evidence-model entity. They are
    kept separate so a change to an analysis engine's output cannot silently
    redefine what the evidence database means.
    """

    name: str
    start_address: int
    end_address: int
    readable: bool = True
    writable: bool = False
    executable: bool = False
    initialized: bool = True

    def __post_init__(self) -> None:
        if self.end_address < self.start_address:
            raise ValueError("end_address must not precede start_address")

    @property
    def size(self) -> int:
        """Inclusive of both endpoints, matching the analysis-side record."""
        return self.end_address - self.start_address + 1


@dataclass(frozen=True)
class Evidence:
    """One recorded observation.

    `mechanically_observed` is the fact/interpretation line the project depends
    on: True means a deterministic tool produced it and a rerun should
    reproduce it; False means a human or agent read something into the data.
    Evidence is immutable once stored - a later look is new evidence, not an
    edit of the old one.
    """

    key: str
    kind: EvidenceKind
    summary: str
    source: str
    mechanically_observed: bool
    detail: str | None = None
    function_address: int | None = None

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("evidence key must not be empty")
        if not self.summary.strip():
            raise ValueError("evidence summary must not be empty")


@dataclass(frozen=True)
class Relationship:
    """A subject-predicate-object claim about the binary's structure."""

    subject: str
    predicate: str
    object: str
    confidence: float
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        for name in ("subject", "predicate", "object"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"relationship {name} must not be empty")


@dataclass(frozen=True)
class HypothesisRevision:
    """One immutable point in a hypothesis's belief history.

    Carries the fields MASTER_SPEC section 23 requires of a hypothesis.
    `created_at` is when the hypothesis was first asserted and is carried
    forward across revisions; `updated_at` is when this particular revision was
    written. `key` is the stable identity that survives revision, so
    `(binary_id, key)` names a belief and `revision` names a moment in it.
    """

    id: int
    binary_id: int
    key: str
    revision: int
    subject: str
    claim: str
    certainty: Certainty
    status: HypothesisStatus
    confidence: float
    evidence: tuple[str, ...]
    uncertainty: str | None
    change_reason: str
    supersedes_id: int | None
    created_at: str
    updated_at: str
