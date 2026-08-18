"""The entities EVIDENCE-001 requires, and the invariants they carry."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from evidence_support import investigation

from ecu_recovery.evidence.schema import migrate
from ecu_recovery.models import (
    Certainty,
    Evidence,
    EvidenceKind,
    HypothesisStatus,
    MemoryRegion,
    Relationship,
)

REQUIRED_TABLES = {
    "analyses",  # the Binary entity; see evidence/schema.py
    "binaries",
    "functions",
    "memory_regions",
    "hypotheses",
    "evidence",
    "hypothesis_evidence",
    "relationships",
    "relationship_evidence",
}


def test_every_required_entity_exists(tmp_path: Path) -> None:
    store, _ = investigation(tmp_path)
    with store.connect() as connection:
        present = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }
    assert present >= REQUIRED_TABLES


def test_binaries_view_exposes_the_binary_entity(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    with store.connect() as connection:
        row = connection.execute(
            "SELECT sha256, size FROM binaries WHERE id = ?", (binary_id,)
        ).fetchone()
    assert row is not None
    assert row["size"] == 256


def test_hypothesis_carries_every_required_field(tmp_path: Path) -> None:
    store, _ = investigation(tmp_path)
    with store.connect() as connection:
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(hypotheses)")}
    # MASTER_SPEC section 23. `analysis_id` is the binary reference; the
    # `binaries` view and `HypothesisRevision.binary_id` expose it by name.
    assert {"id", "analysis_id", "subject", "claim", "status", "confidence"} <= columns
    assert {"created_at", "updated_at"} <= columns


def test_all_five_statuses_are_representable() -> None:
    assert {status.value for status in HypothesisStatus} == {
        "untested",
        "supported",
        "weakened",
        "rejected",
        "confirmed",
    }


def test_status_and_certainty_are_independent_axes(tmp_path: Path) -> None:
    """An inferred claim can be well supported without becoming a known fact."""
    store, binary_id = investigation(tmp_path)
    from ecu_recovery.models import Hypothesis

    revision = store.save_hypothesis(
        binary_id,
        Hypothesis(
            subject="FUN_923A",
            claim="engine-speed calculation",
            certainty=Certainty.INFERRED,
            confidence=0.88,
            status=HypothesisStatus.SUPPORTED,
        ),
    )
    assert revision.certainty is Certainty.INFERRED
    assert revision.status is HypothesisStatus.SUPPORTED


def test_status_defaults_to_untested(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    from ecu_recovery.models import Hypothesis

    revision = store.save_hypothesis(
        binary_id,
        Hypothesis("FUN_1", "a guess", Certainty.INFERRED, 0.4),
    )
    assert revision.status is HypothesisStatus.UNTESTED


def test_unknown_stays_unknown(tmp_path: Path) -> None:
    """An admitted gap must not be able to read as knowledge."""
    store, binary_id = investigation(tmp_path)
    from ecu_recovery.models import Hypothesis

    revision = store.save_hypothesis(
        binary_id,
        Hypothesis(
            subject="FUN_923A",
            claim="scaling formula",
            certainty=Certainty.UNKNOWN,
            confidence=0.0,
            uncertainty="exact scaling formula is not recovered",
        ),
    )
    assert revision.certainty is Certainty.UNKNOWN
    assert revision.status is HypothesisStatus.UNTESTED
    assert revision.uncertainty == "exact scaling formula is not recovered"


def test_known_claims_still_require_full_confidence() -> None:
    from ecu_recovery.models import Hypothesis

    with pytest.raises(ValueError, match="confidence 1.0"):
        Hypothesis("FUN_1", "fact", Certainty.KNOWN, 0.9)


def test_memory_region_round_trips(tmp_path: Path) -> None:
    store, binary_id = investigation(tmp_path)
    store.save_memory_region(binary_id, MemoryRegion("ROM", 0x0000, 0x7FFF, executable=True))
    store.save_memory_region(
        binary_id, MemoryRegion("RAM", 0x8000, 0x8FFF, writable=True, initialized=False)
    )

    regions = store.memory_regions(binary_id)

    assert [region.name for region in regions] == ["ROM", "RAM"]
    assert regions[0].size == 0x8000
    assert regions[0].executable is True
    assert regions[1].writable is True
    assert regions[1].initialized is False


def test_memory_region_rejects_inverted_range() -> None:
    with pytest.raises(ValueError, match="must not precede"):
        MemoryRegion("BAD", 0x100, 0x0FF)


def test_relationship_rejects_impossible_confidence() -> None:
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        Relationship("FUN_A", "calls", "FUN_B", 1.4)


def test_relationship_rejects_empty_terms() -> None:
    with pytest.raises(ValueError, match="predicate must not be empty"):
        Relationship("FUN_A", "  ", "FUN_B", 0.5)


def test_evidence_rejects_empty_key_or_summary() -> None:
    with pytest.raises(ValueError, match="key must not be empty"):
        Evidence("", EvidenceKind.DISASSEMBLY, "something", "ghidra", True)
    with pytest.raises(ValueError, match="summary must not be empty"):
        Evidence("E-1", EvidenceKind.DISASSEMBLY, "   ", "ghidra", True)


def test_migrate_is_idempotent() -> None:
    connection = sqlite3.connect(":memory:")
    migrate(connection)
    before = {str(row[1]) for row in connection.execute("PRAGMA table_info(hypotheses)")}
    migrate(connection)
    after = {str(row[1]) for row in connection.execute("PRAGMA table_info(hypotheses)")}
    assert before == after
