"""Opening a pre-graph database must not lose or invent anything.

The pre-graph schema is `BASE_SCHEMA`: hypotheses with no identity, no status,
no revision, and no history. These tests build a database in exactly that shape
and then open it through the current store.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ecu_recovery.evidence.schema import BASE_SCHEMA
from ecu_recovery.models import Certainty, HypothesisStatus
from ecu_recovery.store import InvestigationStore

LEGACY_ROWS: tuple[tuple[str, str, str, float, list[str]], ...] = (
    ("FUN_8000", "possible initialization routine", "inferred", 0.65, ["first function at base"]),
    ("FUN_9000", "reset vector table", "known", 1.0, ["vector table at 0x0"]),
    ("FUN_A000", "purpose not established", "unknown", 0.0, []),
)


def _legacy_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(BASE_SCHEMA)
    connection.execute(
        """
        INSERT INTO analyses
            (sha256, filename, source_path, size, sha1, md5, entropy, profile_json)
        VALUES ('abc123', 'legacy.rom', '/tmp/legacy.rom', 1024, 'sha1', 'md5', 4.2,
                '{"fill_bytes": {}, "repeated_regions": []}')
        """
    )
    for subject, claim, certainty, confidence, evidence in LEGACY_ROWS:
        connection.execute(
            """
            INSERT INTO hypotheses
                (analysis_id, subject, claim, certainty, confidence, evidence_json, uncertainty)
            VALUES (1, ?, ?, ?, ?, ?, NULL)
            """,
            (subject, claim, certainty, confidence, json.dumps(evidence)),
        )
    connection.commit()
    connection.close()


def test_legacy_rows_all_survive_migration(tmp_path: Path) -> None:
    database = tmp_path / "legacy.sqlite3"
    _legacy_database(database)

    store = InvestigationStore(database)

    current = store.current_hypotheses(1)
    assert {entry.subject for entry in current} == {"FUN_8000", "FUN_9000", "FUN_A000"}
    assert len(current) == len(LEGACY_ROWS)


def test_legacy_rows_keep_their_claims_and_confidence(tmp_path: Path) -> None:
    database = tmp_path / "legacy.sqlite3"
    _legacy_database(database)

    store = InvestigationStore(database)

    by_subject = {entry.subject: entry for entry in store.current_hypotheses(1)}
    assert by_subject["FUN_8000"].claim == "possible initialization routine"
    assert by_subject["FUN_8000"].confidence == 0.65
    assert by_subject["FUN_8000"].evidence == ("first function at base",)
    assert by_subject["FUN_8000"].certainty is Certainty.INFERRED


def test_legacy_rows_are_not_flattered_into_looking_tested(tmp_path: Path) -> None:
    """Nothing shows a legacy claim was tested, so it must read as UNTESTED.

    The one exception is a KNOWN claim, which the model already requires to
    carry confidence 1.0 and which represents a mechanically observed fact.
    """
    database = tmp_path / "legacy.sqlite3"
    _legacy_database(database)

    store = InvestigationStore(database)

    by_subject = {entry.subject: entry for entry in store.current_hypotheses(1)}
    assert by_subject["FUN_8000"].status is HypothesisStatus.UNTESTED
    assert by_subject["FUN_A000"].status is HypothesisStatus.UNTESTED
    assert by_subject["FUN_9000"].status is HypothesisStatus.CONFIRMED


def test_each_legacy_row_becomes_its_own_belief_at_revision_one(tmp_path: Path) -> None:
    """Two legacy rows cannot be retroactively merged into one history."""
    database = tmp_path / "legacy.sqlite3"
    _legacy_database(database)

    store = InvestigationStore(database)

    keys = {entry.key for entry in store.current_hypotheses(1)}
    assert len(keys) == len(LEGACY_ROWS)
    for entry in store.current_hypotheses(1):
        assert entry.revision == 1
        assert entry.supersedes_id is None


def test_a_migrated_belief_can_then_be_revised(tmp_path: Path) -> None:
    database = tmp_path / "legacy.sqlite3"
    _legacy_database(database)
    store = InvestigationStore(database)
    key = next(e.key for e in store.current_hypotheses(1) if e.subject == "FUN_8000")

    store.revise_hypothesis(
        1,
        key,
        confidence=0.9,
        status=HypothesisStatus.SUPPORTED,
        reason="reset vector confirmed",
    )

    history = store.hypothesis_history(1, key)
    assert [entry.confidence for entry in history] == [0.65, 0.9]


def test_new_keys_do_not_collide_with_migrated_ones(tmp_path: Path) -> None:
    database = tmp_path / "legacy.sqlite3"
    _legacy_database(database)
    store = InvestigationStore(database)
    from ecu_recovery.models import Hypothesis

    fresh = store.save_hypothesis(
        1, Hypothesis("FUN_B000", "brand new claim", Certainty.INFERRED, 0.5)
    )

    keys = [entry.key for entry in store.current_hypotheses(1)]
    assert len(keys) == len(set(keys))
    assert fresh.revision == 1


def test_a_gap_in_legacy_row_ids_does_not_produce_a_duplicate_key(tmp_path: Path) -> None:
    """Legacy keys come from row ids, so they can be sparse."""
    database = tmp_path / "legacy.sqlite3"
    _legacy_database(database)
    gapped = sqlite3.connect(database)
    gapped.execute("DELETE FROM hypotheses WHERE id = 2")
    gapped.commit()
    gapped.close()
    store = InvestigationStore(database)
    from ecu_recovery.models import Hypothesis

    store.save_hypothesis(1, Hypothesis("FUN_NEW", "a new claim", Certainty.INFERRED, 0.5))

    keys = [entry.key for entry in store.current_hypotheses(1)]
    assert sorted(keys) == ["H-1", "H-2", "H-3"]
    assert len(keys) == len(set(keys))
