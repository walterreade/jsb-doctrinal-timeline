# SPEC: Joseph Smith Doctrinal Principles Extraction Pipeline (Trial Phase)

**Version:** 0.1.0 (Trial Scope)  
**Target Corpus:** `xml_files/Journals/J1.xml` (Journal, 1832–1834)  
**Status:** Specification Draft  
**Created:** 2026-06-03

---

## 1. Objective

Build a **provenance-grade computational pipeline** to extract, verify, and organize discrete doctrinal and philosophical principles taught by Joseph Smith Jr. from historical TEI-XML manuscripts, starting with a single journal (J1.xml) as a trial implementation.

### 1.1 Success Criteria (Trial Phase)

- Extract **all** verifiable principle assertions from J1.xml (estimated 50-200 principles)
- Achieve **≥95% quote verification rate** (exact or high-confidence fuzzy match)
- Generate a **queryable SQLite database** with full provenance metadata
- Quarantine rate **<10%** (indicates prompt/normalization health)
- **Zero assertions** admitted without computed character offsets

### 1.2 Target Users

- LDS scholars and researchers studying Joseph Smith's doctrinal development
- Digital humanities researchers working with historical corpora
- This implementation team (learning/prototyping before scaling to full JSPP)

### 1.3 Non-Goals (Trial Phase)

- ❌ Multi-document deduplication (clustering across multiple sermons)
- ❌ Human-in-the-loop annotation UI
- ❌ Inductive taxonomy discovery (HDBSCAN/BERTopic clustering)
- ❌ King Follett Discourse multi-account convergence testing
- ❌ Production deployment infrastructure

---

## 2. Commands

### 2.1 Core Pipeline Commands

```bash
# Full pipeline execution (trial)
python -m pipeline.main --input xml_files/Journals/J1.xml --output data/j1_principles.db

# Stage-by-stage execution (for debugging)
python -m pipeline.stages.ingest --input xml_files/Journals/J1.xml
python -m pipeline.stages.chunk --document-sha256 <hash>
python -m pipeline.stages.extract --chunk-ids <id1,id2,...>
python -m pipeline.stages.verify --assertion-ids <id1,id2,...>

# Quality checks
python -m pipeline.audit --database data/j1_principles.db
python -m pipeline.stats --database data/j1_principles.db

# Query examples
python -m pipeline.query --database data/j1_principles.db \
  --date-range "1832-11-01/1834-12-31" \
  --audience public \
  --confidence-min 0.8
```

### 2.2 Development Commands

```bash
# Setup
make install          # Install dependencies (uv-based)
make setup-db         # Initialize SQLite schema with sqlite-vec

# Testing
make test             # Run pytest suite
make test-stage       # Test individual pipeline stage
make test-integration # End-to-end pipeline test on sample

# Quality
make lint             # ruff + mypy
make format           # ruff format
make verify-offsets   # Validate all offsets are computable

# Data inspection
make inspect-xml      # Parse J1.xml and show structure
make show-chunks      # Display chunking results
make show-quarantine  # Review quarantined extractions
```

---

## 3. Project Structure

