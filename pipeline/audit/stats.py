"""Statistics and metrics computation."""

from typing import Any

from pipeline.utils.db import Database


def _safe_percentage(numerator: float, denominator: float) -> float:
    """Calculate percentage safely, returning 0.0 if denominator is 0.

    Args:
        numerator: Numerator
        denominator: Denominator

    Returns:
        Percentage (0.0-100.0) or 0.0 if denominator is 0
    """
    return (numerator / denominator * 100) if denominator > 0 else 0.0


def compute_comprehensive_stats(db: Database) -> dict[str, Any]:
    """Compute comprehensive pipeline statistics.

    Args:
        db: Database connection

    Returns:
        Dict of statistics and metrics
    """
    stats: dict[str, Any] = {}

    # Document stats
    cursor = db.execute("SELECT COUNT(*) as count FROM documents")
    stats["documents"] = cursor.fetchone()["count"]

    # Chunk stats
    cursor = db.execute("SELECT COUNT(*) as count FROM chunks")
    stats["chunks"] = cursor.fetchone()["count"]

    # Assertion stats
    cursor = db.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN verification = 'exact' THEN 1 END) as exact,
            COUNT(CASE WHEN verification = 'fuzzy' THEN 1 END) as fuzzy,
            COUNT(CASE WHEN explicit_or_inferred = 'explicit' THEN 1 END) as explicit,
            COUNT(CASE WHEN explicit_or_inferred = 'inferred' THEN 1 END) as inferred,
            ROUND(AVG(confidence), 3) as avg_confidence,
            MIN(confidence) as min_confidence,
            MAX(confidence) as max_confidence
        FROM assertions
    """)
    assertion_stats = dict(cursor.fetchone())
    stats["assertions"] = assertion_stats

    # Quarantine stats
    cursor = db.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN reason = 'quote_not_found' THEN 1 END) as quote_not_found,
            COUNT(CASE WHEN reason = 'pending_verification' THEN 1 END) as pending
        FROM quarantine
    """)
    quarantine_stats = dict(cursor.fetchone())
    stats["quarantine"] = quarantine_stats

    # Calculate rates
    total_extractions = assertion_stats["total"] + quarantine_stats["total"]
    stats["verification_rate"] = assertion_stats["total"] / total_extractions if total_extractions > 0 else 0.0
    stats["quarantine_rate"] = quarantine_stats["total"] / total_extractions if total_extractions > 0 else 0.0

    # Date distribution
    cursor = db.execute("""
        SELECT
            COUNT(DISTINCT event_date_edtf) as unique_dates,
            MIN(event_date_edtf) as earliest_date,
            MAX(event_date_edtf) as latest_date
        FROM assertions
        WHERE event_date_edtf IS NOT NULL
    """)
    date_stats = dict(cursor.fetchone())
    stats["date_coverage"] = date_stats

    # Audience distribution
    cursor = db.execute("""
        SELECT
            COUNT(DISTINCT audience) as unique_audiences,
            COUNT(CASE WHEN audience IS NOT NULL THEN 1 END) as with_audience
        FROM assertions
    """)
    audience_stats = dict(cursor.fetchone())
    stats["audience_coverage"] = audience_stats

    # Offset validation (should always be 100%)
    cursor = db.execute("""
        SELECT COUNT(*) as count
        FROM assertions
        WHERE char_start >= 0 AND char_end > char_start
    """)
    valid_offsets = cursor.fetchone()["count"]
    stats["offset_validation_rate"] = (
        valid_offsets / assertion_stats["total"] if assertion_stats["total"] > 0 else 0.0
    )

    return stats


def print_comprehensive_stats(stats: dict[str, Any]) -> None:
    """Print comprehensive statistics in a formatted way.

    Args:
        stats: Statistics dict from compute_comprehensive_stats
    """
    print("\n" + "=" * 70)
    print(" " * 15 + "COMPREHENSIVE PIPELINE STATISTICS")
    print("=" * 70)

    # Documents and Chunks
    print(f"\n📄 CORPUS")
    print(f"   Documents:                {stats['documents']}")
    print(f"   Chunks:                   {stats['chunks']}")

    # Assertions
    total_assertions = stats['assertions']['total']
    print(f"\n✅ VERIFIED PRINCIPLES")
    print(f"   Total:                    {total_assertions}")
    print(f"   - Explicit:               {stats['assertions']['explicit']} "
          f"({_safe_percentage(stats['assertions']['explicit'], total_assertions):.1f}%)")
    print(f"   - Inferred:               {stats['assertions']['inferred']} "
          f"({_safe_percentage(stats['assertions']['inferred'], total_assertions):.1f}%)")
    print(f"\n   Average Confidence:       {stats['assertions']['avg_confidence']:.3f}")
    print(f"   Confidence Range:         {stats['assertions']['min_confidence']:.2f} - "
          f"{stats['assertions']['max_confidence']:.2f}")

    # Verification
    print(f"\n🔍 VERIFICATION")
    print(f"   Exact Matches:            {stats['assertions']['exact']} "
          f"({_safe_percentage(stats['assertions']['exact'], total_assertions):.1f}%)")
    print(f"   Fuzzy Matches:            {stats['assertions']['fuzzy']} "
          f"({_safe_percentage(stats['assertions']['fuzzy'], total_assertions):.1f}%)")
    print(f"   Offset Validation:        {stats['offset_validation_rate']*100:.1f}%")

    # Quarantine
    print(f"\n⚠️  QUARANTINE")
    print(f"   Total Quarantined:        {stats['quarantine']['total']}")
    print(f"   - Quote Not Found:        {stats['quarantine']['quote_not_found']}")
    print(f"   - Pending Verification:   {stats['quarantine']['pending']}")

    # Overall rates
    print(f"\n📊 OVERALL METRICS")
    print(f"   Verification Rate:        {stats['verification_rate']*100:.1f}% "
          f"{'✅ PASS' if stats['verification_rate'] >= 0.95 else '❌ FAIL'} (target ≥95%)")
    print(f"   Quarantine Rate:          {stats['quarantine_rate']*100:.1f}% "
          f"{'✅ PASS' if stats['quarantine_rate'] <= 0.10 else '❌ FAIL'} (target ≤10%)")

    # Metadata coverage
    print(f"\n📅 METADATA COVERAGE")
    print(f"   Unique Dates:             {stats['date_coverage']['unique_dates']}")
    print(f"   Date Range:               {stats['date_coverage']['earliest_date']} to "
          f"{stats['date_coverage']['latest_date']}")
    with_audience = stats['audience_coverage']['with_audience']
    print(f"   With Audience Info:       {with_audience}/{total_assertions} "
          f"({_safe_percentage(with_audience, total_assertions):.1f}%)")
    print(f"   Unique Audiences:         {stats['audience_coverage']['unique_audiences']}")

    print("\n" + "=" * 70)
