"""Extract journal entry metadata and map to assertions."""

import logging
import sys
from pathlib import Path

from lxml import etree

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.utils.db import Database

logger = logging.getLogger(__name__)


def _extract_entry_date(date_elem: etree._Element | None, ns: dict) -> tuple[str | None, str]:
    """Extract date information from date element.

    Args:
        date_elem: Date element from XML
        ns: XML namespaces

    Returns:
        Tuple of (entry_date, date_text)
    """
    if date_elem is None:
        return None, ""

    # Try different date attributes (when-iso, from-iso, to-iso)
    entry_date = (
        date_elem.get("when-iso") or
        date_elem.get("from-iso") or
        date_elem.get("{%s}when-iso" % ns["tei"])
    )

    # Get date text for searching
    date_text = (date_elem.text or "").strip()

    return entry_date, date_text


def _find_entry_start(date_text: str, entry_date: str | None, normalized_text: str, entries: list[dict]) -> int:
    """Find entry start position in normalized text.

    Args:
        date_text: Date text to search for
        entry_date: ISO date string
        normalized_text: Full normalized text
        entries: List of previously found entries

    Returns:
        Character start position
    """
    # Try to find date in normalized text
    for pattern in [date_text, entry_date or ""]:
        if pattern:
            pattern_clean = pattern.replace("–", "-").replace("—", "-")
            pos = normalized_text.find(pattern_clean)
            if pos != -1:
                return pos

    # Fallback: use previous entry's end or beginning of text
    return entries[-1].get("char_end", 0) if entries else 0


def _print_progress(current: int, total: int, interval: int = 20) -> None:
    """Print progress at intervals.

    Args:
        current: Current index (0-based)
        total: Total count
        interval: Print every N items
    """
    if current % interval == 0:
        print(f"Processed {current+1}/{total} entries...")


def extract_journal_entry_boundaries(xml_path: str, normalized_text: str) -> list[dict]:
    """Extract journal entry boundaries with dates from TEI XML.

    Args:
        xml_path: Path to TEI XML file
        normalized_text: The normalized text (to compute offsets)

    Returns:
        List of entry metadata dicts with char_start, char_end, date
    """
    # Parse XML
    parser = etree.XMLParser(recover=True, no_network=True)
    tree = etree.parse(xml_path, parser=parser)
    root = tree.getroot()

    # Namespaces
    NS = {
        "tei": "http://www.tei-c.org/ns/1.0",
        "pm": "https://xmlref.com/local/pm",
    }

    # Find all journal entry dividers
    dividers = root.findall(".//tei:ab[@type='journal-entry-divider']", NS)
    print(f"Found {len(dividers)} journal entry dividers")

    entries = []

    for i, divider in enumerate(dividers):
        date_elem = divider.find(".//tei:date", NS)
        entry_date, date_text = _extract_entry_date(date_elem, NS)

        if entry_date is not None or date_text:
            entry_start = _find_entry_start(date_text, entry_date, normalized_text, entries)

            # Update previous entry's end
            if entries:
                entries[-1]["char_end"] = entry_start

            entries.append({
                "char_start": entry_start,
                "char_end": len(normalized_text),  # Will update in next iteration
                "event_date_edtf": entry_date,
                "date_text": date_text,
            })

            _print_progress(i, len(dividers))

    print(f"\nExtracted {len(entries)} journal entries with dates")

    # Print sample
    if entries:
        print("\nSample entries:")
        for entry in entries[:5]:
            length = entry['char_end'] - entry['char_start']
            print(f"  Date: {entry['event_date_edtf']}, "
                  f"Offset: {entry['char_start']}:{entry['char_end']}, "
                  f"Length: {length} chars")

    return entries


def map_assertions_to_entries(db: Database, entry_boundaries: list[dict]) -> int:
    """Map assertions to journal entries and update metadata.

    Args:
        db: Database connection
        entry_boundaries: List of entry metadata from extract_journal_entry_boundaries

    Returns:
        Number of assertions updated
    """
    # Get all assertions
    cursor = db.execute("SELECT id, char_start FROM assertions ORDER BY char_start")
    assertions = cursor.fetchall()

    print(f"\nMapping {len(assertions)} assertions to {len(entry_boundaries)} entries...")

    updated_count = 0

    for assertion in assertions:
        assertion_id = assertion["id"]
        assertion_offset = assertion["char_start"]

        # Find which entry this assertion belongs to
        matched_entry = None
        for entry in entry_boundaries:
            if entry["char_start"] <= assertion_offset < entry["char_end"]:
                matched_entry = entry
                break

        if matched_entry:
            # Update assertion with entry date
            db.execute(
                """
                UPDATE assertions
                SET event_date_edtf = ?
                WHERE id = ?
                """,
                (matched_entry["event_date_edtf"], assertion_id)
            )
            updated_count += 1
        else:
            # No match found - use document-level date
            logger.warning(f"Assertion {assertion_id} at offset {assertion_offset} "
                         f"not matched to any entry")

    print(f"Updated {updated_count}/{len(assertions)} assertions with entry dates")

    return updated_count


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Extract journal entry metadata")
    parser.add_argument("xml_path", help="Path to TEI XML file")
    parser.add_argument("--db-path", default="data/j1_principles.db",
                       help="Path to database")

    args = parser.parse_args()

    print("=" * 60)
    print("Journal Entry Metadata Extraction")
    print("=" * 60)

    # Get normalized text from database
    with Database(args.db_path) as db:
        cursor = db.execute("SELECT sha256, normalized_text FROM documents LIMIT 1")
        doc = cursor.fetchone()

        if not doc:
            print("ERROR: No documents found in database")
            return 1

        normalized_text = doc["normalized_text"]
        print(f"\nDocument: {doc['sha256']}")
        print(f"Text length: {len(normalized_text)} chars")

    # Extract entry boundaries
    entry_boundaries = extract_journal_entry_boundaries(args.xml_path, normalized_text)

    # Update assertions
    with Database(args.db_path) as db:
        updated_count = map_assertions_to_entries(db, entry_boundaries)

    print("\n" + "=" * 60)
    print(f"✓ SUCCESS: Updated {updated_count} assertions with entry dates")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
