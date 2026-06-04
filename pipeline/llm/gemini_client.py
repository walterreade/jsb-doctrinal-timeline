"""Gemini API client for structured principle extraction."""

import json
import logging
from typing import Any

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

from pipeline.config import config
from pipeline.models.principle import PrincipleAssertion

logger = logging.getLogger(__name__)


class GeminiClient:
    """Client for Gemini API with structured output."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        """Initialize Gemini client.

        Args:
            api_key: Gemini API key (defaults to config)
            model: Model name (defaults to config)
        """
        self.api_key = api_key or config.gemini_api_key
        self.model_name = model or config.gemini_model

        if not self.api_key:
            raise ValueError("Gemini API key not configured")

        # Initialize client
        self.client = genai.Client(api_key=self.api_key)

        logger.info(f"Initialized Gemini client with model: {self.model_name}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def extract_principles(
        self,
        chunk_text: str,
        document_context: dict[str, Any],
    ) -> list[PrincipleAssertion]:
        """Extract principles from a text chunk using structured output.

        Args:
            chunk_text: Text to extract principles from
            document_context: Metadata about the source document

        Returns:
            List of extracted PrincipleAssertion objects

        Raises:
            Exception: If API call fails after retries
        """
        prompt = self._build_extraction_prompt(chunk_text, document_context)

        logger.debug(f"Sending extraction request for {len(chunk_text)} chars")

        try:
            # Use JSON mode for structured output
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3,  # Lower temperature for more consistent extraction
                ),
            )

            return self._parse_response(response)

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            raise

    def _parse_response(self, response: Any) -> list[PrincipleAssertion]:
        """Parse Gemini response into PrincipleAssertion objects.

        Args:
            response: Gemini API response

        Returns:
            List of PrincipleAssertion objects
        """
        if not response.text:
            logger.warning("Empty response from Gemini")
            return []

        data = json.loads(response.text)

        # Handle both array and object responses
        if isinstance(data, list):
            principles_data = data
        elif isinstance(data, dict) and "principles" in data:
            principles_data = data["principles"]
        else:
            logger.warning(f"Unexpected response format: {type(data)}")
            return []

        principles = [PrincipleAssertion(**item) for item in principles_data]
        logger.info(f"Extracted {len(principles)} principles")
        return principles

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def glean_principles(
        self,
        chunk_text: str,
        existing_principles: list[dict[str, str]],
        document_context: dict[str, Any],
    ) -> list[PrincipleAssertion]:
        """Find additional principles missed by the initial extraction.

        Args:
            chunk_text: Text to re-analyze
            existing_principles: Already-extracted principles (list of dicts with
                'principle' and 'quote' keys)
            document_context: Metadata about the source document

        Returns:
            List of newly found PrincipleAssertion objects
        """
        prompt = self._build_glean_prompt(chunk_text, existing_principles, document_context)

        logger.debug(f"Sending glean request for {len(chunk_text)} chars "
                     f"({len(existing_principles)} existing)")

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                ),
            )
            return self._parse_response(response)

        except Exception as e:
            logger.error(f"Glean failed: {e}")
            raise

    def _build_extraction_prompt(
        self, chunk_text: str, document_context: dict[str, Any]
    ) -> str:
        """Build the extraction prompt with few-shot examples.

        Args:
            chunk_text: Text chunk to process
            document_context: Document metadata for context

        Returns:
            Complete prompt string
        """
        title = document_context.get("title", "Unknown")
        recorder = document_context.get("recorder", "Unknown")
        date = document_context.get("event_date_edtf", "Unknown date")

        prompt = f"""You are an expert historian analyzing the writings of Joseph Smith Jr., founder of the Latter-day Saint movement. Your task is to extract discrete doctrinal, philosophical, or theological principles from historical manuscripts.

**Document Context:**
- Title: {title}
- Recorder/Scribe: {recorder}
- Date: {date}

