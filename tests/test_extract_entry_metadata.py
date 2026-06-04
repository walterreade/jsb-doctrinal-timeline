"""Tests for journal entry metadata extraction."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.utils.db import Database
from scripts.extract_entry_metadata import (
    _find_entry_start,
    _find_with_word_boundary,
    _iso_to_text_date,
    extract_journal_entry_boundaries,
    map_assertions_to_entries,
)


class TestIsoToTextDate:
    def test_normal_date(self):
        assert _iso_to_text_date("1833-10-06") == "6 October 1833"

    def test_january(self):
        assert _iso_to_text_date("1834-01-16") == "16 January 1834"

    def test_december(self):
        assert _iso_to_text_date("1832-12-05") == "5 December 1832"

    def test_strips_leading_zero_from_day(self):
        assert _iso_to_text_date("1833-03-03") == "3 March 1833"

    def test_invalid_month_zero(self):
        assert _iso_to_text_date("1833-00-15") == ""

    def test_invalid_month_thirteen(self):
        assert _iso_to_text_date("1833-13-01") == ""

    def test_too_few_parts(self):
        assert _iso_to_text_date("1833-10") == ""

    def test_too_many_parts(self):
        assert _iso_to_text_date("1833-10-06-extra") == ""

    def test_empty_string(self):
        assert _iso_to_text_date("") == ""

    def test_non_numeric_month(self):
        assert _iso_to_text_date("1833-XX-06") == ""

    def test_non_numeric_day(self):
        assert _iso_to_text_date("1833-10-YY") == ""


class TestFindWithWordBoundary:
    def test_exact_match(self):
        text = "On 6 October 1833 something happened"
        assert _find_with_word_boundary("6 October 1833", text, 0) == 3

    def test_avoids_substring_in_larger_number(self):
        text = "On 26 October 1833 something happened"
        assert _find_with_word_boundary("6 October 1833", text, 0) == -1

    def test_matches_after_start(self):
        text = "First 26 October then 6 October 1833 here"
        assert _find_with_word_boundary("6 October 1833", text, 0) == 22

    def test_start_of_string(self):
        text = "6 October 1833 is the date"
        assert _find_with_word_boundary("6 October 1833", text, 0) == 0

    def test_not_found(self):
        text = "nothing relevant here"
        assert _find_with_word_boundary("6 October 1833", text, 0) == -1

    def test_search_from_offset(self):
        text = "6 October 1833 first and 6 October 1833 second"
        assert _find_with_word_boundary("6 October 1833", text, 1) == 25

    def test_avoids_letter_prefix(self):
        text = "dateX6 October 1833 here"
        assert _find_with_word_boundary("6 October 1833", text, 0) == -1

    def test_after_punctuation(self):
        text = "Amen. 6 October 1833 entry"
        assert _find_with_word_boundary("6 October 1833", text, 0) == 6

    def test_after_newline(self):
        text = "previous line\n6 October 1833 entry"
        assert _find_with_word_boundary("6 October 1833", text, 0) == 14

    def test_dash_prefixed_date_range(self):
        text = "Here is 6-12 October 1833 entry"
        assert _find_with_word_boundary("6-12 October 1833", text, 0) == 8


class TestFindEntryStart:
    def test_finds_by_iso_date(self):
        text = "preamble 6 October 1833 entry content"
        pos = _find_entry_start("", "1833-10-06", text, [])
        assert pos == 9

    def test_finds_by_date_text(self):
        text = "preamble 6-12 October 1833 entry"
        pos = _find_entry_start("6–12 October 1833", "1833-10-06", text, [])
        assert pos == 9

    def test_prefers_iso_over_date_text(self):
        text = "6 October 1833 first then 6-12 October 1833 second"
        pos = _find_entry_start("6–12 October 1833", "1833-10-06", text, [])
        assert pos == 0

    def test_searches_forward_from_previous_entry(self):
        text = "6 October 1833 first ... 6 October 1833 second"
        entries = [{"char_start": 5, "char_end": 20}]
        pos = _find_entry_start("", "1833-10-06", text, entries)
        assert pos == 25

    def test_returns_negative_one_when_not_found(self):
        text = "nothing here"
        pos = _find_entry_start("", "1833-10-06", text, [])
        assert pos == -1

    def test_no_date_text_no_entry_date(self):
        pos = _find_entry_start("", None, "some text", [])
        assert pos == -1

    def test_dash_normalization_in_date_text(self):
        text = "the 6-12 October 1833 entry"
        pos = _find_entry_start("6–12 October 1833", None, text, [])
        assert pos == 4

    def test_avoids_substring_match(self):
        text = "On 26 October 1833 only"
        pos = _find_entry_start("", "1833-10-06", text, [])
        assert pos == -1


class TestExtractJournalEntryBoundaries:
    """Integration tests using a minimal TEI XML fixture."""

    NORMALIZED = (
        "5 October 1833 entry content here about doctrine. "
        "13 October 1833 another entry with teachings. "
        "20 October 1833 third entry content."
    )

    @pytest.fixture
    def minimal_xml(self, tmp_path):
        xml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader><fileDesc><titleStmt><title>Test</title></titleStmt>
  <publicationStmt><p/></publicationStmt><sourceDesc><p/></sourceDesc>
  </fileDesc></teiHeader>
  <text><body>
    <ab type="journal-entry-divider"><date when-iso="1833-10-05">5 October 1833</date></ab>
    <p>5 October 1833 entry content here about doctrine.</p>
    <ab type="journal-entry-divider"><date when-iso="1833-10-13">13 October 1833</date></ab>
    <p>13 October 1833 another entry with teachings.</p>
    <ab type="journal-entry-divider"><date when-iso="1833-10-20">20 October 1833</date></ab>
    <p>20 October 1833 third entry content.</p>
  </body></text>
</TEI>"""
        xml_path = tmp_path / "test.xml"
        xml_path.write_text(xml_content, encoding="utf-8")
        return str(xml_path)

    def test_finds_all_entries(self, minimal_xml):
        entries = extract_journal_entry_boundaries(minimal_xml, self.NORMALIZED)
        assert len(entries) == 3

    def test_entries_are_monotonically_increasing(self, minimal_xml):
        entries = extract_journal_entry_boundaries(minimal_xml, self.NORMALIZED)
        for i in range(1, len(entries)):
            assert entries[i]["char_start"] > entries[i - 1]["char_start"]

    def test_entries_cover_full_text(self, minimal_xml):
        entries = extract_journal_entry_boundaries(minimal_xml, self.NORMALIZED)
        assert entries[0]["char_start"] == 0
        assert entries[-1]["char_end"] == len(self.NORMALIZED)

    def test_no_gaps_between_entries(self, minimal_xml):
        entries = extract_journal_entry_boundaries(minimal_xml, self.NORMALIZED)
        for i in range(1, len(entries)):
            assert entries[i]["char_start"] == entries[i - 1]["char_end"]

    def test_dates_are_correct(self, minimal_xml):
        entries = extract_journal_entry_boundaries(minimal_xml, self.NORMALIZED)
        assert entries[0]["event_date_edtf"] == "1833-10-05"
        assert entries[1]["event_date_edtf"] == "1833-10-13"
        assert entries[2]["event_date_edtf"] == "1833-10-20"

    def test_skips_unfound_dates(self, tmp_path):
        xml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader><fileDesc><titleStmt><title>Test</title></titleStmt>
  <publicationStmt><p/></publicationStmt><sourceDesc><p/></sourceDesc>
  </fileDesc></teiHeader>
  <text><body>
    <ab type="journal-entry-divider"><date when-iso="1833-10-05">5 October 1833</date></ab>
    <p>5 October 1833 entry one.</p>
    <ab type="journal-entry-divider"><date when-iso="1833-10-27"></date></ab>
    <ab type="journal-entry-divider"><date when-iso="1833-11-01">1 November 1833</date></ab>
    <p>1 November 1833 entry two.</p>
  </body></text>
