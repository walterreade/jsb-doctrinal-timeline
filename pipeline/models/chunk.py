"""Chunk metadata model."""

from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    """Metadata for a semantically-chunked text segment."""

    document_sha256: str = Field(..., description="Parent document SHA-256")
    chunk_index: int = Field(..., ge=0, description="Sequential chunk number")
    char_start: int = Field(..., ge=0, description="Absolute character offset (start)")
    char_end: int = Field(..., gt=0, description="Absolute character offset (end)")
    chunk_text: str = Field(..., min_length=1, description="Text content of chunk")

    def validate_offsets(self, normalized_text: str) -> bool:
        """Validate that offsets correctly slice the normalized text."""
        return normalized_text[self.char_start : self.char_end] == self.chunk_text
