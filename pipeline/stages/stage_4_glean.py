"""Stage 4: Glean pass — find principles missed by initial extraction."""

import json
import logging
from typing import Any

from pipeline.llm.gemini_client import GeminiClient
from pipeline.models.principle import PrincipleAssertion
from pipeline.utils.db import Database

logger = logging.getLogger(__name__)


class PrincipleGleaner:
    """Re-analyze chunks to find principles missed by the first extraction pass."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.client = GeminiClient()

    def glean_from_document(self, document_sha256: str) -> dict[str, Any]:
        """Run a glean pass over all chunks of a document.

        Args:
            document_sha256: Document SHA-256 hash

        Returns:
            Summary dict with counts
        """
        doc = self.db.get_document(document_sha256)
        if not doc:
            raise ValueError(f"Document not found: {document_sha256}")

        document_context = {
            "title": doc["title"],
            "recorder": doc["recorder"],
            "event_date_edtf": doc["event_date_edtf"],
        }

        chunks = self.db.get_chunks(document_sha256)
        logger.info(f"Gleaning {len(chunks)} chunks for document {document_sha256}")

        total_new = 0
        chunks_with_new = 0

        for chunk in chunks:
            chunk_id = chunk["id"]

            existing = self._get_existing_principles(chunk_id)
            if not existing:
                logger.debug(f"Chunk {chunk_id}: no existing principles, skipping glean")
                continue

            try:
                new_principles = self.client.glean_principles(
                    chunk_text=chunk["chunk_text"],
                    existing_principles=existing,
                    document_context=document_context,
                )
            except Exception as e:
                logger.error(f"Glean failed for chunk {chunk_id}: {e}")
                continue

            if new_principles:
                chunks_with_new += 1
                total_new += len(new_principles)
                logger.info(f"Chunk {chunk_id}: {len(new_principles)} new principles")

                for principle in new_principles:
                    self._store_raw_extraction(chunk_id, document_sha256, principle)
            else:
                logger.debug(f"Chunk {chunk_id}: no new principles")

        return {
            "document_sha256": document_sha256,
            "total_chunks": len(chunks),
            "chunks_with_existing": sum(1 for c in chunks if self._get_existing_principles(c["id"])),
            "chunks_with_new": chunks_with_new,
            "total_new": total_new,
        }

    def _get_existing_principles(self, chunk_id: int) -> list[dict[str, str]]:
        cursor = self.db.execute(
            "SELECT principle_statement, verbatim_quote FROM assertions WHERE chunk_id = ?",
            (chunk_id,),
        )
        return [
            {"principle": r["principle_statement"], "quote": r["verbatim_quote"]}
            for r in cursor.fetchall()
        ]

    def _store_raw_extraction(
        self, chunk_id: int, document_sha256: str, principle: PrincipleAssertion
    ) -> None:
        raw_json = principle.model_dump_json()
        self.db.execute(
            """INSERT INTO quarantine (
                document_sha256, chunk_id, raw_json,
                principle_statement, attempted_quote, reason
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                document_sha256,
                chunk_id,
                raw_json,
                principle.principle_statement,
                principle.verbatim_quote,
                "pending_verification",
            ),
        )


def glean_main(document_sha256: str, db_path: str) -> dict[str, Any]:
    """Main entry point for glean stage.

    Args:
        document_sha256: Document SHA-256 hash
        db_path: Path to SQLite database

    Returns:
        Summary dict with glean statistics
    """
    with Database(db_path) as db:
        gleaner = PrincipleGleaner(db)
        return gleaner.glean_from_document(document_sha256)
