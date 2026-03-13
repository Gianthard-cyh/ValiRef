-- pgvector 数据库初始化脚本（小批量测试版）
-- 适用于 4GB 内存服务器

-- 1. 创建扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. 创建论文表
DROP TABLE IF EXISTS papers CASCADE;

CREATE TABLE papers (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    authors TEXT[],
    abstract TEXT,
    categories TEXT[],
    year INTEGER,
    doi TEXT,
    journal_ref TEXT,
    embedding VECTOR(384),  -- all-MiniLM-L6-v2 是384维
    created_at TIMESTAMP DEFAULT NOW()
);

-- 3. 创建B-tree索引（用于元数据过滤）
CREATE INDEX idx_papers_year ON papers(year);
CREATE INDEX idx_papers_categories ON papers USING GIN(categories);

-- 4. 创建全文搜索索引（可选，用于标题/摘要关键词搜索）
CREATE INDEX idx_papers_title_abstract ON papers
USING GIN(to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(abstract, '')));

-- 注意：向量索引 (IVFFlat) 在数据导入完成后再创建，以提高导入速度

-- 5. 验证表结构
\d papers
