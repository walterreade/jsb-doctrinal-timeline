"""Run the full extraction pipeline on JS Histories.xml (a teiCorpus with multiple TEI documents)."""

import sys
import tempfile
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.config import config
from pipeline.stages.stage_0_ingest import ingest_main
from pipeline.stages.stage_1_chunk import chunk_main
from pipeline.stages.stage_2_extract import extract_main
from pipeline.stages.stage_3_verify import verify_main
from pipeline.stages.stage_4_glean import glean_main
from pipeline.utils.db import Database

NS = {"tei": "http://www.tei-c.org/ns/1.0", "pm": "https://xmlref.com/local/pm"}

DB_PATH = str(config.db_path)
CAS_DIR = str(config.cas_dir)


def split_corpus(xml_path: str) -> list[tuple[str, Path]]:
    """Split a teiCorpus into individual TEI XML files.

    Returns list of (title, temp_file_path) tuples.
    """
    parser = etree.XMLParser(recover=True, no_network=True)
    tree = etree.parse(xml_path, parser=parser)
    root = tree.getroot()

    root_tag = etree.QName(root).localname
    if root_tag == "TEI":
        return [("single", Path(xml_path))]

    teis = root.findall("tei:TEI", NS)
    results = []
    tmp_dir = Path(tempfile.mkdtemp(prefix="jsb_tei_"))

    for i, tei in enumerate(teis):
        title_elem = tei.find(".//tei:titleStmt/tei:title[@type='editorial']", NS)
        title = title_elem.text.strip().replace("\n", " ") if title_elem is not None and title_elem.text else f"Document {i+1}"

        body = tei.find(".//tei:text/tei:body", NS)
        body_text = etree.tostring(body, method="text", encoding="unicode") if body is not None else ""
        if len(body_text.strip()) < 100:
            print(f"  Skipping '{title}' (body too short: {len(body_text)} chars)")
            continue

        tmp_path = tmp_dir / f"doc_{i:02d}.xml"
        tei_bytes = etree.tostring(tei, xml_declaration=True, encoding="UTF-8")
        tmp_path.write_bytes(tei_bytes)
        results.append((title, tmp_path))

    return results


def run_pipeline_on_document(title: str, xml_path: Path) -> str | None:
    """Run full pipeline (ingest → chunk → extract → verify → glean → verify) on one document."""
    print(f"\n{'='*70}")
    print(f"  Processing: {title}")
    print(f"{'='*70}")

    try:
        sha256 = ingest_main(str(xml_path), DB_PATH, CAS_DIR)
        print(f"  Ingested: {sha256[:16]}...")

        chunk_main(sha256, DB_PATH)
        with Database(DB_PATH) as db:
            chunks = db.get_chunks(sha256)
        print(f"  Chunked: {len(chunks)} chunks")

        extract_summary = extract_main(sha256, DB_PATH)
        print(f"  Extracted: {extract_summary['total_extracted']} principles (raw)")

        verify_summary = verify_main(sha256, DB_PATH)
        print(f"  Verified: {verify_summary['verified_exact'] + verify_summary['verified_fuzzy']} "
              f"({verify_summary['verification_rate']:.0%})")

        glean_summary = glean_main(sha256, DB_PATH)
        print(f"  Gleaned: {glean_summary['total_new']} new principles")

        if glean_summary["total_new"] > 0:
            verify2 = verify_main(sha256, DB_PATH)
            print(f"  Verified (glean): {verify2['verified_exact'] + verify2['verified_fuzzy']} "
                  f"({verify2['verification_rate']:.0%})")

        return sha256

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    xml_path = "xml_files/Histories/JS Histories.xml"
    print(f"Splitting corpus: {xml_path}")
    documents = split_corpus(xml_path)
    print(f"Found {len(documents)} documents with substantial text\n")

    sha256s = []
    for title, path in documents:
        sha = run_pipeline_on_document(title, path)
        if sha:
            sha256s.append(sha)

    print(f"\n{'='*70}")
    print(f"  COMPLETE: Processed {len(sha256s)} documents")
    print(f"{'='*70}")

    with Database(DB_PATH) as db:
        cursor = db.execute("SELECT COUNT(*) as c FROM assertions")
        total = cursor.fetchone()["c"]
        print(f"  Total assertions in database: {total}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
