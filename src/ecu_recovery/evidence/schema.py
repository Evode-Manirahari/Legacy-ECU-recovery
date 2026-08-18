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

Guarding `UPDATE` alone is not enough, which is worth spelling out because it
is easy to believe otherwise. SQLite resolves an `INSERT OR REPLACE` conflict by
deleting the losing row and inserting the new one, so a `BEFORE UPDATE` trigger
never sees it: a caller could rewrite a stored belief in place, at the same
revision number, and no trigger would fire. Every append-only table therefore
also carries a `BEFORE INSERT` guard that aborts when the identity already
exists, which is the point the `REPLACE` path has to pass through.

`DELETE` is deliberately not guarded. Removing a binary should remove its
investigation through the existing cascade; that is discarding a whole record,
which is a different act from quietly revising a belief inside one. (A
`BEFORE DELETE` guard would not have closed the `REPLACE` path anyway: those
deletes only fire delete triggers when recursive triggers are enabled, which
they are not.)

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

-- The INSERT OR REPLACE path. Each guard fires before conflict resolution can
-- delete the row it would have replaced, so an existing revision cannot be
-- rewritten in place while keeping its identity.
CREATE TRIGGER IF NOT EXISTS hypotheses_are_never_replaced
BEFORE INSERT ON hypotheses
WHEN EXISTS (
    SELECT 1 FROM hypotheses
    WHERE analysis_id = NEW.analysis_id
      AND hypothesis_key = NEW.hypothesis_key
      AND revision = NEW.revision
)
BEGIN
    SELECT RAISE(ABORT,
        'hypotheses are append-only: this revision already exists, append the next one');
END;

CREATE TRIGGER IF NOT EXISTS evidence_is_never_replaced
BEFORE INSERT ON evidence
WHEN EXISTS (
    SELECT 1 FROM evidence
    WHERE binary_id = NEW.binary_id AND evidence_key = NEW.evidence_key
)
BEGIN
    SELECT RAISE(ABORT,
        'evidence is immutable: this key is taken, record the observation under a new key');
END;

CREATE TRIGGER IF NOT EXISTS relationships_are_never_replaced
BEFORE INSERT ON relationships
WHEN EXISTS (
    SELECT 1 FROM relationships
    WHERE binary_id = NEW.binary_id
      AND subject = NEW.subject
      AND predicate = NEW.predicate
      AND object = NEW.object
      AND revision = NEW.revision
)
BEGIN
    SELECT RAISE(ABORT,
        'relationships are append-only: this revision already exists, append the next one');
END;

-- What a recorded belief cited is part of that belief. Replacing a stance link
-- would rewrite the basis of a revision that has already been written.
CREATE TRIGGER IF NOT EXISTS hypothesis_evidence_is_never_replaced
BEFORE INSERT ON hypothesis_evidence
WHEN EXISTS (
    SELECT 1 FROM hypothesis_evidence
    WHERE hypothesis_revision_id = NEW.hypothesis_revision_id
      AND evidence_id = NEW.evidence_id
)
BEGIN
    SELECT RAISE(ABORT,
        'a revision citation is fixed once written: cite it from a new revision instead');
END;

CREATE TRIGGER IF NOT EXISTS relationship_evidence_is_never_replaced
BEFORE INSERT ON relationship_evidence
WHEN EXISTS (
    SELECT 1 FROM relationship_evidence
    WHERE relationship_id = NEW.relationship_id AND evidence_id = NEW.evidence_id
)
BEGIN
    SELECT RAISE(ABORT,
        'a relationship citation is fixed once written: cite it from a new revision instead');
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