```
jsb-doctrinal-timeline/
├── SPEC.md                          # This file
├── README.md                        # User-facing documentation
├── pyproject.toml                   # uv project definition
├── uv.lock                          # Locked dependencies
├── .python-version                  # Python 3.12
│
├── xml_files/
│   └── Journals/
│       └── J1.xml                   # Trial corpus (2.4MB, 18K lines)
│
├── data/                            # Runtime data (gitignored)
│   ├── objects/                     # Content-addressable store (SHA-256)
│   ├── j1_principles.db             # SQLite database with sqlite-vec
│   └── logs/                        # Structured pipeline logs
│
├── pipeline/
│   ├── __init__.py
│   ├── main.py                      # CLI entry point
│   ├── config.py                    # Configuration (API keys, models, thresholds)
│   │
│   ├── models/                      # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── principle.py             # PrincipleAssertion schema
│   │   ├── document.py              # DocumentMetadata schema
│   │   └── chunk.py                 # ChunkMetadata schema
│   │
│   ├── stages/                      # Pipeline stages (each stage is independent)
│   │   ├── __init__.py
│   │   ├── stage_0_ingest.py        # TEI-XML parsing, CAS storage, normalization
│   │   ├── stage_1_chunk.py         # Semantic chunking with offset preservation
│   │   ├── stage_2_extract.py       # LLM-based extraction (Gemini structured output)
│   │   ├── stage_3_verify.py        # Deterministic quote verification
│   │   ├── stage_4_dates.py         # EDTF date normalization
│   │   └── stage_5_metadata.py      # Audience/recorder/event metadata
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── tei_parser.py            # lxml-based TEI parsing
│   │   ├── clear_text.py            # Diplomatic → clear text conversion
│   │   ├── normalization.py         # OCR post-correction (19th-century English)
│   │   ├── cas.py                   # Content-addressable storage
│   │   ├── fuzzy_match.py           # rapidfuzz wrapper for quote verification
│   │   ├── edtf_utils.py            # python-edtf date parsing
│   │   └── db.py                    # SQLite + sqlite-vec database utilities
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── gemini_client.py         # Gemini API client (structured output)
│   │   ├── prompts.py               # Extraction prompt templates (few-shot)
│   │   └── rate_limiter.py          # asyncio-based rate limiting
│   │
│   └── audit/
│       ├── __init__.py
│       ├── stats.py                 # Quality metrics computation
│       ├── quarantine_review.py     # Quarantine analysis
│       └── offset_validator.py      # Verify all offsets are valid
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # pytest fixtures
│   ├── test_tei_parser.py
│   ├── test_chunking.py
│   ├── test_extraction.py
│   ├── test_verification.py
│   ├── test_edtf.py
│   └── test_integration.py          # End-to-end test on J1.xml sample
│
├── scripts/
│   ├── setup_db.sql                 # SQLite schema definition
│   ├── inspect_xml.py               # XML structure exploration
│   └── export_csv.py                # Export principles to CSV/JSON
│
└── docs/
    ├── architecture.md              # Detailed architecture notes
    ├── tei_parsing_guide.md         # TEI-XML parsing rules
    ├── prompting_strategy.md        # LLM prompt engineering notes
    └── evaluation_plan.md           # Metrics and benchmarks
```

---

## 4. Code Style & Conventions

### 4.1 Language & Tools

- **Python 3.12** (type-annotated throughout)
- **uv** for dependency management (fast, modern)
- **Pydantic v2** for all data models
- **lxml** for XML parsing (not BeautifulSoup)
- **sqlite-vec** extension for vector storage
- **asyncio** for API orchestration (no threads)

### 4.2 Style Guide

- **Formatting:** `ruff format` (100 char line length)
- **Linting:** `ruff check` + `mypy --strict`
- **Imports:** Absolute imports only, grouped (stdlib, third-party, local)
- **Naming:**
  - Functions: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
  - Private: `_leading_underscore`
- **Docstrings:** Google style for public APIs
- **Type hints:** Required for all function signatures
- **Error handling:** Explicit exceptions, never bare `except:`

### 4.3 Database Conventions

- **Primary keys:** Integer `id` for tables, `sha256` (TEXT) for documents
- **Foreign keys:** Explicit `REFERENCES` with `ON DELETE CASCADE`
- **Indexes:** Composite indexes on common query patterns
- **Timestamps:** ISO 8601 strings (EDTF for historical dates)
- **Enums:** Stored as TEXT with CHECK constraints

### 4.4 Logging

- **Structured logging:** Use `structlog` with JSON output
- **Levels:**
  - `DEBUG`: Offset computation, fuzzy scores
  - `INFO`: Stage completion, document processed
  - `WARNING`: Quarantine admission, low confidence
  - `ERROR`: API failures, parsing errors
- **Log file rotation:** Daily, 7-day retention

---

## 5. Testing Strategy

### 5.1 Unit Tests

**Coverage target:** ≥85% for core logic

- TEI parsing: Test each transformation rule (del, add, insert, cancel tags)
- Chunking: Verify offset preservation, semantic boundary detection
- Extraction: Mock Gemini responses, test Pydantic validation
- Verification: Test exact match, fuzzy match at various thresholds
- EDTF parsing: Test date range computation (earliest/latest bounds)

### 5.2 Integration Tests

- **End-to-end:** Run full pipeline on a hand-annotated J1.xml excerpt (5-10 entries)
- **Known-good test set:** 20 hand-extracted principles with verified offsets
- **Quarantine test:** Intentionally malformed/ambiguous chunks should quarantine

### 5.3 Property-Based Tests (Hypothesis)

- **Offset invariants:** For any chunk, `char_start + len(chunk_text) == char_end`
- **Roundtrip:** Parsing → clear text → re-parse should be idempotent
- **Quote verification:** Any exact match must have fuzzy score ≥99

