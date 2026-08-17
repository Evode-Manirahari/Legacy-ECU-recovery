"""Domain models shared across intake, storage, and reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Certainty(StrEnum):
    """How strongly an investigation statement is supported."""

    KNOWN = "known"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


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

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if self.certainty is Certainty.KNOWN and self.confidence < 1.0:
            raise ValueError("known claims must have confidence 1.0")

