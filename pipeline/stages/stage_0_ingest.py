"""Stage 0: Document ingest, TEI parsing, and normalization."""

import logging
from pathlib import Path

from pipeline.models.document import DocumentMetadata
from pipeline.utils.cas import ContentAddressableStore
from pipeline.utils.db import Database
from pipeline.utils.tei_parser import TEIParser

logger = logging.getLogger(__name__)


class DocumentIngestor:
    """Ingest TEI-XML documents into the pipeline."""

    def __init__(self, db: Database, cas_dir: Path | str) -> None:
        """Initialize ingestor.

        Args:
            db: Database instance (must be connected via context manager)
            cas_dir: Content-addressable storage directory
        """
        self.db = db
        self.cas = ContentAddressableStore(cas_dir)

    def ingest_document(self, xml_path: Path | str) -> str:
        """Ingest a TEI-XML document.

        Process:
        1. Parse TEI-XML with lxml
        2. Extract metadata from teiHeader
        3. Generate clear text (strip diplomatic markup)
        4. Store raw XML in CAS
        5. Insert document record with frozen normalized text

        Args:
            xml_path: Path to TEI-XML file

        Returns:
            SHA-256 hash of ingested document

        Raises:
            FileNotFoundError: If XML file doesn't exist
        """
        xml_path = Path(xml_path)
        if not xml_path.exists():
            raise FileNotFoundError(f"XML file not found: {xml_path}")

        logger.info(f"Ingesting document: {xml_path}")

        # Read raw XML bytes
        raw_xml = xml_path.read_bytes()

        # Store raw XML in CAS
        xml_sha256 = self.cas.store(raw_xml)
        logger.debug(f"Stored raw XML in CAS: {xml_sha256}")

        # Parse TEI-XML
        parser = TEIParser(str(xml_path))

        # Extract metadata
        metadata_dict = parser.extract_metadata()
        logger.debug(f"Extracted metadata: {metadata_dict}")

        # Generate clear text
        normalized_text = parser.generate_clear_text()
        logger.info(f"Generated clear text: {len(normalized_text)} chars")

        # Hash normalized text (frozen after this point)
        normalized_text_sha256 = self.cas.compute_hash(normalized_text.encode("utf-8"))

        # Build DocumentMetadata model
        metadata = DocumentMetadata(
            sha256=xml_sha256,
            title=metadata_dict["title"],
            source_type=metadata_dict["source_type"],
            provenance_class=metadata_dict["provenance_class"],
            recorder=metadata_dict.get("recorder"),
            event_date_edtf=metadata_dict.get("doc_date_min"),  # Will refine later
            event_date_earliest=metadata_dict.get("doc_date_min"),
            event_date_latest=metadata_dict.get("doc_date_max"),
            record_date_edtf=metadata_dict.get("doc_date_min"),  # Assume same initially
            record_date_earliest=metadata_dict.get("doc_date_min"),
            record_date_latest=metadata_dict.get("doc_date_max"),
            repository=metadata_dict.get("repository"),
            citation=metadata_dict["citation"],
            normalized_text=normalized_text,
            normalized_text_sha256=normalized_text_sha256,
        )

        # Insert into database
        doc_dict = metadata.model_dump()
        self.db.insert_document(doc_dict)

        logger.info(f"Document ingested successfully: {xml_sha256}")
        return xml_sha256


def ingest_main(xml_path: str, db_path: str, cas_dir: str) -> str:
    """Main entry point for document ingest stage.

    Args:
        xml_path: Path to TEI-XML file
        db_path: Path to SQLite database
        cas_dir: Content-addressable storage directory

    Returns:
        SHA-256 hash of ingested document
    """
    with Database(db_path) as db:
        ingestor = DocumentIngestor(db, cas_dir)
        return ingestor.ingest_document(xml_path)
