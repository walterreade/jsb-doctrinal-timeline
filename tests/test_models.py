"""Tests for Pydantic models."""

import pytest
from pydantic import ValidationError

from pipeline.models.principle import PrincipleAssertion


class TestPrincipleAssertion:
    def test_valid_explicit(self):
        p = PrincipleAssertion(
            principle_statement="Faith is essential",
            verbatim_quote="we must have faith",
            explicit_or_inferred="explicit",
            reasoning="Direct statement",
            confidence=0.95,
        )
        assert p.principle_statement == "Faith is essential"
        assert p.explicit_or_inferred == "explicit"

    def test_valid_inferred(self):
        p = PrincipleAssertion(
            principle_statement="Prayer is important",
            verbatim_quote="prayed unto the Lord",
            explicit_or_inferred="inferred",
            reasoning="Implied by action",
            confidence=0.7,
        )
        assert p.explicit_or_inferred == "inferred"

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            PrincipleAssertion(
                principle_statement="test",
                verbatim_quote="test",
                explicit_or_inferred="maybe",
                reasoning="test",
                confidence=0.5,
            )

    def test_confidence_bounds_low(self):
        with pytest.raises(ValidationError):
            PrincipleAssertion(
                principle_statement="test",
                verbatim_quote="test",
                explicit_or_inferred="explicit",
                reasoning="test",
                confidence=-0.1,
            )

    def test_confidence_bounds_high(self):
        with pytest.raises(ValidationError):
            PrincipleAssertion(
                principle_statement="test",
                verbatim_quote="test",
                explicit_or_inferred="explicit",
                reasoning="test",
                confidence=1.1,
            )

    def test_audience_hint_optional(self):
        p = PrincipleAssertion(
            principle_statement="test",
            verbatim_quote="test",
            explicit_or_inferred="explicit",
            reasoning="test",
            confidence=0.5,
        )
        assert p.audience_hint is None

    def test_audience_hint_provided(self):
        p = PrincipleAssertion(
            principle_statement="test",
            verbatim_quote="test",
            explicit_or_inferred="explicit",
            reasoning="test",
            confidence=0.5,
            audience_hint="public conference",
        )
        assert p.audience_hint == "public conference"

    def test_json_roundtrip(self):
        p = PrincipleAssertion(
            principle_statement="Faith is essential",
            verbatim_quote="we must have faith",
            explicit_or_inferred="explicit",
            reasoning="Direct statement",
            confidence=0.95,
            audience_hint="the Saints",
        )
        data = p.model_dump()
        p2 = PrincipleAssertion(**data)
        assert p == p2