### 5.4 Benchmark Tests

- **Performance:** Pipeline should process J1.xml in <10 minutes (excluding API wait)
- **Memory:** Peak RSS <2GB during processing
- **Database size:** Final `.db` file <50MB for J1.xml

---

## 6. Boundaries & Constraints

### 6.1 Always Do

✅ **Preserve provenance**
- Every assertion links to `document_sha256` + exact character offsets
- Store `event_date` (when taught) ≠ `record_date` (when written)
- Record `recorder` (scribe name) separately from `author`

✅ **Verify LLM outputs deterministically**
- Never trust model-reported character positions
- Exact match first, fuzzy fallback with `rapidfuzz` ≥90 threshold
- Quarantine unverifiable quotes (do not silently admit)

✅ **Normalize once, freeze forever**
- Generate clear text at ingest, hash it, store it
- All offsets relative to that frozen string
- Never normalize again downstream

✅ **Type safety**
- Pydantic models for all structured data
- mypy --strict for all code
- SQLite CHECK constraints for enums

✅ **Atomic principles**
- One teaching per assertion
- Force `explicit_or_inferred` flag (distinct handling)
- Decontextualized statements (self-contained)

### 6.2 Ask First Before

⚠️ **Changing normalization rules**
- Altering clear text generation invalidates all offsets
- Requires full corpus re-ingest

⚠️ **Lowering verification thresholds**
- If exact-match rate <90%, fix normalization, don't loosen fuzzy threshold
- Document threshold changes in audit logs

⚠️ **Using different LLM models**
- Output format/quality may vary
- Re-validate schema compliance and few-shot examples

⚠️ **Adding new metadata fields**
- Requires schema migration and backfill strategy

⚠️ **Batch API usage**
- Cheaper but asynchronous, harder to debug
- Prefer sync for trial, batch for scale

### 6.3 Never Do

❌ **Merge multiple accounts into one document**
- Each scribe's record is a separate document (even for same event)
- Convergence is discovered via clustering, not assumed via merging

❌ **Paraphrase verbatim quotes**
- `verbatim_quote` must be character-for-character from chunk

❌ **Admit assertions without verified offsets**
- Zero tolerance: unverifiable → quarantine table

