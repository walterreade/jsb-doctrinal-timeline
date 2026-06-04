"""SQLite database utilities."""

import sqlite3
from pathlib import Path
from typing import Any


class Database:
    """SQLite database manager for the extraction pipeline."""

    def __init__(self, db_path: Path | str) -> None:
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: sqlite3.Connection | None = None

    def __enter__(self) -> "Database":
        """Context manager entry."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging for better performance
        self.conn.row_factory = sqlite3.Row
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()
            self.conn = None

    def initialize_schema(self, schema_path: Path | str) -> None:
        """Initialize database schema from SQL file.

        Args:
            schema_path: Path to SQL schema file
        """
        if not self.conn:
            raise RuntimeError("Database not connected (use context manager)")

        schema_sql = Path(schema_path).read_text(encoding="utf-8")
        self.conn.executescript(schema_sql)
        self.conn.commit()

    def execute(self, query: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> sqlite3.Cursor:
        """Execute a SQL query.

        Args:
            query: SQL query string
            params: Query parameters (tuple or dict)

        Returns:
            Cursor with results
        """
        if not self.conn:
            raise RuntimeError("Database not connected (use context manager)")
        return self.conn.execute(query, params)

    def insert_document(self, metadata: dict[str, Any]) -> str:
        """Insert a document record.

        Args:
            metadata: Document metadata dict

        Returns:
            SHA-256 hash of inserted document
        """
        query = """
            INSERT INTO documents (
                sha256, title, source_type, provenance_class, recorder,
                event_date_edtf, event_date_earliest, event_date_latest,
                record_date_edtf, record_date_earliest, record_date_latest,
                repository, citation, normalized_text, normalized_text_sha256
            ) VALUES (
                :sha256, :title, :source_type, :provenance_class, :recorder,
                :event_date_edtf, :event_date_earliest, :event_date_latest,
                :record_date_edtf, :record_date_earliest, :record_date_latest,
                :repository, :citation, :normalized_text, :normalized_text_sha256
            )
        """
        self.execute(query, metadata)
        return metadata["sha256"]

    def insert_chunk(self, chunk_data: dict[str, Any]) -> int:
        """Insert a chunk record.

        Args:
            chunk_data: Chunk metadata dict

        Returns:
            Chunk ID (autoincrement)
        """
        query = """
            INSERT INTO chunks (
                document_sha256, chunk_index, char_start, char_end, chunk_text
            ) VALUES (
                :document_sha256, :chunk_index, :char_start, :char_end, :chunk_text
            )
        """
        cursor = self.execute(query, chunk_data)
        chunk_id = cursor.lastrowid
        if chunk_id is None:
            raise RuntimeError("Failed to retrieve chunk ID")
        return chunk_id

    def insert_assertion(self, assertion_data: dict[str, Any]) -> int:
        """Insert a verified assertion.

        Args:
            assertion_data: Assertion data dict

        Returns:
            Assertion ID (autoincrement)
        """
        query = """
            INSERT INTO assertions (
                document_sha256, chunk_id, principle_statement, verbatim_quote,
                char_start, char_end, explicit_or_inferred, verification,
                fuzzy_score, confidence, audience, reasoning
            ) VALUES (
                :document_sha256, :chunk_id, :principle_statement, :verbatim_quote,
                :char_start, :char_end, :explicit_or_inferred, :verification,
                :fuzzy_score, :confidence, :audience, :reasoning
            )
        """
        cursor = self.execute(query, assertion_data)
        assertion_id = cursor.lastrowid
        if assertion_id is None:
            raise RuntimeError("Failed to retrieve assertion ID")
        return assertion_id

    def insert_quarantine(self, quarantine_data: dict[str, Any]) -> int:
        """Insert a quarantined (unverifiable) extraction.

        Args:
            quarantine_data: Quarantine record dict

        Returns:
            Quarantine ID (autoincrement)
        """
        query = """
            INSERT INTO quarantine (
                document_sha256, chunk_id, raw_json, principle_statement,
                attempted_quote, reason
            ) VALUES (
                :document_sha256, :chunk_id, :raw_json, :principle_statement,
                :attempted_quote, :reason
            )
        """
        cursor = self.execute(query, quarantine_data)
        quarantine_id = cursor.lastrowid
        if quarantine_id is None:
            raise RuntimeError("Failed to retrieve quarantine ID")
        return quarantine_id

    def get_document(self, sha256: str) -> dict[str, Any] | None:
        """Retrieve document by SHA-256.

        Args:
            sha256: Document SHA-256 hash

        Returns:
            Document dict or None if not found
        """
        query = "SELECT * FROM documents WHERE sha256 = ?"
        cursor = self.execute(query, (sha256,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_chunks(self, document_sha256: str) -> list[dict[str, Any]]:
        """Get all chunks for a document.

        Args:
            document_sha256: Document SHA-256 hash

        Returns:
            List of chunk dicts
        """
        query = """
            SELECT * FROM chunks
            WHERE document_sha256 = ?
            ORDER BY chunk_index
        """
        cursor = self.execute(query, (document_sha256,))
        return [dict(row) for row in cursor.fetchall()]

    def _get_count(self, query: str) -> int:
        """Execute count query and return count value.

        Args:
            query: SQL query that returns a 'count' column

        Returns:
            Count value (0 if no results)
        """
        cursor = self.execute(query)
        row = cursor.fetchone()
        return row["count"] if row else 0

    def _safe_divide(self, numerator: float, denominator: float) -> float:
        """Safely divide two numbers, returning 0.0 if denominator is 0.

        Args:
            numerator: Numerator
            denominator: Denominator

        Returns:
            Division result or 0.0
        """
        return numerator / denominator if denominator > 0 else 0.0

    def get_stats(self) -> dict[str, Any]:
        """Get pipeline statistics.

        Returns:
            Stats dict with counts and metrics
        """
        stats = {}

        # Document and chunk counts
        stats["documents"] = self._get_count("SELECT COUNT(*) as count FROM documents")
        stats["chunks"] = self._get_count("SELECT COUNT(*) as count FROM chunks")

        # Assertion count by verification type
        cursor = self.execute("""
            SELECT verification, COUNT(*) as count
            FROM assertions
            GROUP BY verification
        """)
        stats["assertions_by_verification"] = {row["verification"]: row["count"] for row in cursor}

        # Total assertions
        stats["assertions_total"] = sum(stats["assertions_by_verification"].values())

        # Quarantine count
        stats["quarantined"] = self._get_count("SELECT COUNT(*) as count FROM quarantine")

        # Verification rate
        exact = stats["assertions_by_verification"].get("exact", 0)
        fuzzy = stats["assertions_by_verification"].get("fuzzy", 0)
        stats["verification_rate"] = self._safe_divide(
            exact + fuzzy, stats["assertions_total"]
        )

        # Quarantine rate
        total_extractions = stats["assertions_total"] + stats["quarantined"]
        stats["quarantine_rate"] = self._safe_divide(
            stats["quarantined"], total_extractions
        )

        return stats
