"""SQLite schema for the epistemic evidence model, plus forward migration.

Two rules shape this schema.

First, belief is append-only. `hypotheses` is not a table of current beliefs;
it is the revision log. One row is one immutable moment in one belief's
history, and the current belief is the highest `revision` for a given
`(binary_id, hypothesis_key)`. An `UPDATE` trigger enforces that, so a caller
cannot silently rewrite what the system used to think - the ability to show
that the system changed its mind, and why, is the point of the model.

Second, an observation is immutable. `evidence` rows are also `UPDATE`-guarded:
looking again produces new evidence, it never edits the old record.

`DELETE` is deliberately not guarded. Removing a binary should remove its
investigation through the existing cascade; that is discarding a whole record,
which is a different act from quietly revising a belief inside one.

The `analyses` table is the `Binary` entity. It predates this node and is read
by name elsewhere, so it keeps its physical name and gains a `binaries` view
rather than a rename, which would be a destructive migration with no epistemic
benefit.
"""

from __future__ import annotations

import sqlite3

HYPOTHESIS_STATUSES = ("untested", "supported", "weakened", "rejected", "confirmed")
EVIDENCE_STANCES = ("supports", "contradicts", "context")
EVIDENCE_KINDS = (
    "decompilation",
    "disassembly",
    "call_graph",
    "cross_reference",
    "memory_access",
    "constant",
    "table_access",
    "execution_trace",
    "experiment_result",
    "expert_review",
    "static_property",
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


BASE_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE,
    filename TEXT NOT NULL,
    source_path TEXT NOT NULL,
    size INTEGER NOT NULL,
    sha1 TEXT NOT NULL,
    md5 TEXT NOT NULL,
    entropy REAL NOT NULL,
    processor TEXT,
    byte_order TEXT,
    profile_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS functions (
    id INTEGER PRIMARY KEY,
    analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    address INTEGER NOT NULL,
    name TEXT NOT NULL,
    size INTEGER,
    decompilation TEXT,
    UNIQUE(analysis_id, address)
);
CREATE TABLE IF NOT EXISTS hypotheses (
    id INTEGER PRIMARY KEY,
    analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    claim TEXT NOT NULL,
    certainty TEXT NOT NULL CHECK(certainty IN ('known', 'inferred', 'unknown')),
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    evidence_json TEXT NOT NULL,
    uncertainty TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

EVIDENCE_SCHEMA = f"""
CREATE VIEW IF NOT EXISTS binaries AS SELECT * FROM analyses;

CREATE TABLE IF NOT EXISTS memory_regions (
    id INTEGER PRIMARY KEY,
    binary_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    start_address INTEGER NOT NULL,
    end_address INTEGER NOT NULL,
    readable INTEGER NOT NULL CHECK(readable IN (0, 1)),
    writable INTEGER NOT NULL CHECK(writable IN (0, 1)),
    executable INTEGER NOT NULL CHECK(executable IN (0, 1)),
    initialized INTEGER NOT NULL CHECK(initialized IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK(end_address >= start_address),
    UNIQUE(binary_id, name, start_address)
);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY,
    binary_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    evidence_key TEXT NOT NULL,
    kind TEXT NOT NULL CHECK({_in_list("kind", EVIDENCE_KINDS)}),
    summary TEXT NOT NULL,
    detail TEXT,
    source TEXT NOT NULL,
    mechanically_observed INTEGER NOT NULL CHECK(mechanically_observed IN (0, 1)),
    function_address INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(binary_id, evidence_key)
);

CREATE TABLE IF NOT EXISTS hypothesis_evidence (
    id INTEGER PRIMARY KEY,
    hypothesis_revision_id INTEGER NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
    evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
    stance TEXT NOT NULL CHECK({_in_list("stance", EVIDENCE_STANCES)}),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(hypothesis_revision_id, evidence_id)
);

CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY,
    binary_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    revision INTEGER NOT NULL DEFAULT 1,
    change_reason TEXT NOT NULL DEFAULT 'initial assertion',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(binary_id, subject, predicate, object, revision)
);

CREATE TABLE IF NOT EXISTS relationship_evidence (
    id INTEGER PRIMARY KEY,
    relationship_id INTEGER NOT NULL REFERENCES relationships(id) ON DELETE CASCADE,
    evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
    stance TEXT NOT NULL CHECK({_in_list("stance", EVIDENCE_STANCES)}),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(relationship_id, evidence_id)
);

-- Unique, not merely indexed: two beliefs sharing an identity would make
-- "the current revision of this hypothesis" ambiguous.
DROP INDEX IF EXISTS hypotheses_identity;
CREATE UNIQUE INDEX IF NOT EXISTS hypotheses_identity_unique
    ON hypotheses(analysis_id, hypothesis_key, revision);
CREATE INDEX IF NOT EXISTS evidence_by_binary ON evidence(binary_id);
CREATE INDEX IF NOT EXISTS relationships_identity
    ON relationships(binary_id, subject, predicate, object, revision);

CREATE TRIGGER IF NOT EXISTS hypotheses_are_append_only
BEFORE UPDATE ON hypotheses
BEGIN
    SELECT RAISE(ABORT,
        'hypotheses are append-only: write a new revision instead of overwriting belief');
END;

CREATE TRIGGER IF NOT EXISTS evidence_is_immutable
BEFORE UPDATE ON evidence
BEGIN
    SELECT RAISE(ABORT,
        'evidence is immutable: record a new observation instead of editing one');
END;

CREATE TRIGGER IF NOT EXISTS relationships_are_append_only
BEFORE UPDATE ON relationships
BEGIN
    SELECT RAISE(ABORT,
        'relationships are append-only: write a new revision instead of overwriting');
END;
"""

# Columns added to the pre-graph `hypotheses` table by this node. Order matters
# only for readability; each is applied independently if absent.
HYPOTHESIS_COLUMNS: tuple[tuple[str, str], ...] = (
    ("hypothesis_key", "TEXT"),
    ("revision", "INTEGER NOT NULL DEFAULT 1"),
    (
        "status",
        f"TEXT NOT NULL DEFAULT 'untested' CHECK({_in_list('status', HYPOTHESIS_STATUSES)})",
    ),
    ("change_reason", "TEXT NOT NULL DEFAULT 'initial assertion'"),
    ("supersedes_id", "INTEGER REFERENCES hypotheses(id)"),
    ("updated_at", "TEXT"),
    # Only the caller's own prose, kept apart from `evidence_json` so a
    # revision can carry it forward without having to parse rendered
    # structured evidence back out of a display string.
    ("free_text_json", "TEXT"),
)


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}


def migrate(connection: sqlite3.Connection) -> None:
    """Bring any database, new or pre-graph, up to the evidence model.

    Safe to run repeatedly. A database written before this node keeps every row
    it had: each legacy hypothesis becomes revision 1 of its own belief, because
    there is no honest way to reconstruct after the fact which of two legacy
    rows were revisions of a single claim.
    """
    connection.executescript(BASE_SCHEMA)

    existing = _columns(connection, "hypotheses")
    added = [name for name, ddl in HYPOTHESIS_COLUMNS if name not in existing]
    for name, ddl in HYPOTHESIS_COLUMNS:
        if name not in existing:
            connection.execute(f"ALTER TABLE hypotheses ADD COLUMN {name} {ddl}")

    if "hypothesis_key" in added:
        # Legacy rows predate belief identity. Give each one a stable key
        # derived from its own row id so history starts from where it stands.
        connection.execute(
            "UPDATE hypotheses SET hypothesis_key = 'H-' || id WHERE hypothesis_key IS NULL"
        )
    if "status" in added:
        # A KNOWN claim is a mechanically observed fact carrying confidence
        # 1.0, so CONFIRMED is faithful. Nothing else can be shown to have been
        # tested, so it stays UNTESTED rather than being flattered.
        connection.execute(
            "UPDATE hypotheses SET status = CASE certainty"
            " WHEN 'known' THEN 'confirmed' ELSE 'untested' END"
        )
    if "updated_at" in added:
        connection.execute("UPDATE hypotheses SET updated_at = created_at WHERE updated_at IS NULL")
    if "free_text_json" in added:
        # Legacy rows carry only prose, so their whole evidence list is it.
        connection.execute(
            "UPDATE hypotheses SET free_text_json = evidence_json WHERE free_text_json IS NULL"
        )

    connection.executescript(EVIDENCE_SCHEMA)
