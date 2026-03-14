# DBLP Import and Benchmark Guide

This guide covers importing DBLP data into ParadeDB and running performance benchmarks.

## Overview

- **arXiv papers**: ~2.97 million (with abstracts and embeddings)
- **DBLP papers**: ~3.90 million (titles, authors, venues; no abstracts)
- **Total after import**: ~6.87 million papers

## Prerequisites

```bash
# Install required packages
pip install psycopg2-binary tqdm lxml sentence-transformers

# Or use uv
uv add psycopg2-binary tqdm lxml sentence-transformers
```

## Database Connection

Set environment variables or use defaults:

```bash
export DB_HOST=127.0.0.1
export DB_PORT=5432
export DB_USER=valiref
export DB_PASSWORD=valiref_secret
export DB_NAME=arxiv_db
```

## Phase 1: Schema Migration

### 1.1 Update Database Schema

Run the updated schema script:

```bash
# Connect to database and run schema update
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f scripts/setup_pgvector.sql
```

### 1.2 Migrate Existing Data

Update existing arXiv papers to have `source='arxiv'`:

```bash
python scripts/migrate_add_source.py
```

This will:
- Add `source` and `venue` columns if not present
- Set `source='arxiv'` for all existing papers
- Create indexes on the new columns
- Rebuild the BM25 index

## Phase 2: Import DBLP Data

### 2.1 Download DBLP XML

```bash
# Download DBLP XML dump (~1GB compressed)
cd /data  # or your preferred data directory
wget https://dblp.org/xml/dblp.xml.gz

# Or download the DTD (optional, for validation)
wget https://dblp.org/xml/dblp.dtd
```

### 2.2 Import DBLP Data

```bash
# Import full DBLP dataset
python scripts/import_dblp.py /data/dblp.xml.gz

# Or import a limited number for testing
python scripts/import_dblp.py /data/dblp.xml.gz --limit 100000
```

Expected performance:
- Parsing speed: ~10,000-20,000 entries/sec
- Import speed: ~5,000-8,000 papers/sec
- Total time: ~8-15 minutes for full import

## Phase 3: Query Data

### 3.1 BM25 Search

```bash
# Simple search
python scripts/query_papers_bm25.py "neural network"

# Filter by source
python scripts/query_papers_bm25.py "machine learning" --source arxiv
python scripts/query_papers_bm25.py "machine learning" --source dblp

# Filter by year range
python scripts/query_papers_bm25.py "transformer" --year-from 2020

# Filter by venue (DBLP)
python scripts/query_papers_bm25.py "attention" --source dblp --venue "EMNLP"

# Combined filters
python scripts/query_papers_bm25.py "large language model" \
    --source arxiv --year-from 2022 --top-k 20
```

### 3.2 Vector Search

```bash
# Search arXiv papers using embeddings (default)
python scripts/query_papers.py "deep reinforcement learning"

# Note: DBLP papers don't have embeddings by default
python scripts/query_papers.py "graph neural networks" --source arxiv
```

## Phase 4: Performance Benchmark

### 4.1 Run Benchmarks

```bash
# Run all benchmarks with default settings
python scripts/benchmark_search.py

# Custom concurrency levels
python scripts/benchmark_search.py --concurrency 10 25 50 --queries 500

# Specific test only
python scripts/benchmark_search.py --test bm25
python scripts/benchmark_search.py --test bm25-filtered
python scripts/benchmark_search.py --test bm25-source

# Save results to JSON
python scripts/benchmark_search.py -o benchmark_results.json
```

### 4.2 Expected Performance

Target metrics:
- **QPS** > 1000 for simple BM25 queries
- **Average latency** < 50ms
- **P99 latency** < 200ms

Typical results on a modern server:
```
Test                      Conc      QPS   Avg(ms)   P99(ms)
-----------------------------------------------------------
BM25 Simple                 10   2500.0      15.2      45.3
BM25 Simple                 50   4800.0      18.5      52.1
BM25 Simple                100   5200.0      22.3      78.4
BM25 Filtered               10   1800.0      22.1      58.7
BM25 arXiv                  10   2100.0      18.9      48.2
BM25 DBLP                   10   2800.0      14.2      38.5
```

## Phase 5: Validation

### 5.1 Run Validation

```bash
# Full validation and report
python scripts/validate_and_report.py

# Validation only
python scripts/validate_and_report.py --validate-only

# Report only
python scripts/validate_and_report.py --report-only

# Save report to JSON
python scripts/validate_and_report.py -o validation_report.json
```

### 5.2 Expected Output

```
DATA DISTRIBUTION:
   Total papers:        6,870,000
   arXiv papers:        2,970,000 (43.2%)
   DBLP papers:         3,900,000 (56.8%)

ARXIV STATISTICS:
   Year range:          1986 - 2024
   With abstract:       2,970,000
   With embedding:      2,970,000

DBLP STATISTICS:
   Year range:          1936 - 2024
   With venue:          3,850,000
```

## Troubleshooting

### Import Errors

**Issue**: `lxml not found`
```bash
pip install lxml  # or uv add lxml
```

**Issue**: Memory error during import
```bash
# The script uses iterative parsing, but if you still have issues:
# 1. Increase Python's garbage collection threshold
# 2. Import in smaller batches with --limit
```

### Performance Issues

**Issue**: Slow queries
```sql
-- Check if indexes exist
SELECT indexname FROM pg_indexes WHERE tablename = 'papers';

-- Rebuild BM25 index if needed
DROP INDEX IF EXISTS idx_papers_bm25;
CREATE INDEX idx_papers_bm25 ON papers
USING bm25(id, title, abstract)
WITH (key_field='id');
```

**Issue**: Connection errors during benchmark
```bash
# Increase PostgreSQL max connections
# In postgresql.conf:
max_connections = 200
```

### Data Validation Failures

**Issue**: Missing source column
```bash
# Re-run migration
python scripts/migrate_add_source.py
```

**Issue**: No embeddings for arXiv papers
```bash
# Generate embeddings (if not already done)
python scripts/generate_embeddings.py --batch-size 1000
```

## File Reference

| File | Purpose |
|------|---------|
| `setup_pgvector.sql` | Database schema with source/venue columns |
| `migrate_add_source.py` | Migrate existing arXiv data |
| `import_dblp.py` | Import DBLP XML to database |
| `query_papers_bm25.py` | BM25 search with source filtering |
| `query_papers.py` | Vector search (arXiv only) |
| `benchmark_search.py` | Performance benchmark tool |
| `validate_and_report.py` | Data validation and reporting |

## Storage Requirements

- DBLP XML (compressed): ~1 GB
- DBLP XML (uncompressed): ~5 GB
- PostgreSQL data (after import): ~15-20 GB additional
- Total recommended disk space: 50+ GB

## Memory Requirements

- Minimum: 4 GB RAM
- Recommended: 8 GB RAM
- Import process: 2-4 GB peak

## Notes

1. **DBLP has no abstracts**: BM25 searches on DBLP papers only match titles
2. **Vector search only works on arXiv**: DBLP papers have NULL embeddings
3. **Venue field is DBLP-specific**: arXiv papers have NULL venue (use categories instead)
4. **Case-insensitive venue search**: Use `--venue "emnlp"` to match "EMNLP", "emnlp", etc.
