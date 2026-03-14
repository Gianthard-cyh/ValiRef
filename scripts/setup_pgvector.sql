-- ParadeDB setup for ValiRef
-- ParadeDB includes: pgvector + pg_search (BM25) + pg_analytics

-- 1. Enable pg_search for BM25
CREATE EXTENSION IF NOT EXISTS pg_search;

-- 2. Create papers table
CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    authors TEXT[],
    abstract TEXT,
    categories TEXT[],
    year INTEGER,
    doi TEXT,
    journal_ref TEXT,
    venue VARCHAR(500),  -- DBLP conference/journal name
    source VARCHAR(20) DEFAULT 'arxiv',  -- 'arxiv' or 'dblp'
    embedding VECTOR(384),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 3. Create BM25 index for text search (includes title and abstract)
-- Note: This will be created after data is loaded for better performance
-- CREATE INDEX idx_papers_bm25 ON papers
-- USING bm25(id, title, abstract)
-- WITH (key_field='id');

-- 4. Standard indexes
CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year);
CREATE INDEX IF NOT EXISTS idx_papers_categories ON papers USING GIN(categories);
CREATE INDEX IF NOT EXISTS idx_papers_source ON papers(source);

-- 5. Vector index (create after data is loaded)
-- CREATE INDEX idx_papers_embedding ON papers USING ivfflat (embedding vector_cosine_ops);

-- 6. Helper function to rebuild BM25 index
CREATE OR REPLACE FUNCTION rebuild_bm25_index()
RETURNS void AS $$
BEGIN
    DROP INDEX IF EXISTS idx_papers_bm25;
    CREATE INDEX idx_papers_bm25 ON papers
    USING bm25(id, title, abstract)
    WITH (key_field='id');
END;
$$ LANGUAGE plpgsql;
