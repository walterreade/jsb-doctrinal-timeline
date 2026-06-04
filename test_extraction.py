"""Quick test of extraction on one chunk."""

from pipeline.config import config
from pipeline.llm.gemini_client import GeminiClient
from pipeline.utils.db import Database

# Test with first chunk
with Database(config.db_path) as db:
    cursor = db.execute("SELECT * FROM chunks ORDER BY chunk_index LIMIT 1")
    chunk = dict(cursor.fetchone())

    cursor = db.execute("SELECT * FROM documents WHERE sha256 = ?", (chunk["document_sha256"],))
    doc = dict(cursor.fetchone())

    print(f"Testing extraction on chunk #{chunk['chunk_index']}")
    print(f"Chunk length: {len(chunk['chunk_text'])} chars")
    print(f"Preview: {chunk['chunk_text'][:200]}...\n")

    client = GeminiClient()

    principles = client.extract_principles(
        chunk_text=chunk["chunk_text"],
        document_context={
            "title": doc["title"],
            "recorder": doc["recorder"],
            "event_date_edtf": doc["event_date_edtf"],
        },
    )

    print(f"\nExtracted {len(principles)} principles:\n")

    for i, p in enumerate(principles, 1):
        print(f"{i}. {p.principle_statement}")
        print(f"   Quote: \"{p.verbatim_quote[:100]}...\"")
        print(f"   Type: {p.explicit_or_inferred}, Confidence: {p.confidence}")
        print()
