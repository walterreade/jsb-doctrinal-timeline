"""Main CLI entry point for the extraction pipeline."""

import logging
import sys
from pathlib import Path
from typing import Callable

import structlog

from pipeline.audit.stats import compute_comprehensive_stats, print_comprehensive_stats
from pipeline.config import config
from pipeline.stages.stage_0_ingest import ingest_main
from pipeline.stages.stage_1_chunk import chunk_main
from pipeline.stages.stage_2_extract import extract_main
from pipeline.stages.stage_3_verify import verify_main
from pipeline.utils.db import Database


def setup_logging() -> None:
    """Configure structured logging."""
    config.log_dir.mkdir(parents=True, exist_ok=True)

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(config.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def init_database(schema_path: Path = Path("scripts/setup_db.sql")) -> None:
    """Initialize database schema.

    Args:
        schema_path: Path to SQL schema file
    """
    print(f"Initializing database: {config.db_path}")

    if not schema_path.exists():
        print(f"ERROR: Schema file not found: {schema_path}", file=sys.stderr)
        sys.exit(1)

    with Database(config.db_path) as db:
        db.initialize_schema(schema_path)

    print(f"✓ Database initialized successfully")


def _run_with_error_handling(func: Callable[[], None]) -> None:
    """Run a command function with standard error handling.

    Args:
        func: Function to run
    """
    try:
        func()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def ingest_command(xml_path: str) -> None:
    """Ingest a TEI-XML document.

    Args:
        xml_path: Path to XML file
    """
    def _run():
        setup_logging()
        print(f"Ingesting: {xml_path}")

        sha256 = ingest_main(
            xml_path=xml_path,
            db_path=str(config.db_path),
            cas_dir=str(config.cas_dir),
        )
        print(f"✓ Document ingested: {sha256}")

        # Show stats
        with Database(config.db_path) as db:
            stats = db.get_stats()
            print(f"\nDatabase stats:")
            print(f"  Documents: {stats['documents']}")
            print(f"  Chunks: {stats['chunks']}")
            print(f"  Assertions: {stats['assertions_total']}")

    _run_with_error_handling(_run)


def chunk_command(document_sha256: str) -> None:
    """Chunk a document.

    Args:
        document_sha256: SHA-256 hash of document to chunk
    """
    def _run():
        setup_logging()
        print(f"Chunking document: {document_sha256}")

        chunk_ids = chunk_main(
            document_sha256=document_sha256,
            db_path=str(config.db_path),
        )
        print(f"✓ Document chunked: {len(chunk_ids)} chunks")

        # Show sample chunk
        with Database(config.db_path) as db:
            chunks = db.get_chunks(document_sha256)
            if chunks:
                first = chunks[0]
                print(f"\nSample chunk (#{first['chunk_index']}):")
                print(f"  Offset: {first['char_start']}:{first['char_end']}")
                print(f"  Length: {len(first['chunk_text'])} chars")
                preview = first['chunk_text'][:200] + "..." if len(first['chunk_text']) > 200 else first['chunk_text']
                print(f"  Preview: {preview}")

    _run_with_error_handling(_run)


def extract_command(document_sha256: str) -> None:
    """Extract principles from a document.

    Args:
        document_sha256: SHA-256 hash of document to extract from
    """
    def _run():
        setup_logging()
        print(f"Extracting principles from document: {document_sha256}")
        print("(This will use Gemini API - may take several minutes)")

        summary = extract_main(
            document_sha256=document_sha256,
            db_path=str(config.db_path),
        )

        print(f"\n✓ Extraction complete:")
        print(f"  Total chunks: {summary['total_chunks']}")
        print(f"  Chunks processed: {summary['chunks_processed']}")
        print(f"  Principles extracted: {summary['total_extracted']} (unverified)")
        print(f"  Empty chunks: {summary['empty_chunks']}")
        print(f"\nNext step: Run verification to validate quotes")

    _run_with_error_handling(_run)


def verify_command(document_sha256: str) -> None:
    """Verify extracted principles.

    Args:
        document_sha256: SHA-256 hash of document to verify
    """
    def _run():
        setup_logging()
        print(f"Verifying principles for document: {document_sha256}")

        summary = verify_main(
            document_sha256=document_sha256,
            db_path=str(config.db_path),
        )

        print(f"\n✓ Verification complete:")
        print(f"  Total extractions: {summary['total']}")
        print(f"  Verified (exact): {summary['verified_exact']}")
        print(f"  Verified (fuzzy): {summary['verified_fuzzy']}")
        print(f"  Quarantined: {summary['quarantined']}")
        print(f"\n  Verification rate: {summary['verification_rate']:.1%}")
        print(f"  Quarantine rate: {summary['quarantine_rate']:.1%}")

        # Check success criteria
        if summary['verification_rate'] >= 0.95:
            print(f"\n✓ SUCCESS: Verification rate meets ≥95% target")
        else:
            print(f"\n⚠ WARNING: Verification rate below 95% target")

        if summary['quarantine_rate'] <= 0.10:
            print(f"✓ SUCCESS: Quarantine rate meets ≤10% target")
        else:
            print(f"⚠ WARNING: Quarantine rate above 10% target")

    _run_with_error_handling(_run)


def stats_command(comprehensive: bool = False) -> None:
    """Display pipeline statistics.

    Args:
        comprehensive: Show comprehensive stats (default: basic)
    """
    with Database(config.db_path) as db:
        if comprehensive:
            stats = compute_comprehensive_stats(db)
            print_comprehensive_stats(stats)
        else:
            stats = db.get_stats()
            print("\n=== Pipeline Statistics ===\n")
            print(f"Documents:     {stats['documents']}")
            print(f"Chunks:        {stats['chunks']}")
            print(f"Assertions:    {stats['assertions_total']}")
            print(f"  - Exact:     {stats['assertions_by_verification'].get('exact', 0)}")
            print(f"  - Fuzzy:     {stats['assertions_by_verification'].get('fuzzy', 0)}")
            print(f"Quarantined:   {stats['quarantined']}")
            print(f"\nVerification:  {stats['verification_rate']:.1%}")
            print(f"Quarantine:    {stats['quarantine_rate']:.1%}")


def _handle_init(args: list[str]) -> None:
    """Handle init command."""
    init_database()


def _handle_ingest(args: list[str]) -> None:
    """Handle ingest command."""
    if len(args) < 1:
        print("ERROR: Missing XML path", file=sys.stderr)
        sys.exit(1)
    ingest_command(args[0])


def _handle_chunk(args: list[str]) -> None:
    """Handle chunk command."""
    if len(args) < 1:
        print("ERROR: Missing document SHA-256", file=sys.stderr)
        sys.exit(1)
    chunk_command(args[0])


def _handle_extract(args: list[str]) -> None:
    """Handle extract command."""
    if len(args) < 1:
        print("ERROR: Missing document SHA-256", file=sys.stderr)
        sys.exit(1)
    extract_command(args[0])


def _handle_verify(args: list[str]) -> None:
    """Handle verify command."""
    if len(args) < 1:
        print("ERROR: Missing document SHA-256", file=sys.stderr)
        sys.exit(1)
    verify_command(args[0])


def _handle_stats(args: list[str]) -> None:
    """Handle stats command."""
    comprehensive = "--comprehensive" in args
    stats_command(comprehensive)


# Command registry: maps command names to handler functions
COMMANDS: dict[str, Callable[[list[str]], None]] = {
    "init": _handle_init,
    "ingest": _handle_ingest,
    "chunk": _handle_chunk,
    "extract": _handle_extract,
    "verify": _handle_verify,
    "stats": _handle_stats,
}


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m pipeline.main init")
        print("  python -m pipeline.main ingest <xml_path>")
        print("  python -m pipeline.main chunk <document_sha256>")
        print("  python -m pipeline.main extract <document_sha256>")
        print("  python -m pipeline.main verify <document_sha256>")
        print("  python -m pipeline.main stats [--comprehensive]")
        sys.exit(1)

    command = sys.argv[1]
    handler = COMMANDS.get(command)

    if handler is None:
        print(f"ERROR: Unknown command: {command}", file=sys.stderr)
        sys.exit(1)

    handler(sys.argv[2:])


if __name__ == "__main__":
    main()
