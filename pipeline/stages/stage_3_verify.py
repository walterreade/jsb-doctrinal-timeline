"""Stage 3: Deterministic quote verification."""

import json
import logging
from typing import Any

from pipeline.config import config
from pipeline.models.principle import PrincipleAssertion
from pipeline.utils.db import Database
from pipeline.utils.fuzzy_match import find_best_match

logger = logging.getLogger(__name__)


class QuoteVerifier:
    """Verify extracted quotes against source text."""

    def __init__(self, db: Database) -> None:
        """Initialize verifier.

        Args:
            db: Database instance (must be connected via context manager)
        """
        self.db = db
        self.fuzzy_threshold = config.fuzzy_threshold

    def verify_document(self, document_sha256: str) -> dict[str, Any]:
        """Verify all pending extractions for a document.

        Args:
            document_sha256: Document SHA-256 hash

        Returns:
            Summary dict with verification statistics
        """
        logger.info(f"Verifying extractions for document: {document_sha256}")

        # Get document
        doc = self.db.get_document(document_sha256)
        if not doc:
            raise ValueError(f"Document not found: {document_sha256}")

        normalized_text = doc["normalized_text"]

        # Get all pending extractions (stored in quarantine with reason='pending_verification')
        cursor = self.db.execute(
            """
            SELECT * FROM quarantine
            WHERE document_sha256 = ? AND reason = 'pending_verification'
            """,
            (document_sha256,),
        )

        pending = cursor.fetchall()
        logger.info(f"Found {len(pending)} pending extractions to verify")

        stats = {
            "total": len(pending),
            "verified_exact": 0,
            "verified_fuzzy": 0,
            "quarantined": 0,
        }

        for row in pending:
            try:
                result = self._verify_pending_extraction(row, document_sha256, normalized_text)
                self._update_stats(stats, result)
            except Exception as e:
                logger.error(f"Verification failed for quarantine ID {row['id']}: {e}")
                stats["quarantined"] += 1
                continue

        # Calculate rates
        if stats["total"] > 0:
            stats["verification_rate"] = (
                stats["verified_exact"] + stats["verified_fuzzy"]
            ) / stats["total"]
            stats["quarantine_rate"] = stats["quarantined"] / stats["total"]
        else:
            stats["verification_rate"] = 0.0
            stats["quarantine_rate"] = 0.0

        logger.info(
            f"Verification complete: {stats['verified_exact']} exact, "
            f"{stats['verified_fuzzy']} fuzzy, {stats['quarantined']} quarantined"
        )

        return stats

    def _verify_pending_extraction(
        self, row: Any, document_sha256: str, normalized_text: str
    ) -> dict[str, Any]:
        """Verify a single pending extraction.

        Args:
            row: Database row from quarantine table
            document_sha256: Document SHA-256
            normalized_text: Full document text

        Returns:
            Verification result dict
        """
        principle_data = json.loads(row["raw_json"])
        principle = PrincipleAssertion(**principle_data)

        return self._verify_quote(
            principle=principle,
            chunk_id=row["chunk_id"],
            document_sha256=document_sha256,
            normalized_text=normalized_text,
        )

    def _update_stats(self, stats: dict[str, int], result: dict[str, Any]) -> None:
        """Update verification statistics based on result.

        Args:
            stats: Statistics dict to update
            result: Verification result
        """
        if result["verified"]:
            if result["verification"] == "exact":
                stats["verified_exact"] += 1
            else:
                stats["verified_fuzzy"] += 1
        else:
            stats["quarantined"] += 1

    def _verify_quote(
        self,
        principle: PrincipleAssertion,
        chunk_id: int,
        document_sha256: str,
        normalized_text: str,
    ) -> dict[str, Any]:
        """Verify a single quote against source text.

        Args:
            principle: Extracted principle
            chunk_id: Source chunk ID
            document_sha256: Source document SHA-256
            normalized_text: Full document normalized text

        Returns:
            Dict with verification result and metadata
        """
        quote = principle.verbatim_quote

        # Get chunk for constrained search
        cursor = self.db.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,))
        chunk_row = cursor.fetchone()

        if not chunk_row:
            logger.warning(f"Chunk {chunk_id} not found for verification")
            return {"verified": False, "reason": "chunk_not_found"}

        chunk = dict(chunk_row)
        chunk_text = chunk["chunk_text"]
        chunk_start = chunk["char_start"]

        # Try exact match first (in chunk)
        pos = chunk_text.find(quote)

        if pos != -1:
            # Exact match found
            abs_start = chunk_start + pos
            abs_end = abs_start + len(quote)
            return self._store_and_return_match(
                principle=principle,
                chunk_id=chunk_id,
                document_sha256=document_sha256,
                abs_start=abs_start,
                abs_end=abs_end,
                verification="exact",
                fuzzy_score=None,
                quote=quote,
            )

        # Try fuzzy match (constrained to chunk)
        match_result = find_best_match(quote, chunk_text, self.fuzzy_threshold)

        if match_result:
            # Fuzzy match found
            abs_start = chunk_start + match_result.char_start
            abs_end = chunk_start + match_result.char_end
            return self._store_and_return_match(
                principle=principle,
                chunk_id=chunk_id,
                document_sha256=document_sha256,
                abs_start=abs_start,
                abs_end=abs_end,
                verification="fuzzy",
                fuzzy_score=match_result.score,
                quote=quote,
            )

        # No match found - quarantine
        logger.warning(
            f"Quote not verified: \"{quote[:100]}...\" "
            f"(chunk {chunk_id}, searched {len(chunk_text)} chars)"
        )

        # Keep in quarantine with updated reason
        self.db.execute(
            """
            UPDATE quarantine
            SET reason = 'quote_not_found'
            WHERE chunk_id = ? AND attempted_quote = ?
            """,
            (chunk_id, quote),
        )

        return {"verified": False, "reason": "quote_not_found"}

    def _store_and_return_match(
        self,
        principle: PrincipleAssertion,
        chunk_id: int,
        document_sha256: str,
        abs_start: int,
        abs_end: int,
        verification: str,
        fuzzy_score: float | None,
        quote: str,
    ) -> dict[str, Any]:
        """Store verified assertion and return match result.

        Args:
            principle: Verified principle
            chunk_id: Source chunk ID
            document_sha256: Source document SHA-256
            abs_start: Absolute character start offset
            abs_end: Absolute character end offset
            verification: 'exact' or 'fuzzy'
            fuzzy_score: Fuzzy match score (None if exact)
            quote: Quote text for logging

        Returns:
            Dict with verification result
        """
        # Store in database
        assertion_data = {
            "document_sha256": document_sha256,
            "chunk_id": chunk_id,
            "principle_statement": principle.principle_statement,
            "verbatim_quote": principle.verbatim_quote,
            "char_start": abs_start,
            "char_end": abs_end,
            "explicit_or_inferred": principle.explicit_or_inferred,
            "verification": verification,
            "fuzzy_score": fuzzy_score,
            "confidence": principle.confidence,
            "audience": principle.audience_hint,
            "reasoning": principle.reasoning,
        }

        self.db.insert_assertion(assertion_data)

        # Remove from quarantine
        self.db.execute(
            """
            DELETE FROM quarantine
            WHERE chunk_id = ? AND attempted_quote = ? AND reason = 'pending_verification'
            """,
            (chunk_id, principle.verbatim_quote),
        )

        # Log match
        if verification == "exact":
            logger.debug(
                f"Exact match: offset={abs_start}:{abs_end}, "
                f'quote="{quote[:50]}..."'
            )
        else:
            logger.debug(
                f"Fuzzy match: score={fuzzy_score:.1f}, "
                f"offset={abs_start}:{abs_end}, "
                f'quote="{quote[:50]}..."'
            )

        # Return result
        result = {
            "verified": True,
            "verification": verification,
            "char_start": abs_start,
            "char_end": abs_end,
        }
        if fuzzy_score is not None:
            result["fuzzy_score"] = fuzzy_score

        return result


def verify_main(document_sha256: str, db_path: str) -> dict[str, Any]:
    """Main entry point for verification stage.

    Args:
        document_sha256: Document SHA-256 hash
        db_path: Path to SQLite database

    Returns:
        Summary dict with verification statistics
    """
    with Database(db_path) as db:
        verifier = QuoteVerifier(db)
        return verifier.verify_document(document_sha256)
