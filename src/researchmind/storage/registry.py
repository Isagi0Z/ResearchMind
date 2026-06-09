"""SQLite-backed registry for tracking processed papers and detecting duplicates.

Provides persistent storage of SRO metadata so the pipeline can skip
already-processed PDFs and users can query their processed-paper catalogue.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from researchmind.models.sro import StructuredResearchObject

logger = logging.getLogger(__name__)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS papers (
    sro_id             TEXT    PRIMARY KEY,
    sha256             TEXT    UNIQUE NOT NULL,
    title              TEXT    NOT NULL,
    created_at         TEXT    NOT NULL,
    overall_confidence REAL    NOT NULL,
    extraction_route   TEXT    NOT NULL,
    requires_review    INTEGER NOT NULL DEFAULT 0,
    json_path          TEXT    NOT NULL
);
"""

_INSERT_SQL = """
INSERT INTO papers (
    sro_id, sha256, title, created_at,
    overall_confidence, extraction_route,
    requires_review, json_path
) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
"""

_FIND_DUPLICATE_SQL = "SELECT sro_id FROM papers WHERE sha256 = ?;"
_GET_PAPER_SQL = "SELECT * FROM papers WHERE sro_id = ?;"

# Column names in SELECT * order (matches CREATE TABLE declaration)
_COLUMNS = (
    "sro_id",
    "sha256",
    "title",
    "created_at",
    "overall_confidence",
    "extraction_route",
    "requires_review",
    "json_path",
)


class PaperRegistry:
    """Persistent registry of all papers processed by the ingestion pipeline.

    Uses a single SQLite database file.  Thread-safe for single-writer /
    multiple-reader workloads (the default SQLite behaviour).
    """

    def __init__(self, db_path: str) -> None:
        """Initialise the registry, creating the database and table if needed.

        Args:
            db_path: Filesystem path for the SQLite database file.
        """
        self._db_path = db_path

        # Ensure parent directory exists
        parent = Path(db_path).parent
        parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute(_CREATE_TABLE_SQL)
        self._conn.commit()
        logger.info("Paper registry initialised at %s", db_path)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def find_duplicate(self, sha256: str) -> str | None:
        """Check whether a PDF with the given SHA-256 hash has already been processed.

        Args:
            sha256: Lowercase hex-encoded SHA-256 digest of the PDF file.

        Returns:
            The ``sro_id`` of the existing record, or ``None`` if no match.
        """
        cursor = self._conn.execute(_FIND_DUPLICATE_SQL, (sha256,))
        row = cursor.fetchone()
        if row is not None:
            logger.debug("Duplicate detected for sha256=%s → sro_id=%s", sha256, row[0])
            return row[0]
        return None

    def register(self, sro: StructuredResearchObject, json_path: str) -> None:
        """Insert a new paper record into the registry.

        Args:
            sro: The fully assembled Structured Research Object.
            json_path: Filesystem path where the serialised SRO JSON was saved.

        Raises:
            sqlite3.IntegrityError: If the ``sro_id`` or ``sha256`` already
                exists (callers should use :meth:`find_duplicate` first).
        """
        try:
            self._conn.execute(
                _INSERT_SQL,
                (
                    sro.meta.sro_id,
                    sro.meta.source_file.sha256,
                    sro.header.title,
                    sro.meta.created_at.isoformat(),
                    sro.quality.overall_confidence,
                    sro.meta.extraction_route.value,
                    int(sro.quality.requires_manual_review),
                    json_path,
                ),
            )
            self._conn.commit()
            logger.info(
                "Registered paper sro_id=%s title='%s'",
                sro.meta.sro_id,
                sro.header.title[:80],
            )
        except sqlite3.IntegrityError:
            logger.warning(
                "Paper already registered (sro_id=%s, sha256=%s)",
                sro.meta.sro_id,
                sro.meta.source_file.sha256,
            )
            raise

    def list_papers(self, min_confidence: float = 0.0) -> list[dict[str, Any]]:
        """Return all registered papers matching the minimum confidence threshold.

        Args:
            min_confidence: Only return papers whose ``overall_confidence``
                is ≥ this value.  Defaults to ``0.0`` (all papers).

        Returns:
            A list of dicts, each keyed by column name.
        """
        cursor = self._conn.execute(
            "SELECT * FROM papers WHERE overall_confidence >= ? ORDER BY created_at DESC;",
            (min_confidence,),
        )
        rows = cursor.fetchall()
        return [dict(zip(_COLUMNS, row)) for row in rows]

    def get_paper(self, sro_id: str) -> dict[str, Any] | None:
        """Retrieve a single paper record by its SRO ID.

        Args:
            sro_id: The unique identifier of the Structured Research Object.

        Returns:
            A dict keyed by column name, or ``None`` if not found.
        """
        cursor = self._conn.execute(_GET_PAPER_SQL, (sro_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(zip(_COLUMNS, row))

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()
        logger.debug("Registry connection closed.")

    def __enter__(self) -> "PaperRegistry":
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        self.close()