**Instructions:**
1. Extract ONLY principles that are explicitly taught or clearly inferred by Joseph Smith
2. Each principle must be ATOMIC (one teaching per assertion)
3. Make principles DECONTEXTUALIZED (self-contained, understandable without surrounding text)
4. Copy `verbatim_quote` EXACTLY character-for-character from the source text below (NEVER paraphrase)
5. Flag each as "explicit" (directly stated) or "inferred" (logically entailed but not verbatim)
6. Provide reasoning for why each qualifies as a principle (audit trail)
7. If the text contains NO principles (e.g., purely administrative or narrative), return an empty array []

**Output Format:**
Return a JSON array of objects, where each object has these fields:
- principle_statement (string): The extracted principle
- verbatim_quote (string): Exact quote from source text
- explicit_or_inferred (string): Either "explicit" or "inferred"
- reasoning (string): Why this qualifies as a principle
- confidence (number): 0.0 to 1.0
- audience_hint (string or null): Audience context if identifiable

**Few-Shot Examples:**

Example 1 - Explicit principle:
Input: "God himself was once as we are now, and is an exalted man, and sits enthroned in yonder heavens"
Output: [{{
  "principle_statement": "God was once a mortal man who became exalted",
  "verbatim_quote": "God himself was once as we are now, and is an exalted man",
  "explicit_or_inferred": "explicit",
  "reasoning": "Joseph Smith directly states that God was once in a mortal state like humans currently are, representing a unique theological teaching about the nature of deity",
  "confidence": 0.95,
  "audience_hint": "public conference"
}}]

Example 2 - Inferred principle:
Input: "I attended meeting and heard Elder Rigdon preach on the duty of parents to teach their children the principles of the gospel"
Output: [{{
  "principle_statement": "Parents have a duty to teach their children gospel principles",
  "verbatim_quote": "the duty of parents to teach their children the principles of the gospel",
  "explicit_or_inferred": "inferred",
  "reasoning": "While this reports Sidney Rigdon's sermon rather than Joseph Smith's direct words, the principle is presented as doctrinal instruction in Joseph's journal, suggesting implicit endorsement",
  "confidence": 0.75,
  "audience_hint": "meeting attendees"
}}]

Example 3 - No principles (administrative):
Input: "Attended to some business in the store today. Weather was fair and pleasant. Received a letter from Brother Hyrum."
Output: []

**Text to analyze:**

{chunk_text}

**Task:** Extract all doctrinal, philosophical, or theological principles taught by Joseph Smith in the above text. Return ONLY a valid JSON array (no markdown formatting, no code blocks).
"""
        return prompt

    def _build_glean_prompt(
        self,
        chunk_text: str,
        existing_principles: list[dict[str, str]],
        document_context: dict[str, Any],
    ) -> str:
        """Build the glean prompt for finding missed principles.

        Args:
            chunk_text: Text chunk to re-analyze
            existing_principles: Already-extracted principles
            document_context: Document metadata for context

        Returns:
            Complete prompt string
        """
        title = document_context.get("title", "Unknown")
        recorder = document_context.get("recorder", "Unknown")
        date = document_context.get("event_date_edtf", "Unknown date")

        existing_json = json.dumps(existing_principles, indent=2)

        return f"""You are an expert historian analyzing the writings of Joseph Smith Jr. A first-pass extraction has already identified some doctrinal principles from this passage. Your task is to find any ADDITIONAL principles that were MISSED.

**Document Context:**
- Title: {title}
- Recorder/Scribe: {recorder}
- Date: {date}

**Rules:**
1. Only report NEW principles not already covered by the existing list
2. Each principle must be grounded in a verbatim quote from the passage
3. Copy `verbatim_quote` EXACTLY character-for-character (NEVER paraphrase)
4. Flag each as "explicit" (directly stated) or "inferred" (logically entailed but not verbatim)
5. If nothing was missed, return an empty array []

**Passage:**

{chunk_text}

**Already Extracted ({len(existing_principles)} principles):**
{existing_json}

**Output Format:**
Return a JSON array of objects with these fields:
- principle_statement (string): The new principle
- verbatim_quote (string): Exact quote from source text
- explicit_or_inferred (string): Either "explicit" or "inferred"
- reasoning (string): Why this was missed and why it qualifies
- confidence (number): 0.0 to 1.0
- audience_hint (string or null): Audience context if identifiable

Return ONLY a valid JSON array (no markdown, no code blocks). Return [] if nothing new.
"""
