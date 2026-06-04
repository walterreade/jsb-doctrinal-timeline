"""Regenerate j1_principles_extracted.md with explicit/inferred tagging."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.utils.db import Database


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/j1_principles.db"

    with Database(db_path) as db:
        cursor = db.execute("""
            SELECT event_date_edtf, principle_statement, explicit_or_inferred,
                   COALESCE(audience, 'Not specified') as audience
            FROM assertions
            ORDER BY event_date_edtf, id
        """)
        rows = [dict(r) for r in cursor.fetchall()]

    with open("j1_principles_extracted.md", "w") as f:
        f.write("# Joseph Smith Doctrinal Principles Chronology (J1: 1832–1834)\n\n")
        f.write("A chronological table of every doctrinal principle taught by Joseph Smith "
                "as recorded in Journal 1 (1832–1834).\n\n")
        f.write(f"**Source:** Joseph Smith Papers Project — Journal, 1832–1834  \n")
        f.write(f"**Total Principles:** {len(rows)}  \n")
        f.write("**Date Range:** November 27, 1832 to December 5, 1834  \n")
        f.write("**Extraction Method:** Provenance-grade computational pipeline "
                "with deterministic verification\n\n")
        f.write("---\n\n")
        f.write("| Date | Principle | Type | Audience | Recorded By |\n")
        f.write("|------|-----------|------|----------|-------------|\n")
        for row in rows:
            principle = row["principle_statement"].replace("|", "\\|")
            audience = row["audience"].replace("|", "\\|")
            ptype = row["explicit_or_inferred"]
            f.write(f"| {row['event_date_edtf']} | {principle} | {ptype} "
                    f"| {audience} | Joseph Smith Jr. |\n")

    print(f"Wrote {len(rows)} principles to j1_principles_extracted.md")


if __name__ == "__main__":
    main()