</TEI>"""
        xml_path = tmp_path / "test_skip.xml"
        xml_path.write_text(xml_content, encoding="utf-8")
        normalized = "5 October 1833 entry one. 1 November 1833 entry two."
        entries = extract_journal_entry_boundaries(str(xml_path), normalized)
        dates = [e["event_date_edtf"] for e in entries]
        assert "1833-10-05" in dates
        assert "1833-11-01" in dates
        assert "1833-10-27" not in dates


class TestMapAssertionsToEntries:
    """Tests for bisect-based assertion mapping."""

    @pytest.fixture
    def db_with_schema(self, tmp_path):
        db_path = tmp_path / "test.db"
        with Database(db_path) as db:
            db.conn.executescript("""
                CREATE TABLE documents (
                    sha256 TEXT PRIMARY KEY,
                    normalized_text TEXT
                );
                CREATE TABLE chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_sha256 TEXT,
                    chunk_index INTEGER,
                    char_start INTEGER,
                    char_end INTEGER,
                    chunk_text TEXT
                );
                CREATE TABLE assertions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_sha256 TEXT,
                    chunk_id INTEGER,
                    principle_statement TEXT,
                    verbatim_quote TEXT,
                    char_start INTEGER,
                    char_end INTEGER,
                    explicit_or_inferred TEXT,
                    verification TEXT,
                    fuzzy_score REAL,
                    confidence REAL,
                    audience TEXT,
                    event_date_edtf TEXT,
                    reasoning TEXT
                );
                CREATE TABLE quarantine (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_sha256 TEXT,
                    chunk_id INTEGER,
                    raw_json TEXT,
                    principle_statement TEXT,
                    attempted_quote TEXT,
                    reason TEXT
                );
            """)
        return db_path

    def _insert_assertion(self, db, char_start, char_end):
        db.execute(
            """INSERT INTO assertions
               (document_sha256, chunk_id, principle_statement, verbatim_quote,
                char_start, char_end, explicit_or_inferred, verification, confidence, reasoning)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("abc123", 1, "test principle", "test quote",
             char_start, char_end, "explicit", "exact", 0.9, "test"),
        )

    def test_maps_assertions_to_correct_entries(self, db_with_schema):
        entries = [
            {"char_start": 0, "char_end": 100, "event_date_edtf": "1833-10-05"},
            {"char_start": 100, "char_end": 200, "event_date_edtf": "1833-10-13"},
            {"char_start": 200, "char_end": 300, "event_date_edtf": "1833-10-20"},
        ]

        with Database(db_with_schema) as db:
            self._insert_assertion(db, 50, 80)
            self._insert_assertion(db, 150, 180)
            self._insert_assertion(db, 250, 280)

        with Database(db_with_schema) as db:
            count = map_assertions_to_entries(db, entries)

        assert count == 3

        with Database(db_with_schema) as db:
            rows = db.execute(
                "SELECT char_start, event_date_edtf FROM assertions ORDER BY char_start"
            ).fetchall()
            assert rows[0]["event_date_edtf"] == "1833-10-05"
            assert rows[1]["event_date_edtf"] == "1833-10-13"
            assert rows[2]["event_date_edtf"] == "1833-10-20"

    def test_assertion_at_entry_boundary_maps_to_later_entry(self, db_with_schema):
        entries = [
            {"char_start": 0, "char_end": 100, "event_date_edtf": "1833-10-05"},
            {"char_start": 100, "char_end": 200, "event_date_edtf": "1833-10-13"},
        ]

        with Database(db_with_schema) as db:
            self._insert_assertion(db, 100, 130)

        with Database(db_with_schema) as db:
            map_assertions_to_entries(db, entries)

        with Database(db_with_schema) as db:
            row = db.execute("SELECT event_date_edtf FROM assertions").fetchone()
            assert row["event_date_edtf"] == "1833-10-13"

    def test_unmapped_assertion_not_updated(self, db_with_schema):
        entries = [
            {"char_start": 100, "char_end": 200, "event_date_edtf": "1833-10-05"},
        ]

        with Database(db_with_schema) as db:
            self._insert_assertion(db, 50, 80)

        with Database(db_with_schema) as db:
            count = map_assertions_to_entries(db, entries)

        assert count == 0

    def test_empty_entries_list(self, db_with_schema):
        with Database(db_with_schema) as db:
            self._insert_assertion(db, 50, 80)

        with Database(db_with_schema) as db:
            count = map_assertions_to_entries(db, [])

        assert count == 0
