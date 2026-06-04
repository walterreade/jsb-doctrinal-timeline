"""Tests for fuzzy string matching utilities."""

import pytest

from pipeline.utils.fuzzy_match import MatchResult, find_best_match


class TestFindBestMatchExact:
    def test_exact_match_returns_100(self):
        result = find_best_match("hello world", "say hello world today")
        assert result is not None
        assert result.score == 100.0

    def test_exact_match_correct_offsets(self):
        result = find_best_match("hello", "say hello today")
        assert result is not None
        assert result.char_start == 4
        assert result.char_end == 9

    def test_exact_match_at_start(self):
        result = find_best_match("hello", "hello world")
        assert result is not None
        assert result.char_start == 0
        assert result.char_end == 5

    def test_exact_match_at_end(self):
        result = find_best_match("world", "hello world")
        assert result is not None
        assert result.char_start == 6
        assert result.char_end == 11

    def test_offset_invariant(self):
        needle = "the truth"
        haystack = "we know the truth is important"
        result = find_best_match(needle, haystack)
        assert result is not None
        assert haystack[result.char_start : result.char_end] == needle


class TestFindBestMatchFuzzy:
    def test_fuzzy_match_with_ocr_variance(self):
        needle = "the gospel of Jesus Christ"
        haystack = "preaching th e gosple of Jesus Chrst to the world"
        result = find_best_match(needle, haystack, threshold=70.0)
        assert result is not None
        assert result.score >= 70.0

    def test_fuzzy_match_below_threshold_returns_none(self):
        result = find_best_match("completely different", "nothing in common here", threshold=90.0)
        assert result is None

    def test_fuzzy_match_offsets_are_valid(self):
        needle = "laying on of hands"
        haystack = "the ordinance of layng on of handes was performed"
        result = find_best_match(needle, haystack, threshold=70.0)
        if result is not None:
            assert 0 <= result.char_start < result.char_end <= len(haystack)


class TestFindBestMatchEdgeCases:
    def test_empty_needle_returns_none(self):
        assert find_best_match("", "some haystack") is None

    def test_empty_haystack_returns_none(self):
        assert find_best_match("needle", "") is None

    def test_both_empty_returns_none(self):
        assert find_best_match("", "") is None

    def test_needle_longer_than_haystack(self):
        result = find_best_match("a very long needle string", "short")
        assert result is None or result.score < 50

    def test_identical_strings(self):
        text = "the priesthood is a high and holy institution"
        result = find_best_match(text, text)
        assert result is not None
        assert result.score == 100.0
        assert result.char_start == 0
        assert result.char_end == len(text)

    def test_result_is_named_tuple(self):
        result = find_best_match("hello", "hello world")
        assert result is not None
        assert isinstance(result, MatchResult)
        assert hasattr(result, "score")
        assert hasattr(result, "char_start")
        assert hasattr(result, "char_end")
