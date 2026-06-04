"""TEI-XML parser for Joseph Smith Papers Project documents."""

import re
from typing import Any

from lxml import etree


class TEIParser:
    """Parser for TEI P5 XML documents from the JSPP."""

    # TEI namespace
    TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}
    PMDC_NS = {"pm": "https://xmlref.com/local/pm"}
    LDS_NS = {"lds": "https://ldsc.xmlref.com/local/ldschurch"}

    # Combined namespace dict
    NS = {**TEI_NS, **PMDC_NS, **LDS_NS}

    def __init__(self, xml_path: str) -> None:
        """Initialize parser with XML file.

        Args:
            xml_path: Path to TEI XML file
        """
        self.xml_path = xml_path
        # Use lenient parser to handle non-standard XML attributes
        parser = etree.XMLParser(recover=True, no_network=True)
        self.tree = etree.parse(xml_path, parser=parser)
        self.root = self.tree.getroot()

    def extract_metadata(self) -> dict[str, Any]:
        """Extract document-level metadata from teiHeader.

        Returns:
            Dictionary of metadata fields
        """
        metadata: dict[str, Any] = {}

        # Title
        title_elem = self.root.find(".//tei:titleStmt/tei:title[@type='editorial']", self.NS)
        if title_elem is not None and title_elem.text:
            metadata["title"] = title_elem.text.strip()
        else:
            # Fallback to msName
            msname_elem = self.root.find(".//tei:msName", self.NS)
            metadata["title"] = self._extract_text_or_default(msname_elem, "Untitled")

        # Repository
        repo_elem = self.root.find(".//tei:repository", self.NS)
        metadata["repository"] = self._extract_text_or_default(repo_elem, None)

        # Recorder/scribes (from handwriting description in summary)
        summary_elem = self.root.find(".//tei:msContents/tei:summary/tei:p", self.NS)
        recorders = []
        if summary_elem is not None:
            # Extract all person references in handwriting context
            for person_ref in summary_elem.findall(".//tei:ref[@pm:link-pointer-type='person']", self.NS):
                if person_ref.text:
                    recorders.append(person_ref.text.strip())

        # Use first recorder as primary (if available)
        metadata["recorder"] = recorders[0] if recorders else None
        metadata["all_recorders"] = recorders

        # Date range from attributes
        tei_elem = self.root.find(".//tei:TEI", self.NS)
        if tei_elem is not None:
            metadata["doc_date_min"] = tei_elem.get("{%s}docDateMin" % self.PMDC_NS["pm"])
            metadata["doc_date_max"] = tei_elem.get("{%s}docDateMax" % self.PMDC_NS["pm"])

        # Citation (construct from series and title)
        series_elem = self.root.find(".//tei:seriesStmt/tei:title", self.NS)
        series = self._extract_text_or_default(series_elem, "")
        metadata["citation"] = f"{series}: {metadata['title']}" if series else metadata["title"]

        # Source type heuristic (journals are primary, compilations secondary)
        if "journal" in metadata["title"].lower():
            metadata["source_type"] = "primary"
            # Journals are typically contemporary_diary
            metadata["provenance_class"] = "contemporary_diary"
        else:
            metadata["source_type"] = "primary"  # Default assumption for JSPP
            metadata["provenance_class"] = "contemporary_scribal_record"

        return metadata

    def generate_clear_text(self) -> str:
        """Generate clear text by stripping diplomatic markup.

        Applies transformation rules:
        - Remove <del> and <cancel> content (cancellations)
        - Keep <add> and <insert> content (insertions)
        - Remove editorial annotations
        - Normalize whitespace

        Returns:
            Clean, readable text string
        """
        # Find the main text body
        body = self.root.find(".//tei:text/tei:body", self.NS)
        if body is None:
            return ""

        # Recursively extract text with diplomatic transformations
        text = self._extract_text_recursive(body)

        # Normalize whitespace
        text = self._normalize_whitespace(text)

        return text

    def _extract_text_recursive(self, elem: etree._Element) -> str:
        """Recursively extract text from element tree with transformations.

        Args:
            elem: XML element to process

        Returns:
            Extracted text string
        """
        # Skip certain elements entirely
        skip_tags = {
            "del",  # Deleted/cancelled text
            "cancel",  # Cancelled text
            "note",  # Editorial notes (footnotes, annotations)
            "pb",  # Page breaks
            "lb",  # Line breaks (we normalize whitespace instead)
            "teiHeader",  # Header (already extracted metadata)
            "fw",  # Form work (page numbers, headers)
        }

        # Get tag without namespace
        tag = etree.QName(elem).localname

        if tag in skip_tags:
            return ""

        # Start with element's direct text
        text_parts = []
        if elem.text:
            text_parts.append(elem.text)

        # Process children
        for child in elem:
            child_text = self._extract_text_recursive(child)
            if child_text:
                text_parts.append(child_text)

            # Add tail text (text after child element)
            if child.tail:
                text_parts.append(child.tail)

        return " ".join(text_parts)

    def _extract_text_or_default(self, elem: etree._Element | None, default: str | None) -> str | None:
        """Extract text from element or return default.

        Args:
            elem: XML element (can be None)
            default: Default value if element is None or has no text

        Returns:
            Stripped text or default value
        """
        if elem is not None and elem.text:
            return elem.text.strip()
        return default

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in extracted text.

        Args:
            text: Raw extracted text

        Returns:
            Text with normalized whitespace
        """
        # Collapse multiple spaces/newlines into single space
        text = re.sub(r"\s+", " ", text)

        # Remove leading/trailing whitespace
        text = text.strip()

        # Restore paragraph breaks (double newline) where appropriate
        # Look for common sentence-ending punctuation followed by capital letter
        text = re.sub(r"([.!?])\s+([A-Z])", r"\1\n\n\2", text)

        return text
