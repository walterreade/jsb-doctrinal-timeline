# Metadata Implementation Plan

## Current State vs. Required State

### What We Have Now ✅

**Document-level metadata:**
- Title: "Journal, 1832–1834"
- Recorder: "JS" (Joseph Smith)
- Event date range: 1832-11-28 to 1834-12-05
- Provenance class: contemporary_diary
- Source type: primary

**Assertion-level metadata (from LLM):**
- Audience hints: "personal prayer", "lay ministry", "Latter-day Saints", etc.
- These are **inferred** by the LLM from context, not extracted from structure

### What's Missing ❌

**Entry-level granular metadata:**
- Specific date for each journal entry (e.g., "1832-12-04")
- Specific recorder/scribe for each entry (Oliver Cowdery, Frederick Williams, etc.)
- Specific audience when mentioned (e.g., "spoke to brethren at meeting")
- Recording context (contemporaneous vs. later recollection)

**Why it's missing:**
Our current chunking is **semantic** (splits on paragraph/sentence boundaries) rather than **structural** (splits on journal entry boundaries). This means:
- One chunk might contain parts of multiple journal entries
- We lose the date markers that were in the XML

## Solution: Phase 5 Implementation

### Approach 1: Re-chunk by Journal Entry (Recommended)

**Strategy:** Parse XML to identify `<ab type="journal-entry-divider">` tags and chunk by entry

**Benefits:**
- Each chunk has a specific date
- Each chunk has a specific recorder (from handwriting analysis)
- Principles inherit exact metadata from their entry
- Matches the provenance model in the SPEC

**Implementation:**
```python
def chunk_by_journal_entry(xml_path: str) -> list[ChunkMetadata]:
    """Chunk document by journal entry boundaries."""
    parser = TEIParser(xml_path)
    
    # Find all journal entry dividers with dates
    dividers = parser.root.findall(
        ".//tei:ab[@type='journal-entry-divider']",
        parser.NS
    )
    
    for divider in dividers:
        # Extract date from divider
        date_elem = divider.find(".//tei:date", parser.NS)
        entry_date = date_elem.get("when-iso") or date_elem.get("from-iso")
        
        # Extract entry text until next divider
        entry_text = extract_entry_text(divider)
        
        # Create chunk with metadata
        yield ChunkMetadata(
            chunk_text=entry_text,
            event_date_edtf=entry_date,
            recorder=identify_recorder(entry_text),  # From handwriting notes
            audience=None,  # Will be extracted by LLM
        )
```

### Approach 2: Post-Process Current Chunks (Simpler)

**Strategy:** Map each chunk back to journal entries using character offsets

**Benefits:**
- Don't need to re-chunk
- Don't need to re-extract
- Can add metadata retroactively

**Implementation:**
```python
def add_entry_metadata_to_assertions():
    """Add journal entry metadata to existing assertions."""
    
    # Parse XML to get entry date ranges
    entry_map = parse_journal_entry_dates(xml_path)
    # Returns: [(start_offset, end_offset, date, recorder), ...]
    
    # For each assertion, find which entry it came from
    for assertion in assertions:
        char_offset = assertion.char_start
        
        # Find matching entry
        for start, end, date, recorder in entry_map:
            if start <= char_offset < end:
                # Update assertion metadata
                update_assertion_metadata(
                    assertion_id=assertion.id,
                    event_date_edtf=date,
                    recorder=recorder
                )
                break
```

## What Metadata Exists in J1.xml

### Date Information
Every journal entry has a date in ISO format:
```xml
<ab type="journal-entry-divider">
    <date when-iso="1832-12-04">4 December 1832</date> • Tuesday
</ab>
```

**Coverage:** 100% of entries have dates

### Recorder/Scribe Information
From the source note (already extracted):
```
handwriting of Oliver Cowdery, JS, Frederick G. Williams,
Parley P. Pratt, Sidney Rigdon, Freeman Nickerson, and six
unidentified scribes
```

**But:** Individual entry-level recorder identification requires:
1. Handwriting analysis (beyond scope)
2. Explicit attributions in text ("Elder Rigdon penned this")
3. Pattern matching (certain dates = certain scribes)

**Coverage:** ~20% explicit, ~50% inferable from patterns

### Audience Information
Mentioned in entry text when relevant:
- "attended meeting" → implied congregation
- "spoke to the brethren" → church members
- "blessed my family" → family
- "private prayer" → personal

**Coverage:** ~30% explicit, ~60% inferable by LLM

## Recommended Implementation Path

