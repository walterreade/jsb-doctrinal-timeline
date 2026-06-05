"""Export principle timelines as markdown tables.

Generates:
- js_histories_extracted.md — Principles from JS Histories documents only
- joseph_smith_principles_timeline.md — Combined chronological table of all principles
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.utils.db import Database

J1_SHA = "a344934fb478fd2ef54eefdd0a266b28ad39edd24925d737b30a88a5d841bd81"


def write_markdown_table(rows: list[dict], output_path: str, title: str, source: str) -> None:
    """Write a markdown table of principles."""
    with open(output_path, "w") as f:
        f.write(f"# {title}\n\n")
        f.write(f"**Source:** {source}  \n")
        f.write(f"**Total Principles:** {len(rows)}  \n")
        if rows:
            dates = sorted(set(r["event_date_edtf"] or "unknown" for r in rows))
            f.write(f"**Date Range:** {dates[0]} to {dates[-1]}  \n")
        f.write("**Extraction Method:** Provenance-grade computational pipeline "
                "with deterministic verification\n\n")
        f.write("---\n\n")
        f.write("| Date | Principle | Type | Audience | Source Document | Recorded By |\n")
        f.write("|------|-----------|------|----------|----------------|-------------|\n")
        for row in rows:
            principle = row["principle_statement"].replace("|", "\\|").replace("\n", " ")
            audience = (row["audience"] or "Not specified").replace("|", "\\|").replace("\n", " ")
            ptype = row["explicit_or_inferred"] or "unknown"
            doc_title = (row.get("doc_title") or "Unknown").replace("|", "\\|").replace("\n", " ")
            date = row["event_date_edtf"] or "unknown"
            f.write(f"| {date} | {principle} | {ptype} "
                    f"| {audience} | {doc_title} | Joseph Smith Jr. |\n")

    print(f"Wrote {len(rows)} principles to {output_path}")


def fetch_principles(db: Database, where: str = "", params: tuple = ()) -> list[dict]:
    """Fetch principles with document titles."""
    query = f"""
        SELECT a.event_date_edtf, a.principle_statement, a.explicit_or_inferred,
               COALESCE(a.audience, 'Not specified') as audience,
               d.title as doc_title
        FROM assertions a
        JOIN documents d ON a.document_sha256 = d.sha256
        {where}
        ORDER BY a.event_date_edtf, a.id
    """
    return [dict(r) for r in db.execute(query, params).fetchall()]


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/j1_principles.db"

    with Database(db_path) as db:
        # J1 principles (for regenerating j1_principles_extracted.md)
        j1_rows = fetch_principles(db, "WHERE a.document_sha256 = ?", (J1_SHA,))
        write_markdown_table(
            j1_rows,
            "j1_principles_extracted.md",
            "Joseph Smith Doctrinal Principles Chronology (J1: 1832–1834)",
            "Joseph Smith Papers Project — Journal, 1832–1834",
        )

        # JS Histories principles (all non-J1 documents)
        hist_rows = fetch_principles(db, "WHERE a.document_sha256 != ?", (J1_SHA,))
        write_markdown_table(
            hist_rows,
            "js_histories_extracted.md",
            "Joseph Smith Doctrinal Principles — JS Histories",
            "Joseph Smith Papers Project — JS Histories corpus",
        )

        # Combined timeline (everything)
        all_rows = fetch_principles(db)
        write_markdown_table(
            all_rows,
            "joseph_smith_principles_timeline.md",
            "Joseph Smith Doctrinal Principles — Combined Timeline",
            "Joseph Smith Papers Project — Journal 1832–1834 + JS Histories",
        )


if __name__ == "__main__":
    main()
