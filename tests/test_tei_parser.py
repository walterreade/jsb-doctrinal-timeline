"""Tests for TEI-XML parser."""

import pytest

from pipeline.utils.tei_parser import TEIParser


@pytest.fixture
def minimal_tei(tmp_path):
    xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0"
     xmlns:pm="https://xmlref.com/local/pm"
     pm:docDateMin="1832-11-27"
     pm:docDateMax="1834-12-05">
  <teiHeader>
    <fileDesc>
      <titleStmt>
        <title type="editorial">Journal, 1832–1834</title>
      </titleStmt>
      <publicationStmt><p/></publicationStmt>
      <sourceDesc>
        <msDesc>
          <msIdentifier>
            <repository>Church History Library</repository>
          </msIdentifier>
          <msContents>
            <summary>
              <p>Written primarily in the hand of
                <ref pm:link-pointer-type="person">Joseph Smith</ref> and
                <ref pm:link-pointer-type="person">Frederick G. Williams</ref>.
              </p>
            </summary>
          </msContents>
        </msDesc>
      </sourceDesc>
    </fileDesc>
  </teiHeader>
  <text>
    <body>
      <p>This is <del>deleted</del> <add>added</add> text.</p>
      <p>Second paragraph with <del>cancelled</del> content.</p>
    </body>
  </text>
</TEI>"""
    path = tmp_path / "test.xml"
    path.write_text(xml, encoding="utf-8")
    return str(path)


class TestExtractMetadata:
    def test_title(self, minimal_tei):
        parser = TEIParser(minimal_tei)
        metadata = parser.extract_metadata()
        assert metadata["title"] == "Journal, 1832–1834"

    def test_repository(self, minimal_tei):
        parser = TEIParser(minimal_tei)
        metadata = parser.extract_metadata()
        assert metadata["repository"] == "Church History Library"

    def test_recorder(self, minimal_tei):
        parser = TEIParser(minimal_tei)
        metadata = parser.extract_metadata()
        assert metadata["recorder"] == "Joseph Smith"

    def test_all_recorders(self, minimal_tei):
        parser = TEIParser(minimal_tei)
        metadata = parser.extract_metadata()
        assert "Joseph Smith" in metadata["all_recorders"]
        assert "Frederick G. Williams" in metadata["all_recorders"]

    def test_source_type_journal(self, minimal_tei):
        parser = TEIParser(minimal_tei)
        metadata = parser.extract_metadata()
        assert metadata["source_type"] == "primary"
        assert metadata["provenance_class"] == "contemporary_diary"


class TestGenerateClearText:
    def test_removes_del_tags(self, minimal_tei):
        parser = TEIParser(minimal_tei)
        text = parser.generate_clear_text()
        assert "deleted" not in text
        assert "cancelled" not in text

    def test_keeps_add_tags(self, minimal_tei):
        parser = TEIParser(minimal_tei)
        text = parser.generate_clear_text()
        assert "added" in text

    def test_no_empty_body(self, tmp_path):
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader><fileDesc><titleStmt><title>T</title></titleStmt>
  <publicationStmt><p/></publicationStmt><sourceDesc><p/></sourceDesc>
  </fileDesc></teiHeader>
  <text></text>
</TEI>"""
        path = tmp_path / "nobody.xml"
        path.write_text(xml, encoding="utf-8")
        parser = TEIParser(str(path))
        assert parser.generate_clear_text() == ""


class TestNormalizeWhitespace:
    def test_collapses_multiple_spaces(self, minimal_tei):
        parser = TEIParser(minimal_tei)
        result = parser._normalize_whitespace("hello   world")
        assert "   " not in result

    def test_strips_leading_trailing(self, minimal_tei):
        parser = TEIParser(minimal_tei)
        result = parser._normalize_whitespace("  hello  ")
        assert not result.startswith(" ")
        assert not result.endswith(" ")

    def test_paragraph_breaks_after_sentence(self, minimal_tei):
        parser = TEIParser(minimal_tei)
        result = parser._normalize_whitespace("First sentence. Second sentence.")
        assert "\n\n" in result
