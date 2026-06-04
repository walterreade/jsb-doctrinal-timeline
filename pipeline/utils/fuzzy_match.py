"""Fuzzy string matching utilities for quote verification."""

from typing import NamedTuple

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein


class MatchResult(NamedTuple):
    """Result of a fuzzy match operation."""

    score: float  # Similarity score (0-100)
    char_start: int  # Start position in haystack
    char_end: int  # End position in haystack


def find_best_match(
    needle: str, haystack: str, threshold: float = 90.0
) -> MatchResult | None:
    """Find best fuzzy match of needle in haystack.

    Uses rapidfuzz's partial_ratio_alignment for OCR/transcription variance.

    Args:
        needle: String to search for
        haystack: String to search in
        threshold: Minimum similarity score (0-100) to accept

    Returns:
        MatchResult if found above threshold, None otherwise
    """
    if not needle or not haystack:
        return None

    # First try exact match (fastest)
    exact_pos = haystack.find(needle)
    if exact_pos != -1:
        return MatchResult(
            score=100.0,
            char_start=exact_pos,
            char_end=exact_pos + len(needle),
        )

    # Fall back to fuzzy matching using rapidfuzz's extractOne
    # This properly handles substring matching with alignment
    from rapidfuzz import process

    # Use process.extractOne to find best match with position information
    result = process.extractOne(
        needle,
        [haystack],
        scorer=fuzz.partial_ratio,
        score_cutoff=threshold
    )

    if result is None:
        return None

    # result is tuple: (match_text, score, index)
    match_score = result[1]

    # Now find the actual substring position using partial_ratio_alignment
    # This gives us the exact alignment of the substring
    from rapidfuzz.fuzz import partial_ratio_alignment

    alignment = partial_ratio_alignment(needle, haystack)

    # alignment.src_start/src_end refers to positions in needle
    # alignment.dest_start/dest_end refers to positions in haystack
    char_start = alignment.dest_start
    char_end = alignment.dest_end

    return MatchResult(
        score=match_score,
        char_start=char_start,
        char_end=char_end,
    )
