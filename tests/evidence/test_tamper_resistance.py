"""The append-only guarantee against a caller who does not use the store API.

The central requirement of this node is that belief state is never silently
overwritten. `BEFORE UPDATE` triggers were the first line of that, and on their
own they do not hold: SQLite resolves an `INSERT OR REPLACE` conflict by
deleting the losing row and inserting the new one, so an update trigger never
fires and a stored revision can be rewritten in place while keeping its
identity. These tests pin the `BEFORE INSERT` guards that close that path.

They go through raw SQL on purpose. The store's own API only ever appends, so a
test written against the API cannot reach this: the question here is whether the
database itself refuses, which is what the schema docstring claims.
"""

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
    Hypothesis,
    HypothesisStatus,
    Relationship,
)
from ecu_recovery.store import InvestigationStore

APPEND_ONLY_TABLES = (
    "hypotheses",
    "evidence",
    "relationships",
    "hypothesis_evidence",
    "relationship_evidence",
)


def _populated(tmp_path: Path) -> tuple[InvestigationStore, int]:
    """One binary carrying evidence, a belief that cites it, and a relationship."""
    store, binary_id = investigation(tmp_path)
    store.save_evidence(
        binary_id,
        Evidence(
            key="E-1",
            kind=EvidenceKind.CONSTANT,
            summary="compares against 1000",
            source="ghidra",
            mechanically_observed=True,
        ),
    )
    store.save_hypothesis(
        binary_id,
        Hypothesis(
            subject="FUN_0800",
            claim="clamps its output to 1000",
            certainty=Certainty.INFERRED,
            confidence=0.6,
        ),
        supporting=["E-1"],
    )
    store.save_relationship(
        binary_id,
        Relationship(
            subject="FUN_0800",
            predicate="calls",
            object="FUN_0900",
            confidence=0.9,
            evidence=("E-1",),
        ),
    )
    return store, binary_id


def _replace_row(
    connection: sqlite3.Connection, table: str, row_id: int, **changes: object
) -> None:
    """Rewrite one row through the REPLACE path, keeping its identity."""
    row = connection.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
    assert row is not None
    columns = list(row.keys())
    values = [changes.get(name, row[name]) for name in columns]
    placeholders = ", ".join("?" * len(columns))
    connection.execute(
        f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
        values,
    )


# --- the REPLACE path ---


def test_a_belief_cannot_be_rewritten_in_place_through_replace(tmp_path: Path) -> None:
    """The exact hole a BEFORE UPDATE trigger leaves open."""
    store, binary_id = _populated(tmp_path)
    current = store.current_hypothesis(binary_id, "H-1")
    assert current is not None

    with pytest.raises(sqlite3.IntegrityError, match="append-only"), store.connect() as connection:
        _replace_row(connection, "hypotheses", current.id, confidence=0.99)

    unchanged = store.current_hypothesis(binary_id, "H-1")
    assert unchanged is not None
    assert unchanged.confidence == 0.6


def test_an_observation_cannot_be_rewritten_through_replace(tmp_path: Path) -> None:
    store, binary_id = _populated(tmp_path)
    with store.connect() as connection:
        evidence_id = int(
            connection.execute("SELECT id FROM evidence WHERE evidence_key = 'E-1'").fetchone()[
                "id"
            ]
        )

    with pytest.raises(sqlite3.IntegrityError, match="immutable"), store.connect() as connection:
        _replace_row(connection, "evidence", evidence_id, summary="something else entirely")

    assert [item.summary for item in store.evidence_for_binary(binary_id)] == [
        "compares against 1000"
    ]


def test_a_relationship_revision_cannot_be_rewritten_through_replace(tmp_path: Path) -> None:
    store, binary_id = _populated(tmp_path)
    with store.connect() as connection:
        relationship_id = int(connection.execute("SELECT id FROM relationships").fetchone()["id"])

    with pytest.raises(sqlite3.IntegrityError, match="append-only"), store.connect() as connection:
        _replace_row(connection, "relationships", relationship_id, confidence=0.1)

    assert [item.confidence for item in store.current_relationships(binary_id)] == [0.9]


