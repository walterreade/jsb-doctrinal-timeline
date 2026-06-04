"""Document metadata model."""

from typing import Literal

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Metadata for a source document from the Joseph Smith corpus."""

    sha256: str = Field(..., description="SHA-256 hash of raw document bytes")
    title: str = Field(..., description="Document title from TEI header")
    source_type: Literal["primary", "secondary"] = Field(
        ..., description="Primary (contemporaneous) or secondary (later compilation)"
    )
    provenance_class: Literal[
        "autograph",
        "dictated_revelation",
        "contemporary_scribal_record",
        "contemporary_diary",
        "later_recollection",
        "amalgamation",
        "published_edition",
    ] = Field(..., description="W3C PROV-style provenance classification")
    recorder: str | None = Field(None, description="Name of scribe/recorder")
    event_date_edtf: str | None = Field(None, description="EDTF date when taught")
    event_date_earliest: str | None = Field(None, description="Lower bound date")
    event_date_latest: str | None = Field(None, description="Upper bound date")
    record_date_edtf: str | None = Field(None, description="EDTF date when recorded")
    record_date_earliest: str | None = Field(None, description="Lower bound recording date")
    record_date_latest: str | None = Field(None, description="Upper bound recording date")
    repository: str | None = Field(None, description="Archive location (e.g., CHL)")
    citation: str | None = Field(None, description="Full bibliographic citation")
    normalized_text: str = Field(..., description="Clear text (frozen after normalization)")
    normalized_text_sha256: str = Field(..., description="SHA-256 of normalized text")
