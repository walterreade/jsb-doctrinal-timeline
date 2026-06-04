-- Create comprehensive metadata views for querying principles

-- View 1: Principles with full metadata
CREATE VIEW IF NOT EXISTS principles_full_metadata AS
SELECT
    a.id,
    a.principle_statement,
    a.verbatim_quote,
    a.explicit_or_inferred,
    a.confidence,

    -- Entry-level metadata
    a.event_date_edtf AS entry_date,
    a.audience,

    -- Document-level metadata
    d.title AS document_title,
    d.recorder AS primary_recorder,
    d.provenance_class,
    d.source_type,
    d.repository,

    -- Verification metadata
    a.verification,
    a.fuzzy_score,

    -- Provenance (offsets)
    a.char_start,
    a.char_end,
    a.chunk_id,
    d.sha256 AS document_sha256,

    -- Quality metadata
    a.reasoning,
    a.created_at
FROM assertions a
JOIN documents d ON a.document_sha256 = d.sha256
ORDER BY a.event_date_edtf, a.id;

-- View 2: Principles by date summary
CREATE VIEW IF NOT EXISTS principles_by_date AS
SELECT
    event_date_edtf AS date,
    COUNT(*) AS principle_count,
    COUNT(CASE WHEN explicit_or_inferred = 'explicit' THEN 1 END) AS explicit_count,
    COUNT(CASE WHEN explicit_or_inferred = 'inferred' THEN 1 END) AS inferred_count,
    ROUND(AVG(confidence), 3) AS avg_confidence,
    COUNT(CASE WHEN verification = 'exact' THEN 1 END) AS exact_matches,
    COUNT(CASE WHEN verification = 'fuzzy' THEN 1 END) AS fuzzy_matches
FROM assertions
WHERE event_date_edtf IS NOT NULL
GROUP BY event_date_edtf
ORDER BY event_date_edtf;

-- View 3: Principles by audience
CREATE VIEW IF NOT EXISTS principles_by_audience AS
SELECT
    audience,
    COUNT(*) AS principle_count,
    ROUND(AVG(confidence), 3) AS avg_confidence,
    COUNT(CASE WHEN explicit_or_inferred = 'explicit' THEN 1 END) AS explicit_count,
    COUNT(CASE WHEN explicit_or_inferred = 'inferred' THEN 1 END) AS inferred_count
FROM assertions
WHERE audience IS NOT NULL
GROUP BY audience
ORDER BY principle_count DESC;

-- View 4: High-confidence explicit principles
CREATE VIEW IF NOT EXISTS principles_high_confidence_explicit AS
SELECT
    principle_statement,
    verbatim_quote,
    event_date_edtf AS entry_date,
    audience,
    confidence,
    verification
FROM assertions
WHERE explicit_or_inferred = 'explicit'
  AND confidence >= 0.90
ORDER BY event_date_edtf, confidence DESC;

-- View 5: Quarantined extractions for review
CREATE VIEW IF NOT EXISTS quarantine_review AS
SELECT
    id,
    principle_statement,
    attempted_quote,
    reason,
    document_sha256,
    chunk_id,
    created_at
FROM quarantine
WHERE reason != 'pending_verification'
ORDER BY created_at DESC;