def test_what_a_recorded_belief_cited_cannot_be_restated(tmp_path: Path) -> None:
    """Flipping a stance would rewrite the basis of a belief already written."""
    store, binary_id = _populated(tmp_path)
    with store.connect() as connection:
        link_id = int(connection.execute("SELECT id FROM hypothesis_evidence").fetchone()["id"])

    with (
        pytest.raises(sqlite3.IntegrityError, match="fixed once written"),
        store.connect() as (connection),
    ):
        _replace_row(connection, "hypothesis_evidence", link_id, stance="contradicts")


def test_what_a_relationship_cited_cannot_be_restated(tmp_path: Path) -> None:
    store, _ = _populated(tmp_path)
    with store.connect() as connection:
        link_id = int(connection.execute("SELECT id FROM relationship_evidence").fetchone()["id"])

    with (
        pytest.raises(sqlite3.IntegrityError, match="fixed once written"),
        store.connect() as (connection),
    ):
        _replace_row(connection, "relationship_evidence", link_id, stance="contradicts")


# --- the guards must not block what the model is for ---


def test_appending_the_next_revision_still_works(tmp_path: Path) -> None:
    """A guard that blocked legitimate appends would break the model instead."""
    store, binary_id = _populated(tmp_path)

    revised = store.revise_hypothesis(
        binary_id,
        "H-1",
        status=HypothesisStatus.WEAKENED,
        confidence=0.3,
        reason="the clamp turned out to be conditional",
    )

    assert revised.revision == 2
    assert [item.revision for item in store.hypothesis_history(binary_id, "H-1")] == [1, 2]


def test_reasserting_a_relationship_still_appends_a_revision(tmp_path: Path) -> None:
    store, binary_id = _populated(tmp_path)

    store.save_relationship(
        binary_id,
        Relationship(
            subject="FUN_0800",
            predicate="calls",
            object="FUN_0900",
            confidence=0.95,
            evidence=("E-1",),
        ),
        reason="confirmed by a second cross-reference",
    )

    history = store.relationship_history(binary_id, "FUN_0800", "calls", "FUN_0900")
    assert [(revision, confidence) for revision, confidence, _ in history] == [(1, 0.9), (2, 0.95)]


def test_discarding_a_whole_binary_is_still_allowed(tmp_path: Path) -> None:
    """DELETE stays unguarded by design: dropping a record is not revising one."""
    store, binary_id = _populated(tmp_path)

    with store.connect() as connection:
        connection.execute("DELETE FROM analyses WHERE id = ?", (binary_id,))

    with store.connect() as connection:
        for table in APPEND_ONLY_TABLES:
            remaining = connection.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            assert remaining == 0, table


def test_evidence_references_are_a_constraint_not_a_comment(tmp_path: Path) -> None:
    store, _ = _populated(tmp_path)

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"), store.connect() as connection:
        connection.execute(
            "INSERT INTO evidence (binary_id, evidence_key, kind, summary, source, "
            "mechanically_observed) VALUES (99999, 'X-1', 'constant', 's', 'ghidra', 1)"
        )


# --- the guards reach an existing database too ---


def test_a_database_written_before_the_guards_gains_them_on_migration(tmp_path: Path) -> None:
    """Otherwise the fix would only protect databases created after it."""
    store, binary_id = _populated(tmp_path)
    with store.connect() as connection:
        for table in APPEND_ONLY_TABLES:
            connection.execute(f"DROP TRIGGER IF EXISTS {table}_are_never_replaced")
            connection.execute(f"DROP TRIGGER IF EXISTS {table}_is_never_replaced")

    with store.connect() as connection:
        migrate(connection)

    current = store.current_hypothesis(binary_id, "H-1")
    assert current is not None
    with pytest.raises(sqlite3.IntegrityError, match="append-only"), store.connect() as connection:
        _replace_row(connection, "hypotheses", current.id, confidence=0.99)


def test_every_append_only_table_carries_both_guards(tmp_path: Path) -> None:
    """Named explicitly so a table added later is not left unprotected by accident."""
    store, _ = _populated(tmp_path)

    with store.connect() as connection:
        triggers = {
            (str(row["tbl_name"]), str(row["name"]))
            for row in connection.execute(
                "SELECT tbl_name, name FROM sqlite_master WHERE type = 'trigger'"
            )
        }

    for table in APPEND_ONLY_TABLES:
        names = {name for owner, name in triggers if owner == table}
        assert any("never_replaced" in name for name in names), f"{table} has no INSERT guard"
