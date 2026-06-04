"""Export principles to various formats (CSV, JSON, Markdown)."""

import csv
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.utils.db import Database


# Standard field set for exports
EXPORT_FIELDS = [
    "id",
    "principle_statement",
    "verbatim_quote",
    "explicit_or_inferred",
    "confidence",
    "event_date_edtf",
    "audience",
    "verification",
    "fuzzy_score",
    "char_start",
    "char_end",
    "reasoning",
]


def _fetch_assertions(db: Database, fields: list[str], order_by: str = "event_date_edtf, id") -> list[dict[str, Any]]:
    """Fetch assertions with specified fields.

    Args:
        db: Database connection
        fields: List of field names to select
        order_by: ORDER BY clause

    Returns:
        List of assertion rows as dicts
    """
    fields_str = ",\n            ".join(fields)
    query = f"""
        SELECT
            {fields_str}
        FROM assertions
        ORDER BY {order_by}
    """
    cursor = db.execute(query)
    return [dict(row) for row in cursor.fetchall()]


def export_to_csv(db: Database, output_path: str) -> int:
    """Export principles to CSV.

    Args:
        db: Database connection
        output_path: Output CSV file path

    Returns:
        Number of rows exported
    """
    rows = _fetch_assertions(db, EXPORT_FIELDS)

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def export_to_json(db: Database, output_path: str, pretty: bool = True) -> int:
    """Export principles to JSON.

    Args:
        db: Database connection
        output_path: Output JSON file path
        pretty: Whether to pretty-print JSON

    Returns:
        Number of records exported
    """
    rows = _fetch_assertions(db, EXPORT_FIELDS)

    with open(output_path, 'w', encoding='utf-8') as f:
        if pretty:
            json.dump(rows, f, indent=2, ensure_ascii=False)
        else:
            json.dump(rows, f, ensure_ascii=False)

    return len(rows)


def export_to_markdown(db: Database, output_path: str) -> int:
    """Export principles to Markdown format.

    Args:
        db: Database connection
        output_path: Output Markdown file path

    Returns:
        Number of principles exported
    """
    markdown_fields = [
        "principle_statement",
        "verbatim_quote",
        "explicit_or_inferred",
        "confidence",
        "event_date_edtf",
        "audience",
        "verification",
    ]
    rows = _fetch_assertions(db, markdown_fields, order_by="event_date_edtf, confidence DESC")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Joseph Smith Doctrinal Principles\n\n")
        f.write("**Source:** Journal, 1832–1834\n\n")
        f.write(f"**Total Principles:** {len(rows)}\n\n")
        f.write("---\n\n")

        current_date = None
        for row in rows:
            # Group by date
            if row["event_date_edtf"] != current_date:
                current_date = row["event_date_edtf"]
                f.write(f"\n## {current_date}\n\n")

            # Write principle
            f.write(f"### {row['principle_statement']}\n\n")
            f.write(f"> \"{row['verbatim_quote']}\"\n\n")
            f.write(f"- **Type:** {row['explicit_or_inferred']}\n")
            f.write(f"- **Confidence:** {row['confidence']:.2f}\n")
            f.write(f"- **Audience:** {row['audience'] or 'Not specified'}\n")
            f.write(f"- **Verification:** {row['verification']}\n\n")
            f.write("---\n\n")

    return len(rows)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Export principles to various formats")
    parser.add_argument("format", choices=["csv", "json", "markdown", "all"],
                       help="Export format")
    parser.add_argument("--db-path", default="data/j1_principles.db",
                       help="Path to database")
    parser.add_argument("--output-dir", default="exports",
                       help="Output directory")

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("Principles Export Utility")
    print("=" * 60)

    with Database(args.db_path) as db:
        # Get total count
        cursor = db.execute("SELECT COUNT(*) as count FROM assertions")
        total = cursor.fetchone()["count"]
        print(f"\nTotal principles to export: {total}")

        formats_to_export = ["csv", "json", "markdown"] if args.format == "all" else [args.format]

        for fmt in formats_to_export:
            output_path = output_dir / f"j1_principles.{fmt if fmt != 'markdown' else 'md'}"

            print(f"\nExporting to {fmt.upper()}...")

            if fmt == "csv":
                count = export_to_csv(db, str(output_path))
            elif fmt == "json":
                count = export_to_json(db, str(output_path))
            elif fmt == "markdown":
                count = export_to_markdown(db, str(output_path))

            print(f"  ✓ Exported {count} principles to: {output_path}")

    print("\n" + "=" * 60)
    print("✓ Export complete")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
