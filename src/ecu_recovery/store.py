"""SQLite persistence for investigation facts, evidence, and belief history.

Belief is never overwritten here. `save_hypothesis` and `revise_hypothesis`
both append a revision, and the store reads current belief as the newest
revision of each hypothesis. Callers that only ever state a hypothesis once see
the same behaviour they always did; callers that change their mind get a
history they can show.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from .evidence.schema import migrate
from .models import (
    BinaryProfile,
    Certainty,
    Evidence,
    EvidenceStance,
    FunctionRecord,
    Hypothesis,
    HypothesisRevision,
    HypothesisStatus,
    MemoryRegion,
    Relationship,
)

INITIAL_REASON = "initial assertion"


def _render_evidence(summary: str, stance: EvidenceStance, key: str) -> str:
    """Render structured evidence into the free-text list the report reads."""
    return f"{key} [{stance.value}] {summary}"


class InvestigationStore:
    def __init__(self, database_path: str | Path):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            migrate(connection)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        # Per-connection, not per-database: without this the evidence-to-
        # hypothesis references would be documentation rather than a constraint.
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    # ------------------------------------------------------------------
    # Binary and function facts
    # ------------------------------------------------------------------

    def save_profile(self, profile: BinaryProfile) -> int:
        profile_json = json.dumps(
            {
                "fill_bytes": {f"0x{k:02X}": v for k, v in profile.fill_bytes.items()},
                "repeated_regions": [region.__dict__ for region in profile.repeated_regions],
            },
            sort_keys=True,
        )
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO analyses
                    (sha256, filename, source_path, size, sha1, md5, entropy,
                     processor, byte_order, profile_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sha256) DO UPDATE SET
                    filename=excluded.filename,
                    source_path=excluded.source_path,
                    processor=COALESCE(excluded.processor, analyses.processor),
                    byte_order=COALESCE(excluded.byte_order, analyses.byte_order),
                    profile_json=excluded.profile_json
                """,
                (
                    profile.sha256,
                    profile.filename,
                    profile.path,
                    profile.size,
                    profile.sha1,
                    profile.md5,
                    profile.entropy,
                    profile.processor,
                    profile.byte_order,
                    profile_json,
                ),
            )
            row = connection.execute(
                "SELECT id FROM analyses WHERE sha256 = ?", (profile.sha256,)
            ).fetchone()
            assert row is not None
            return int(row["id"])

    def save_function(self, analysis_id: int, function: FunctionRecord) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO functions (analysis_id, address, name, size, decompilation)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(analysis_id, address) DO UPDATE SET
                    name=excluded.name, size=excluded.size,
                    decompilation=excluded.decompilation
                """,
                (
                    analysis_id,
                    function.address,
                    function.name,
                    function.size,
                    function.decompilation,
                ),
            )

    def save_memory_region(self, binary_id: int, region: MemoryRegion) -> int:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_regions
                    (binary_id, name, start_address, end_address,
                     readable, writable, executable, initialized)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(binary_id, name, start_address) DO UPDATE SET
                    end_address=excluded.end_address,
                    readable=excluded.readable,
                    writable=excluded.writable,
                    executable=excluded.executable,
                    initialized=excluded.initialized
                """,
                (
                    binary_id,
                    region.name,
                    region.start_address,
                    region.end_address,
                    int(region.readable),
                    int(region.writable),
                    int(region.executable),
                    int(region.initialized),
                ),
            )
            row = connection.execute(
                "SELECT id FROM memory_regions WHERE binary_id = ? AND name = ? "
                "AND start_address = ?",
                (binary_id, region.name, region.start_address),
            ).fetchone()
            assert row is not None
            return int(row["id"])

    def memory_regions(self, binary_id: int) -> list[MemoryRegion]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM memory_regions WHERE binary_id = ? ORDER BY start_address",
                (binary_id,),
            ).fetchall()
        return [
            MemoryRegion(
                name=str(row["name"]),
                start_address=int(row["start_address"]),
                end_address=int(row["end_address"]),
                readable=bool(row["readable"]),
                writable=bool(row["writable"]),
                executable=bool(row["executable"]),
                initialized=bool(row["initialized"]),
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    def save_evidence(self, binary_id: int, evidence: Evidence) -> int:
        """Record one observation. Re-recording the same key is rejected.

        Evidence is immutable, so a conflicting key is a caller error rather
        than an update: a second look at the same thing is a second piece of
        evidence and deserves its own key.
        """
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM evidence WHERE binary_id = ? AND evidence_key = ?",
                (binary_id, evidence.key),
            ).fetchone()
            if existing is not None:
                raise ValueError(
                    f"evidence {evidence.key!r} already exists for binary {binary_id}; "
                    "evidence is immutable, record a new observation under a new key"
                )
            cursor = connection.execute(
                """
                INSERT INTO evidence
                    (binary_id, evidence_key, kind, summary, detail, source,
                     mechanically_observed, function_address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    binary_id,
                    evidence.key,
                    evidence.kind.value,
                    evidence.summary,
                    evidence.detail,
                    evidence.source,
                    int(evidence.mechanically_observed),
                    evidence.function_address,
                ),
            )
            return int(cursor.lastrowid or 0)

    def evidence_for_binary(
        self, binary_id: int, *, mechanical_only: bool = False
    ) -> list[Evidence]:
        """Every observation recorded against a binary.

        `mechanical_only` narrows to what a deterministic tool observed, which
        is the subset an engineering reader may treat as fact rather than
        interpretation.
        """
        query = "SELECT * FROM evidence WHERE binary_id = ?"
        if mechanical_only:
            query += " AND mechanically_observed = 1"
        query += " ORDER BY id"
        with self.connect() as connection:
            rows = connection.execute(query, (binary_id,)).fetchall()
        return [self._evidence_from_row(row) for row in rows]

    def evidence_for_revision(self, revision_id: int) -> list[tuple[Evidence, EvidenceStance]]:
        """What this belief rested on at this moment, with each stance."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT e.*, link.stance AS stance
                FROM hypothesis_evidence AS link
                JOIN evidence AS e ON e.id = link.evidence_id
                WHERE link.hypothesis_revision_id = ?
                ORDER BY link.id
                """,
                (revision_id,),
            ).fetchall()
        return [(self._evidence_from_row(row), EvidenceStance(row["stance"])) for row in rows]

    @staticmethod
    def _evidence_from_row(row: sqlite3.Row) -> Evidence:
        from .models import EvidenceKind

        return Evidence(
            key=str(row["evidence_key"]),
            kind=EvidenceKind(row["kind"]),
            summary=str(row["summary"]),
            source=str(row["source"]),
            mechanically_observed=bool(row["mechanically_observed"]),
            detail=None if row["detail"] is None else str(row["detail"]),
            function_address=(
                None if row["function_address"] is None else int(row["function_address"])
            ),
        )

    def _resolve_evidence_ids(
        self,
        connection: sqlite3.Connection,
        binary_id: int,
        keys: Sequence[str],
    ) -> list[int]:
        resolved: list[int] = []
        for key in keys:
            row = connection.execute(
                "SELECT id FROM evidence WHERE binary_id = ? AND evidence_key = ?",
                (binary_id, key),
            ).fetchone()
            if row is None:
                raise KeyError(
                    f"evidence {key!r} is not recorded for binary {binary_id}; "
                    "record the observation before citing it"
                )
            resolved.append(int(row["id"]))
        return resolved

    # ------------------------------------------------------------------
    # Hypotheses: append-only belief history
    # ------------------------------------------------------------------

    def save_hypothesis(
        self,
        analysis_id: int,
        hypothesis: Hypothesis,
        *,
        key: str | None = None,
        reason: str = INITIAL_REASON,
        supporting: Sequence[str] = (),
        contradicting: Sequence[str] = (),
        context: Sequence[str] = (),
    ) -> HypothesisRevision:
        """State a belief, or restate one that already exists.

        With no `key`, identity is `(subject, claim)`: restating the same claim
        about the same subject appends a revision of that belief rather than
        creating a second, indistinguishable one. Pass `key` to control
        identity explicitly, which is what a caller wants when the claim itself
        is being rewritten.
        """
        with self.connect() as connection:
            resolved_key = key
            previous: sqlite3.Row | None = None
            if resolved_key is None:
                previous = connection.execute(
                    """
                    SELECT * FROM hypotheses
                    WHERE analysis_id = ? AND subject = ? AND claim = ?
                    ORDER BY revision DESC, id DESC LIMIT 1
                    """,
                    (analysis_id, hypothesis.subject, hypothesis.claim),
                ).fetchone()
                resolved_key = (
                    str(previous["hypothesis_key"])
                    if previous is not None
                    else self._next_key(connection, analysis_id)
                )
            else:
                previous = self._current_row(connection, analysis_id, resolved_key)

            return self._append_revision(
                connection,
                analysis_id=analysis_id,
                key=resolved_key,
                previous=previous,
                subject=hypothesis.subject,
                claim=hypothesis.claim,
                certainty=hypothesis.certainty,
                status=hypothesis.status,
                confidence=hypothesis.confidence,
                free_text_evidence=tuple(hypothesis.evidence),
                uncertainty=hypothesis.uncertainty,
                reason=reason,
                supporting=supporting,
                contradicting=contradicting,
                context=context,
            )

    def revise_hypothesis(
        self,
        binary_id: int,
        key: str,
        *,
        reason: str,
        claim: str | None = None,
        status: HypothesisStatus | None = None,
        confidence: float | None = None,
        certainty: Certainty | None = None,
        uncertainty: str | None = None,
        supporting: Sequence[str] = (),
        contradicting: Sequence[str] = (),
        context: Sequence[str] = (),
    ) -> HypothesisRevision:
        """Change a belief, preserving what it was before.

        Anything not named keeps its previous value, so a caller that only
        learned something about confidence does not have to restate the claim.
        `reason` is required: a belief that changed without a recorded reason
        is exactly the silent overwrite this model exists to prevent.

        Evidence cited by the previous revision is carried forward, so each
        revision holds the complete basis for that belief at that moment.
        """
        if not reason.strip():
            raise ValueError("a revision must record why the belief changed")
        with self.connect() as connection:
            previous = self._current_row(connection, binary_id, key)
            if previous is None:
                raise KeyError(f"hypothesis {key!r} does not exist for binary {binary_id}")
            return self._append_revision(
                connection,
                analysis_id=binary_id,
                key=key,
                previous=previous,
                subject=str(previous["subject"]),
                claim=previous["claim"] if claim is None else claim,
                certainty=Certainty(previous["certainty"]) if certainty is None else certainty,
                status=HypothesisStatus(previous["status"]) if status is None else status,
                confidence=(float(previous["confidence"]) if confidence is None else confidence),
                free_text_evidence=(),
                uncertainty=previous["uncertainty"] if uncertainty is None else uncertainty,
                reason=reason,
                supporting=supporting,
                contradicting=contradicting,
                context=context,
            )

    def _append_revision(
        self,
        connection: sqlite3.Connection,
        *,
        analysis_id: int,
        key: str,
        previous: sqlite3.Row | None,
        subject: str,
        claim: str,
        certainty: Certainty,
        status: HypothesisStatus,
        confidence: float,
        free_text_evidence: tuple[str, ...],
        uncertainty: str | None,
        reason: str,
        supporting: Sequence[str],
        contradicting: Sequence[str],
        context: Sequence[str],
    ) -> HypothesisRevision:
        # Validate through the domain model so persistence cannot store a
        # belief the in-memory type would reject.
        Hypothesis(
            subject=subject,
            claim=claim,
            certainty=certainty,
            confidence=confidence,
            evidence=free_text_evidence,
            uncertainty=uncertainty,
            status=status,
        )

        stances: list[tuple[int, EvidenceStance]] = []
        for keys, stance in (
            (supporting, EvidenceStance.SUPPORTS),
            (contradicting, EvidenceStance.CONTRADICTS),
            (context, EvidenceStance.CONTEXT),
        ):
            stances.extend(
                (evidence_id, stance)
                for evidence_id in self._resolve_evidence_ids(connection, analysis_id, keys)
            )

        revision = 1 if previous is None else int(previous["revision"]) + 1
        created_at = None if previous is None else str(previous["created_at"])

        # Carry the previous revision's basis forward so every revision holds
        # the complete grounds for the belief it records.
        carried: list[tuple[int, EvidenceStance]] = (
            [] if previous is None else self._revision_links(connection, int(previous["id"]))
        )
        # A stance restated on this revision is the newer judgement and wins;
        # keeping the carried-forward one would silently ignore a caller that
        # just decided the same observation now cuts the other way. Dict order
        # holds the original position, so the basis reads chronologically.
        by_evidence: dict[int, EvidenceStance] = dict(carried)
        for evidence_id, stance in stances:
            by_evidence[evidence_id] = stance
        links = list(by_evidence.items())

        free_text = free_text_evidence
        if not free_text and previous is not None:
            free_text = tuple(json.loads(str(previous["free_text_json"] or "[]")))

        rendered: list[str] = []
        for evidence_id, stance in links:
            row = connection.execute(
                "SELECT evidence_key, summary FROM evidence WHERE id = ?", (evidence_id,)
            ).fetchone()
            rendered.append(_render_evidence(str(row["summary"]), stance, str(row["evidence_key"])))
        evidence_json = json.dumps([*free_text, *rendered])

        cursor = connection.execute(
            """
            INSERT INTO hypotheses
                (analysis_id, hypothesis_key, revision, subject, claim, certainty,
                 status, confidence, evidence_json, free_text_json, uncertainty,
                 change_reason, supersedes_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    COALESCE(?, CURRENT_TIMESTAMP), CURRENT_TIMESTAMP)
            """,
            (
                analysis_id,
                key,
                revision,
                subject,
                claim,
                certainty.value,
                status.value,
                confidence,
                evidence_json,
                json.dumps(list(free_text)),
                uncertainty,
                reason,
                None if previous is None else int(previous["id"]),
                created_at,
            ),
        )
        revision_id = int(cursor.lastrowid or 0)
        for evidence_id, stance in links:
            connection.execute(
                """
                INSERT INTO hypothesis_evidence
                    (hypothesis_revision_id, evidence_id, stance)
                VALUES (?, ?, ?)
                """,
                (revision_id, evidence_id, stance.value),
            )
        row = connection.execute("SELECT * FROM hypotheses WHERE id = ?", (revision_id,)).fetchone()
        assert row is not None
        return self._revision_from_row(row)

    @staticmethod
    def _revision_links(
        connection: sqlite3.Connection, revision_id: int
    ) -> list[tuple[int, EvidenceStance]]:
        rows = connection.execute(
            "SELECT evidence_id, stance FROM hypothesis_evidence "
            "WHERE hypothesis_revision_id = ? ORDER BY id",
            (revision_id,),
        ).fetchall()
        return [(int(row["evidence_id"]), EvidenceStance(row["stance"])) for row in rows]

    @staticmethod
    def _next_key(connection: sqlite3.Connection, analysis_id: int) -> str:
        """The lowest unused `H-n` for this binary.

        Counting existing keys is not enough: a migrated database keys legacy
        rows by their row id, and a gap in those ids would make a count collide
        with a key already in use.
        """
        taken = {
            str(row["hypothesis_key"])
            for row in connection.execute(
                "SELECT DISTINCT hypothesis_key FROM hypotheses WHERE analysis_id = ?",
                (analysis_id,),
            )
        }
        ordinal = 1
        while f"H-{ordinal}" in taken:
            ordinal += 1
        return f"H-{ordinal}"

    @staticmethod
    def _current_row(
        connection: sqlite3.Connection, analysis_id: int, key: str
    ) -> sqlite3.Row | None:
        row: sqlite3.Row | None = connection.execute(
            """
            SELECT * FROM hypotheses
            WHERE analysis_id = ? AND hypothesis_key = ?
            ORDER BY revision DESC LIMIT 1
            """,
            (analysis_id, key),
        ).fetchone()
        return row

    @staticmethod
    def _revision_from_row(row: sqlite3.Row) -> HypothesisRevision:
        return HypothesisRevision(
            id=int(row["id"]),
            binary_id=int(row["analysis_id"]),
            key=str(row["hypothesis_key"]),
            revision=int(row["revision"]),
            subject=str(row["subject"]),
            claim=str(row["claim"]),
            certainty=Certainty(row["certainty"]),
            status=HypothesisStatus(row["status"]),
            confidence=float(row["confidence"]),
            evidence=tuple(json.loads(str(row["evidence_json"]))),
            uncertainty=None if row["uncertainty"] is None else str(row["uncertainty"]),
            change_reason=str(row["change_reason"]),
            supersedes_id=None if row["supersedes_id"] is None else int(row["supersedes_id"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def current_hypothesis(self, binary_id: int, key: str) -> HypothesisRevision | None:
        """What the system believes now, or None if it never believed it."""
        with self.connect() as connection:
            row = self._current_row(connection, binary_id, key)
        return None if row is None else self._revision_from_row(row)

    def hypothesis_history(self, binary_id: int, key: str) -> list[HypothesisRevision]:
        """Every belief state this hypothesis has held, oldest first."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM hypotheses
                WHERE analysis_id = ? AND hypothesis_key = ?
                ORDER BY revision
                """,
                (binary_id, key),
            ).fetchall()
        return [self._revision_from_row(row) for row in rows]

    def current_hypotheses(self, binary_id: int) -> list[HypothesisRevision]:
        with self.connect() as connection:
            rows = connection.execute(
                self._CURRENT_HYPOTHESES_SQL, (binary_id, binary_id)
            ).fetchall()
        return [self._revision_from_row(row) for row in rows]

    _CURRENT_HYPOTHESES_SQL = """
        SELECT h.* FROM hypotheses AS h
        JOIN (
            SELECT analysis_id, hypothesis_key, MAX(revision) AS revision
            FROM hypotheses WHERE analysis_id = ?
            GROUP BY analysis_id, hypothesis_key
        ) AS current
          ON current.analysis_id = h.analysis_id
         AND current.hypothesis_key = h.hypothesis_key
         AND current.revision = h.revision
        WHERE h.analysis_id = ?
        ORDER BY h.confidence DESC, h.id
    """

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    def save_relationship(
        self,
        binary_id: int,
        relationship: Relationship,
        *,
        reason: str = INITIAL_REASON,
        stance: EvidenceStance = EvidenceStance.SUPPORTS,
    ) -> int:
        """Assert a structural relationship, revising rather than overwriting."""
        with self.connect() as connection:
            evidence_ids = self._resolve_evidence_ids(connection, binary_id, relationship.evidence)
            previous = connection.execute(
                """
                SELECT MAX(revision) AS revision FROM relationships
                WHERE binary_id = ? AND subject = ? AND predicate = ? AND object = ?
                """,
                (binary_id, relationship.subject, relationship.predicate, relationship.object),
            ).fetchone()
            revision = 1 if previous["revision"] is None else int(previous["revision"]) + 1
            cursor = connection.execute(
                """
                INSERT INTO relationships
                    (binary_id, subject, predicate, object, confidence, revision, change_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    binary_id,
                    relationship.subject,
                    relationship.predicate,
                    relationship.object,
                    relationship.confidence,
                    revision,
                    reason,
                ),
            )
            relationship_id = int(cursor.lastrowid or 0)
            for evidence_id in evidence_ids:
                connection.execute(
                    """
                    INSERT INTO relationship_evidence (relationship_id, evidence_id, stance)
                    VALUES (?, ?, ?)
                    """,
                    (relationship_id, evidence_id, stance.value),
                )
            return relationship_id

    def current_relationships(self, binary_id: int) -> list[Relationship]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT r.* FROM relationships AS r
                JOIN (
                    SELECT subject, predicate, object, MAX(revision) AS revision
                    FROM relationships WHERE binary_id = ?
                    GROUP BY subject, predicate, object
                ) AS current
                  ON current.subject = r.subject
                 AND current.predicate = r.predicate
                 AND current.object = r.object
                 AND current.revision = r.revision
                WHERE r.binary_id = ?
                ORDER BY r.subject, r.predicate, r.object
                """,
                (binary_id, binary_id),
            ).fetchall()
            return [
                Relationship(
                    subject=str(row["subject"]),
                    predicate=str(row["predicate"]),
                    object=str(row["object"]),
                    confidence=float(row["confidence"]),
                    evidence=tuple(
                        str(item["evidence_key"])
                        for item in connection.execute(
                            """
                            SELECT e.evidence_key FROM relationship_evidence AS link
                            JOIN evidence AS e ON e.id = link.evidence_id
                            WHERE link.relationship_id = ? ORDER BY link.id
                            """,
                            (int(row["id"]),),
                        )
                    ),
                )
                for row in rows
            ]

    def relationship_history(
        self, binary_id: int, subject: str, predicate: str, object: str
    ) -> list[tuple[int, float, str]]:
        """Revision, confidence, and reason for one relationship, oldest first."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT revision, confidence, change_reason FROM relationships
                WHERE binary_id = ? AND subject = ? AND predicate = ? AND object = ?
                ORDER BY revision
                """,
                (binary_id, subject, predicate, object),
            ).fetchall()
        return [
            (int(row["revision"]), float(row["confidence"]), str(row["change_reason"]))
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def report_data(
        self, analysis_id: int
    ) -> tuple[sqlite3.Row, list[sqlite3.Row], list[sqlite3.Row]]:
        """Facts and *current* belief for one binary.

        Superseded revisions are excluded. Returning the whole revision log
        here would make a report show a belief the system has already moved on
        from as though it were still held.
        """
        with self.connect() as connection:
            analysis = connection.execute(
                "SELECT * FROM analyses WHERE id = ?", (analysis_id,)
            ).fetchone()
            if analysis is None:
                raise KeyError(f"analysis {analysis_id} does not exist")
            functions = connection.execute(
                "SELECT * FROM functions WHERE analysis_id = ? ORDER BY address", (analysis_id,)
            ).fetchall()
            hypotheses = connection.execute(
                self._CURRENT_HYPOTHESES_SQL, (analysis_id, analysis_id)
            ).fetchall()
            return analysis, list(functions), list(hypotheses)
