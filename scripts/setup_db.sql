-- Joseph Smith Doctrinal Principles Database Schema
-- SQLite with sqlite-vec extension for future vector storage
-- Created: 2026-06-03

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Documents table (immutable, content-addressable)
CREATE TABLE IF NOT EXISTS documents (
    sha256 TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_type TEXT CHECK(source_type IN ('primary', 'secondary')),
    provenance_class TEXT CHECK(provenance_class IN (
        'autograph',
        'dictated_revelation',
        'contemporary_scribal_record',
        'contemporary_diary',
        'later_recollection',
        'amalgamation',
        'published_edition'
    )),
    recorder TEXT,
    event_date_edtf TEXT,
    event_date_earliest TEXT,
    event_date_latest TEXT,
    record_date_edtf TEXT,
    record_date_earliest TEXT,
    record_date_latest TEXT,
    repository TEXT,
    citation TEXT,
    normalized_text TEXT NOT NULL,
    normalized_text_sha256 TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Chunks table (offset-preserving)
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_sha256 TEXT NOT NULL REFERENCES documents(sha256) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(document_sha256, chunk_index),
    CHECK(char_end > char_start)
);

-- Assertions table (verified principles)
CREATE TABLE IF NOT EXISTS assertions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_sha256 TEXT NOT NULL REFERENCES documents(sha256) ON DELETE CASCADE,
    chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    principle_statement TEXT NOT NULL,
    verbatim_quote TEXT NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    explicit_or_inferred TEXT CHECK(explicit_or_inferred IN ('explicit', 'inferred')),
    verification TEXT CHECK(verification IN ('exact', 'fuzzy')) NOT NULL,
    fuzzy_score REAL CHECK(fuzzy_score IS NULL OR (fuzzy_score >= 0 AND fuzzy_score <= 100)),
    confidence REAL CHECK(confidence BETWEEN 0 AND 1),
    audience TEXT,
    reasoning TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    CHECK(char_end > char_start),
    CHECK((verification = 'exact' AND fuzzy_score IS NULL) OR
          (verification = 'fuzzy' AND fuzzy_score >= 90))
);

-- Quarantine table (unverifiable extractions)
CREATE TABLE IF NOT EXISTS quarantine (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_sha256 TEXT,
    chunk_id INTEGER,
    raw_json TEXT NOT NULL,
    principle_statement TEXT,
    attempted_quote TEXT,
    reason TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_sha256);
CREATE INDEX IF NOT EXISTS idx_assertions_document ON assertions(document_sha256);
CREATE INDEX IF NOT EXISTS idx_assertions_chunk ON assertions(chunk_id);
CREATE INDEX IF NOT EXISTS idx_assertions_confidence ON assertions(confidence);
CREATE INDEX IF NOT EXISTS idx_assertions_verification ON assertions(verification);
CREATE INDEX IF NOT EXISTS idx_quarantine_reason ON quarantine(reason);

-- Metadata view for easy querying
CREATE VIEW IF NOT EXISTS principles_with_metadata AS
SELECT
    a.id,
    a.principle_statement,
    a.verbatim_quote,
    a.explicit_or_inferred,
    a.confidence,
    a.audience,
    a.verification,
    a.fuzzy_score,
    d.title AS document_title,
    d.recorder,
    d.event_date_edtf,
    d.record_date_edtf,
    d.provenance_class,
    d.source_type,
    a.char_start,
    a.char_end
FROM assertions a
JOIN documents d ON a.document_sha256 = d.sha256;