❌ **Use token-based chunking with LangChain `add_start_index`**
- Known bug (issues #17642, #18972, #29884)
- Use character-based splitting or manual `str.find()`

❌ **Trust relative dates from LLM**
- "Thursday" or "spring 1831" must be parsed to EDTF deterministically
- Model can extract, but code must normalize

❌ **Store secrets in code**
- API keys via environment variables only
- `.env` file gitignored

---

## 7. Implementation Plan (Trial Phase)

### Phase 1: Foundation (Week 1)

**Goal:** Ingest J1.xml, generate clean database with metadata

- [ ] Setup: `uv init`, install dependencies (`lxml`, `pydantic`, `sqlite-vec`)
- [ ] Database schema: Implement `setup_db.sql` (documents, chunks, assertions, quarantine)
- [ ] TEI parser: Implement clear text generation (strip `<del>`, keep `<add>`, etc.)
- [ ] Normalization: Basic 19th-century spelling/OCR correction
- [ ] CAS storage: SHA-256 hashing, object storage
- [ ] Metadata extraction: Parse `<teiHeader>` for title, dates, scribes
- [ ] **Milestone:** One document ingested with frozen normalized text

### Phase 2: Chunking (Week 1-2)

**Goal:** Offset-preserving semantic chunking

- [ ] Implement `RecursiveCharacterTextSplitter` (character-based, not token)
- [ ] Compute absolute offsets for each chunk (`char_start`, `char_end`)
- [ ] Validate: `normalized_text[chunk.char_start:chunk.char_end] == chunk.text`
- [ ] Store chunks in database
- [ ] **Milestone:** J1.xml split into ~100-200 semantic chunks with verified offsets

### Phase 3: Extraction (Week 2)

**Goal:** LLM-based principle extraction with structured output

- [ ] Pydantic schema: `PrincipleAssertion` model
- [ ] Gemini client: Implement `response_schema` structured output
- [ ] Few-shot prompts: 2-3 hand-built examples from J1.xml
- [ ] Asyncio orchestration: Semaphore-based rate limiting
- [ ] Batch processing: Process all chunks, store raw results
- [ ] **Milestone:** 50-200 principle candidates extracted

### Phase 4: Verification (Week 2-3)

**Goal:** Deterministic quote verification to provenance-grade standard

- [ ] Exact match: `chunk_text.find(assertion.verbatim_quote)`
- [ ] Fuzzy fallback: `rapidfuzz.partial_ratio_alignment()` with threshold ≥90
- [ ] Offset computation: Convert chunk-relative → document-absolute
- [ ] Quarantine: Unverifiable assertions → `quarantine` table with reason
- [ ] **Milestone:** ≥95% verification rate, <10% quarantine rate

### Phase 5: Date & Metadata Normalization (Week 3)

**Goal:** EDTF dates, audience/recorder extraction

- [ ] EDTF parser: `python-edtf` integration
- [ ] Date extraction: Regex + NER for date expressions
- [ ] Compute `event_date_earliest`/`latest` bounds
- [ ] Audience heuristics: Public vs. private, named groups
- [ ] Recorder extraction: Map scribes from `<teiHeader>`
- [ ] **Milestone:** All assertions have normalized metadata

### Phase 6: Quality Assurance (Week 3-4)

**Goal:** Audit, metrics, and validation

- [ ] Audit script: Verify zero assertions without offsets
- [ ] Stats dashboard: Extraction/verification rates, quarantine breakdown
- [ ] Manual review: Sample 20 random assertions, check faithfulness
- [ ] Integration test: Run full pipeline on J1.xml, validate against known-good set
- [ ] **Milestone:** Pipeline meets all success criteria

### Phase 7: Documentation & Handoff (Week 4)

**Goal:** Prepare for scale-up decision

- [ ] README: Usage instructions, setup guide
- [ ] Architecture doc: Stage-by-stage explanation
- [ ] Evaluation report: Metrics, failure modes, scaling recommendations
- [ ] Export utilities: CSV/JSON export for manual analysis
- [ ] **Milestone:** Trial complete, ready for King Follett or full JSPP

---

## 8. Model & API Specifications

### 8.1 Gemini Configuration

**Primary model:** `gemini-3.5-flash` (stable, GA)

| Use Case | Model | Config | Cost (per 1M tokens) |
|----------|-------|--------|----------------------|
| Principle extraction | `gemini-3.5-flash` | Structured output, thinking=low | $1.50 input / $9.00 output |
| Hard reasoning cases | `gemini-3.5-flash` | Thinking=medium | Same |
| Embedding (future) | `gemini-embedding-001` | `task_type=CLUSTERING`, dim=768 | $0.15 input |

**Structured output:**
```python
response_schema = {
    "response_mime_type": "application/json",
    "response_schema": list[PrincipleAssertion]
}
```

**Rate limits (free tier, estimated):**
- Monitor live limits in AI Studio (no longer published)
- Implement exponential backoff with `tenacity`
- For trial: ~200 chunks × 2 API calls = 400 requests (well within limits)

### 8.2 Alternative: Local Models (If Needed)

If API costs/limits become prohibitive:

- **Extraction:** `llama-3.3-70b-instruct` via `llama.cpp` (requires GPU)
- **Normalization:** Hugging Face `dslim/bert-base-NER` for date/person extraction
- **Embedding:** `sentence-transformers/all-MiniLM-L6-v2` (local, fast)

---

## 9. Database Schema (Core Tables)

```sql
-- Documents (immutable, content-addressable)
CREATE TABLE documents (
    sha256 TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_type TEXT CHECK(source_type IN ('primary', 'secondary')),
    provenance_class TEXT CHECK(provenance_class IN (
        'autograph', 'dictated_revelation', 'contemporary_scribal_record',
        'contemporary_diary', 'later_recollection', 'amalgamation',
        'published_edition'
    )),
    recorder TEXT,  -- Scribe name
    event_date_edtf TEXT,  -- When principle was taught
    event_date_earliest TEXT,
    event_date_latest TEXT,
    record_date_edtf TEXT,  -- When this record was written
    record_date_earliest TEXT,
    record_date_latest TEXT,
    repository TEXT,
    citation TEXT,
    normalized_text_sha256 TEXT,  -- Hash of frozen clear text
    created_at TEXT DEFAULT (datetime('now'))
);

-- Chunks (offset-preserving)
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_sha256 TEXT REFERENCES documents(sha256) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    char_start INTEGER NOT NULL,  -- Absolute offset in normalized_text
    char_end INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(document_sha256, chunk_index)
);

-- Assertions (verified principles)
CREATE TABLE assertions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_sha256 TEXT REFERENCES documents(sha256) ON DELETE CASCADE,
    chunk_id INTEGER REFERENCES chunks(id) ON DELETE CASCADE,
    principle_statement TEXT NOT NULL,  -- Atomic, decontextualized
    verbatim_quote TEXT NOT NULL,  -- Exact span from chunk
    char_start INTEGER NOT NULL,  -- Absolute offset (verified)
    char_end INTEGER NOT NULL,
    explicit_or_inferred TEXT CHECK(explicit_or_inferred IN ('explicit', 'inferred')),
    verification TEXT CHECK(verification IN ('exact', 'fuzzy')) NOT NULL,
    fuzzy_score REAL,  -- NULL if exact, ≥90 if fuzzy
    confidence REAL CHECK(confidence BETWEEN 0 AND 1),
    audience TEXT,  -- 'public', 'private', specific group, or NULL
    created_at TEXT DEFAULT (datetime('now'))
);

-- Quarantine (unverifiable extractions)
CREATE TABLE quarantine (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_sha256 TEXT,
    chunk_id INTEGER,
    raw_json TEXT NOT NULL,  -- Original LLM response
    reason TEXT NOT NULL,  -- Why quarantined (e.g., "fuzzy_score=72 below threshold")
    created_at TEXT DEFAULT (datetime('now'))
);

-- Indexes for common queries
CREATE INDEX idx_assertions_date ON assertions(char_start);  -- For provenance lookup
CREATE INDEX idx_assertions_confidence ON assertions(confidence);
CREATE INDEX idx_chunks_document ON chunks(document_sha256);
```

---

## 10. Key Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Low verification rate (<90%)** | Medium | High | Fix normalization, not thresholds; inspect quarantine |
| **High quarantine rate (>10%)** | Medium | Medium | Improve prompt clarity, add few-shot examples |
| **LLM hallucinated quotes** | High | Critical | Deterministic verification rejects hallucinations |
| **Offset drift after normalization** | Low | Critical | Normalize once, freeze, hash; validate in tests |
| **API rate limits hit** | Low | Medium | Exponential backoff, cache responses, monitor usage |
| **TEI parsing edge cases** | Medium | Medium | Comprehensive test suite, manual XML inspection |
| **Chunk boundaries split principles** | Medium | Low | Semantic chunking + modest overlap (10-30%) |
| **Date ambiguity (e.g., "spring 1831")** | High | Low | EDTF uncertainty flags, store earliest/latest bounds |

---

## 11. Success Metrics (Trial Phase)

### 11.1 Primary Metrics

- **Verification rate:** ≥95% (exact or fuzzy≥90)
- **Quarantine rate:** <10%
- **Offset coverage:** 100% (zero assertions without offsets)
- **Pipeline runtime:** <10 minutes (excluding API latency)

### 11.2 Quality Metrics

- **Atomicity:** Manual review of 20 assertions → all single-teaching
- **Faithfulness:** Manual review → ≥95% accurately reflect source
- **Decontextualization:** Manual review → ≥90% self-contained

### 11.3 Data Metrics

- **Principles extracted:** 50-200 from J1.xml (baseline estimate)
- **Database size:** <50MB
- **Chunk count:** ~100-200 (avg ~500-1000 chars/chunk)

---

## 12. Appendix: Research Document Integration

This SPEC is derived from `deep-research-doctrinal-principles-timeline.md`, focusing on:

- **Stages 0-6** (ingest through metadata extraction)
- **Trial scope:** Single journal (J1.xml) instead of full JSPP
- **Deferred to post-trial:** Deduplication (Stage 7), clustering (Stage 8), vector search (Stage 9)

**Key methodological principles preserved:**
1. Content-addressable immutable storage
2. Offset-preserving chunking (never trust LLM positions)
3. Deterministic verification (never admit unverified quotes)
4. Three-date split (event_date, record_date, recorder)
5. EDTF for historical date uncertainty
6. Cardinal rule: Never merge accounts (each scribe = separate document)

**Next phase decision criteria:**
- If trial succeeds (≥95% verification): Scale to King Follett multi-account test or full J1-J3
- If trial fails (<90% verification): Root-cause analysis, prompt/normalization refinement
- If API costs prohibitive: Evaluate local model alternatives (llama.cpp, vLLM)

---

**Document History:**
- 2026-06-03: Initial draft (trial scope on J1.xml)
