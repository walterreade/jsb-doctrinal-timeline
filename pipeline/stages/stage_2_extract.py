"""Stage 2: LLM-based principle extraction."""

import asyncio
import json
import logging
from typing import Any

from pipeline.llm.gemini_client import GeminiClient
from pipeline.models.principle import PrincipleAssertion
from pipeline.utils.db import Database

logger = logging.getLogger(__name__)


class PrincipleExtractor:
    """Extract principles from chunks using LLM."""

    def __init__(self, db: Database) -> None:
        """Initialize extractor.

        Args:
            db: Database instance (must be connected via context manager)
        """
        self.db = db
        self.client = GeminiClient()

    def extract_from_chunk(
        self, chunk_id: int
    ) -> tuple[list[PrincipleAssertion], dict[str, Any]]:
        """Extract principles from a single chunk.

        Args:
            chunk_id: Chunk ID to process

        Returns:
            Tuple of (extracted principles, chunk metadata)

        Raises:
            ValueError: If chunk not found
        """
        # Fetch chunk
        cursor = self.db.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,))
        chunk_row = cursor.fetchone()

        if not chunk_row:
            raise ValueError(f"Chunk not found: {chunk_id}")

        chunk = dict(chunk_row)

        # Fetch document for context
        doc = self.db.get_document(chunk["document_sha256"])
        if not doc:
            raise ValueError(f"Document not found: {chunk['document_sha256']}")

        logger.info(f"Extracting from chunk {chunk_id} ({len(chunk['chunk_text'])} chars)")

        # Extract principles
        principles = self.client.extract_principles(
            chunk_text=chunk["chunk_text"],
            document_context={
                "title": doc["title"],
                "recorder": doc["recorder"],
                "event_date_edtf": doc["event_date_edtf"],
            },
        )

        logger.info(f"Extracted {len(principles)} principles from chunk {chunk_id}")

        return principles, chunk

    def extract_from_document(self, document_sha256: str) -> dict[str, Any]:
        """Extract principles from all chunks of a document.

        Args:
            document_sha256: Document SHA-256 hash

        Returns:
            Summary dict with counts and statistics
        """
        logger.info(f"Extracting principles from document: {document_sha256}")

        chunks = self.db.get_chunks(document_sha256)
        logger.info(f"Processing {len(chunks)} chunks")

        total_extracted = 0
        total_empty = 0

        for chunk in chunks:
            try:
                extracted_count = self._extract_and_store_chunk(chunk, document_sha256)
                if extracted_count > 0:
                    total_extracted += extracted_count
                else:
                    total_empty += 1
            except Exception as e:
                logger.error(f"Failed to extract from chunk {chunk['id']}: {e}")
                continue

        summary = {
            "document_sha256": document_sha256,
            "total_chunks": len(chunks),
            "chunks_processed": len(chunks),
            "total_extracted": total_extracted,
            "empty_chunks": total_empty,
        }

        logger.info(
            f"Extraction complete: {total_extracted} raw principles from {len(chunks)} chunks"
        )

        return summary

    def _extract_and_store_chunk(self, chunk: dict, document_sha256: str) -> int:
        """Extract principles from a chunk and store them.

        Args:
            chunk: Chunk dict
            document_sha256: Document SHA-256 hash

        Returns:
            Number of principles extracted
        """
        chunk_id = chunk["id"]
        principles, _ = self.extract_from_chunk(chunk_id)

        if principles:
            logger.info(
                f"Chunk {chunk_id}: {len(principles)} principles (raw, unverified)"
            )
            for principle in principles:
                self._store_raw_extraction(
                    chunk_id=chunk_id,
                    document_sha256=document_sha256,
                    principle=principle,
                )
        else:
            logger.debug(f"Chunk {chunk_id}: no principles found")

        return len(principles)

    def _store_raw_extraction(
        self, chunk_id: int, document_sha256: str, principle: PrincipleAssertion
    ) -> None:
        """Store raw extraction temporarily for verification stage.

        For now, we'll store in a temporary table. In a production system,
        this might be a separate staging table or in-memory cache.

        Args:
            chunk_id: Source chunk ID
            document_sha256: Source document SHA-256
            principle: Extracted principle (unverified)
        """
        # Store as JSON in quarantine table temporarily
        # (will be moved to assertions table after verification)
        raw_json = principle.model_dump_json()

        self.db.execute(
            """
            INSERT INTO quarantine (
                document_sha256, chunk_id, raw_json,
                principle_statement, attempted_quote, reason
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                document_sha256,
                chunk_id,
                raw_json,
                principle.principle_statement,
                principle.verbatim_quote,
                "pending_verification",
            ),
        )


def extract_main(document_sha256: str, db_path: str) -> dict[str, Any]:
    """Main entry point for extraction stage.

    Args:
        document_sha256: Document SHA-256 hash
        db_path: Path to SQLite database

    Returns:
        Summary dict with extraction statistics
    """
    with Database(db_path) as db:
        extractor = PrincipleExtractor(db)
        return extractor.extract_from_document(document_sha256)
