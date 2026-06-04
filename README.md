# Joseph Smith Doctrinal Principles Extraction Pipeline

A provenance-grade computational pipeline for extracting, verifying, and organizing doctrinal principles from Joseph Smith's historical writings.

## Overview

This pipeline processes TEI-XML documents from the Joseph Smith Papers Project (JSPP) and extracts discrete doctrinal, philosophical, and theological principles with full provenance tracking and deterministic quote verification.

### Trial Phase Status

Currently implementing trial scope on **J1.xml** (Journal, 1832-1834) before scaling to the full JSPP corpus.

## Features

✅ **Implemented (Phases 1-4)**
- TEI-XML parsing with clear text generation
- Content-addressable storage (SHA-256)
- Semantic chunking with absolute character offsets
- LLM-based principle extraction (Gemini structured output)
- Deterministic quote verification (exact + fuzzy matching)
- Full provenance metadata tracking
- SQLite database with integrity constraints

🚧 **Pending (Phases 5-6)**
- EDTF date normalization
- Audience/recorder metadata extraction
- Quality metrics and evaluation
- Export utilities (CSV/JSON)

## Quick Start

### Prerequisites

- Python 3.12+
- Gemini API key
- `uv` package manager

### Installation

```bash
# Install dependencies
uv sync --dev

# Set up environment variables
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### Initialize Database

```bash
uv run python -m pipeline.main init
```

### Run Full Pipeline

```bash
# 1. Ingest TEI-XML document
uv run python -m pipeline.main ingest xml_files/Journals/J1.xml

# 2. Chunk document (creates semantic chunks with offsets)
uv run python -m pipeline.main chunk <document_sha256>

# 3. Extract principles (uses Gemini API)
uv run python -m pipeline.main extract <document_sha256>

# 4. Verify quotes (deterministic verification)
uv run python -m pipeline.main verify <document_sha256>

# 5. View statistics
uv run python -m pipeline.main stats
```

## Architecture

### Pipeline Stages

```
Stage 0: Ingest
├─ Parse TEI-XML (lxml)
├─ Extract metadata from teiHeader
├─ Generate clear text (strip diplomatic markup)
└─ Store in content-addressable storage

Stage 1: Chunk
├─ Semantic chunking (LangChain RecursiveCharacterTextSplitter)
├─ Compute absolute character offsets
└─ Validate offsets against normalized text

Stage 2: Extract
├─ LLM extraction (Gemini 3.5 Flash)
├─ Structured output (Pydantic schema validation)
├─ Few-shot prompting
└─ Rate limiting (tenacity + exponential backoff)

Stage 3: Verify
├─ Exact match (str.find)
├─ Fuzzy fallback (rapidfuzz ≥90 threshold)
├─ Compute document-absolute offsets
└─ Quarantine unverifiable quotes

Stage 4: Date Normalization (TODO)
└─ EDTF date parsing with bounds

Stage 5: Metadata Extraction (TODO)
└─ Audience, recorder, event dates

Stage 6: Quality Assurance (TODO)
└─ Metrics, audit, manual review
```

### Database Schema

```sql
documents       -- Source documents (SHA-256 addressable)
  ├─ sha256 (PK)
  ├─ title, recorder, dates (EDTF)
  ├─ provenance_class (W3C PROV-style)
  └─ normalized_text (frozen after ingest)

chunks          -- Semantic chunks with offsets
  ├─ id (PK)
  ├─ document_sha256 (FK)
  ├─ char_start, char_end (absolute offsets)
  └─ chunk_text

assertions      -- Verified principles
  ├─ id (PK)
  ├─ document_sha256, chunk_id (FK)
  ├─ principle_statement (atomic, decontextualized)
  ├─ verbatim_quote (exact from source)
  ├─ char_start, char_end (verified offsets)
  ├─ verification (exact | fuzzy)
  ├─ fuzzy_score, confidence
  └─ explicit_or_inferred

quarantine      -- Unverifiable extractions
  ├─ id (PK)
  ├─ raw_json (original LLM response)
  ├─ attempted_quote
  └─ reason (why quarantined)
```

## Success Criteria (Trial Phase)

| Metric | Target | Current |
|--------|--------|---------|
| Verification rate | ≥95% | TBD |
| Quarantine rate | ≤10% | TBD |
| Offset coverage | 100% | ✅ 100% |
| Principles extracted | 50-200 | TBD |

## Configuration

Edit `pipeline/config.py` or set environment variables:

```python
# Database
db_path = "data/j1_principles.db"
cas_dir = "data/objects"

# LLM
gemini_api_key = "..."  # From .env
gemini_model = "gemini-3.5-flash"

# Extraction
chunk_size = 1000        # Character-based
chunk_overlap = 200
fuzzy_threshold = 90.0   # Minimum similarity score
min_confidence = 0.5
```

## Project Structure

```
jsb-doctrinal-timeline/
├── pipeline/
│   ├── models/          # Pydantic schemas
│   ├── stages/          # Pipeline stages (0-5)
│   ├── utils/           # TEI parsing, DB, CAS, fuzzy matching
│   ├── llm/             # Gemini client
│   └── config.py
├── xml_files/
│   └── Journals/J1.xml  # Trial corpus
├── data/                # Runtime data (gitignored)
│   ├── j1_principles.db # SQLite database
│   ├── objects/         # Content-addressable store
│   └── logs/            # Structured logs
├── tests/               # Pytest suite
└── scripts/
    └── setup_db.sql     # Database schema
```

## Development

```bash
# Run tests
uv run pytest

# Lint and format
uv run ruff check .
uv run ruff format .
uv run mypy pipeline/

# Type checking
uv run mypy --strict pipeline/
```

## Key Design Decisions

### 1. Offset Preservation
- All chunks store **absolute character offsets** into normalized text
- Never trust LLM-reported positions
- Validate: `normalized_text[char_start:char_end] == chunk_text`

### 2. Normalization Freeze
- Clear text generated **once** at ingest
- SHA-256 hash stored for integrity
- All downstream offsets relative to frozen text
- **Never normalize again** or offsets drift

### 3. Deterministic Verification
- Exact match first (`str.find`)
- Fuzzy fallback (`rapidfuzz ≥90`) for OCR variance
- **Zero tolerance:** unverifiable → quarantine
- Constrained to originating chunk (avoid cross-span false positives)

### 4. Provenance Tracking
- Three-date split: `event_date` (taught) vs `record_date` (written)
- W3C PROV-style classification
- Every assertion links to `document_sha256` + verified offsets
- Cardinal rule: **Never merge accounts** (each scribe = separate document)

## Limitations

- **Preview models:** `gemini-3-flash-preview` may change before GA
- **Rate limits:** Not published per-model; monitor AI Studio
- **TEI parsing edge cases:** Lenient mode handles most, but complex markup may need refinement
- **Fuzzy matching:** Approximate alignment; rare edge cases may mis-locate spans

## References

- [Joseph Smith Papers Project](https://josephsmithpapers.org)
- [SPEC.md](SPEC.md) - Detailed specification
- [deep-research-doctrinal-principles-timeline.md](deep-research-doctrinal-principles-timeline.md) - Research synthesis

## License

Research project - see project owner for licensing.
