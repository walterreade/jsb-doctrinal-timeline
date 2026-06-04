"""Simple test of Gemini API connection."""

import json
import os

from google import genai
from google.genai import types

# Get API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    # Try loading from .env
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("ERROR: GEMINI_API_KEY not found")
    exit(1)

print(f"API key loaded: {api_key[:20]}...")

# Initialize client
client = genai.Client(api_key=api_key)

# Simple test prompt
prompt = """Extract doctrinal principles from this text. Return a JSON array.

Text: "God himself was once as we are now, and is an exalted man"

Return format: [{"principle": "...", "quote": "..."}]
"""

print("\nSending test request...")

try:
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )

    print("\n✓ API call successful!")
    print(f"\nResponse text:\n{response.text}")

    # Parse JSON
    data = json.loads(response.text)
    print(f"\n✓ Valid JSON response")
    print(f"Parsed data: {json.dumps(data, indent=2)}")

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
