"""Stage 1: Semantic chunking with offset preservation."""

import logging
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from pipeline.config import config
from pipeline.models.chunk import ChunkMetadata
from pipeline.utils.db import Database

logger = logging.getLogger(__name__)


class DocumentChunker:
    """Chunk documents with absolute character offset preservation."""

    def __init__(self, db: Database) -> None:
        """Initialize chunker.

        Args:
            db: Database instance (must be connected via context manager)
        """
        self.db = db

        # Character-based splitter (not token-based to avoid offset bugs)
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            length_function=len,
            is_separator_regex=False,
            separators=["\n\n", "\n", ". ", " ", ""],  # Hierarchical splitting
        )

    def chunk_document(self, document_sha256: str) -> list[int]:
        """Chunk a document and store chunks with absolute offsets.

        Args:
            document_sha256: SHA-256 hash of document to chunk

        Returns:
            List of chunk IDs

        Raises:
            ValueError: If document not found or offsets cannot be computed
        """
        logger.info(f"Chunking document: {document_sha256}")

        # Retrieve document
        doc = self.db.get_document(document_sha256)
        if not doc:
            raise ValueError(f"Document not found: {document_sha256}")

        normalized_text = doc["normalized_text"]
        logger.info(f"Document length: {len(normalized_text)} chars")

        # Split into chunks
        chunks = self.splitter.split_text(normalized_text)
        logger.info(f"Generated {len(chunks)} chunks")

        # Compute absolute offsets for each chunk
        chunk_ids = []
        search_from = 0

        for chunk_index, chunk_text in enumerate(chunks):
            # Find chunk in normalized text starting from last position
            char_start = normalized_text.find(chunk_text, search_from)

            if char_start == -1:
                # This should never happen with character-based splitting
                raise ValueError(
                    f"Chunk {chunk_index} not found in document "
                    f"(searched from position {search_from})"
                )

            char_end = char_start + len(chunk_text)

            # Validate offset
            extracted = normalized_text[char_start:char_end]
            if extracted != chunk_text:
                raise ValueError(
                    f"Offset validation failed for chunk {chunk_index}: "
                    f"expected {len(chunk_text)} chars, got {len(extracted)}"
                )

            # Create chunk metadata
            chunk_metadata = ChunkMetadata(
                document_sha256=document_sha256,
                chunk_index=chunk_index,
                char_start=char_start,
                char_end=char_end,
                chunk_text=chunk_text,
            )

            # Double-check with Pydantic model validator
            if not chunk_metadata.validate_offsets(normalized_text):
                raise ValueError(
                    f"Pydantic validation failed for chunk {chunk_index}"
                )

            # Insert into database
            chunk_dict = chunk_metadata.model_dump()
            chunk_id = self.db.insert_chunk(chunk_dict)
            chunk_ids.append(chunk_id)

            logger.debug(
                f"Chunk {chunk_index}: offset={char_start}:{char_end}, "
                f"length={len(chunk_text)}"
            )

            # Update search position for next chunk (accounting for overlap)
            search_from = char_start + 1

        logger.info(f"Chunked document successfully: {len(chunk_ids)} chunks")
        return chunk_ids


def chunk_main(document_sha256: str, db_path: str) -> list[int]:
    """Main entry point for chunking stage.

    Args:
        document_sha256: SHA-256 hash of document to chunk
        db_path: Path to SQLite database

    Returns:
        List of chunk IDs
    """
    with Database(db_path) as db:
        chunker = DocumentChunker(db)
        return chunker.chunk_document(document_sha256)