### Step 1: Add Entry-Date Mapping (30 minutes)
```python
# scripts/add_entry_dates.py
"""Map assertions to journal entry dates."""

import re
from lxml import etree
from pipeline.utils.db import Database

def extract_entry_boundaries(xml_path):
    """Extract (offset, date) pairs for each journal entry."""
    tree = etree.parse(xml_path)
    # ... parse entry dividers and compute offsets
    return entry_map

def update_assertion_dates(db_path, xml_path, normalized_text):
    """Update all assertions with entry dates."""
    entry_map = extract_entry_boundaries(xml_path)
    
    with Database(db_path) as db:
        assertions = db.execute("SELECT id, char_start FROM assertions")
        
        for assertion in assertions:
            # Find which entry this assertion came from
            entry_date = find_entry_for_offset(
                assertion['char_start'],
                entry_map,
                normalized_text
            )
            
            # Update assertion
            db.execute(
                "UPDATE assertions SET event_date_edtf = ? WHERE id = ?",
                (entry_date, assertion['id'])
            )
```

### Step 2: Enhance Database Schema (5 minutes)
```sql
-- Add entry-level metadata columns to assertions
ALTER TABLE assertions ADD COLUMN event_date_edtf TEXT;
ALTER TABLE assertions ADD COLUMN entry_recorder TEXT;

-- Create index for date queries
CREATE INDEX idx_assertions_date ON assertions(event_date_edtf);
```

### Step 3: Create Metadata Query Views (10 minutes)
```sql
-- View with full metadata
CREATE VIEW principles_with_full_metadata AS
SELECT
    a.id,
    a.principle_statement,
    a.verbatim_quote,
    a.explicit_or_inferred,
    a.confidence,
    a.audience,
    -- Entry-level metadata
    a.event_date_edtf AS entry_date,
    a.entry_recorder,
    -- Document-level metadata  
    d.title AS document_title,
    d.recorder AS primary_recorder,
    d.provenance_class,
    d.source_type,
    -- Verification
    a.verification,
    a.fuzzy_score
FROM assertions a
JOIN documents d ON a.document_sha256 = d.sha256
ORDER BY a.event_date_edtf, a.id;
```

## Expected Output After Implementation

### Query: Principles by Date
```sql
SELECT 
    event_date_edtf,
    COUNT(*) as principle_count
FROM assertions
GROUP BY event_date_edtf
ORDER BY event_date_edtf;
```

**Expected Result:**
```
event_date_edtf  | principle_count
-----------------|----------------
1832-11-27       | 2
1832-11-28       | 3
1832-12-04       | 5
1833-10-04       | 4
...
```

### Query: Principle with Full Metadata
```sql
SELECT 
    principle_statement,
    event_date_edtf,
    entry_recorder,
    audience,
    provenance_class
FROM principles_with_full_metadata
WHERE principle_statement LIKE '%temple%'
LIMIT 5;
```

**Expected Result:**
```
principle_statement                              | event_date  | recorder | audience      | provenance
-------------------------------------------------|-------------|----------|---------------|------------------
Believers are promised endowment from on high    | 1833-12-18  | JS       | Saints        | contemporary_diary
The ritual washing of feet is preparatory        | 1834-01-05  | Cowdery  | lay ministry  | contemporary_diary
...
```

## Effort Estimate

| Task | Time | Difficulty |
|------|------|------------|
| Parse entry boundaries from XML | 30 min | Easy |
| Map assertions to entries | 30 min | Medium |
| Update database schema | 5 min | Easy |
| Run metadata update script | 5 min | Easy |
| Create query views | 10 min | Easy |
| Test and validate | 20 min | Easy |
| **Total** | **~2 hours** | **Low** |

## Current Workaround

Until Phase 5 is implemented, you can:

1. **Use document-level metadata:**
   - All principles are from "Journal, 1832-1834"
   - Primary recorder: JS (Joseph Smith)
   - Date range: 1832-11-28 to 1834-12-05

2. **Use LLM-inferred audience:**
   - Already populated in `assertions.audience` column
   - Examples: "personal prayer", "lay ministry", "Latter-day Saints"

3. **Manual date lookup:**
   - Use `char_start` offset to find position in normalized text
   - Cross-reference with XML to find which journal entry
   - This is tedious but works for spot-checking

## Next Steps

Would you like me to:
1. **Implement the entry-date mapping now** (~1 hour)?
2. **Just show you how to query existing metadata** (5 minutes)?
3. **Create a sample with 10-20 principles showing full metadata** (15 minutes)?

The infrastructure is all there - we just need to connect the assertions back to their source journal entries via the offset mapping.
