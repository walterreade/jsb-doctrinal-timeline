"""Principle assertion model (for LLM extraction)."""

from typing import Literal

from pydantic import BaseModel, Field


class PrincipleAssertion(BaseModel):
    """A single doctrinal principle extracted from a text chunk."""

    principle_statement: str = Field(
        ...,
        description="Atomic, decontextualized teaching (one principle per assertion)",
    )
    verbatim_quote: str = Field(
        ...,
        description="EXACT character-for-character quote from source (never paraphrase)",
    )
    explicit_or_inferred: Literal["explicit", "inferred"] = Field(
        ...,
        description=(
            "explicit: Joseph Smith states principle directly; "
            "inferred: principle is entailed but not verbatim"
        ),
    )
    reasoning: str = Field(
        ...,
        description="Why this is a principle (audit trail for human review)",
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Extraction confidence (0-1 scale)"
    )
    audience_hint: str | None = Field(
        None,
        description='Optional audience context (e.g., "public conference", "private letter")',
    )
