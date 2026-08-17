"""SQLite persistence for investigation facts and hypotheses."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .models import BinaryProfile, FunctionRecord, Hypothesis

SCHEMA = """
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


class InvestigationStore:
    def __init__(self, database_path: str | Path):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

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
                    profile.sha256, profile.filename, profile.path, profile.size,
                    profile.sha1, profile.md5, profile.entropy, profile.processor,
                    profile.byte_order, profile_json,
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
                (analysis_id, function.address, function.name, function.size, function.decompilation),
            )

    def save_hypothesis(self, analysis_id: int, hypothesis: Hypothesis) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO hypotheses
                    (analysis_id, subject, claim, certainty, confidence,
                     evidence_json, uncertainty)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_id, hypothesis.subject, hypothesis.claim,
                    hypothesis.certainty.value, hypothesis.confidence,
                    json.dumps(hypothesis.evidence), hypothesis.uncertainty,
                ),
            )

    def report_data(self, analysis_id: int) -> tuple[sqlite3.Row, list[sqlite3.Row], list[sqlite3.Row]]:
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
                "SELECT * FROM hypotheses WHERE analysis_id = ? ORDER BY confidence DESC, id",
                (analysis_id,),
            ).fetchall()
            return analysis, list(functions), list(hypotheses)

