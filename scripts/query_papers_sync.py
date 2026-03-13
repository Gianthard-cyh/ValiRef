#!/usr/bin/env python3
"""
arXiv 论文查询脚本（同步版）
"""

import psycopg2
from sentence_transformers import SentenceTransformer
import torch

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "valiref",
    "password": "valiref_secret",
    "database": "arxiv_db"
}

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def vector_to_str(vec: list[float]) -> str:
    """将向量转换为PostgreSQL vector格式"""
    return "[" + ",".join(str(v) for v in vec) + "]"


def search_similar(query: str, top_k: int = 10):
    """向量相似度搜索"""
    print(f"📥 加载模型...")
    model = SentenceTransformer(MODEL_NAME, device='cpu')

    print(f"🔍 查询: {query}")
    query_vec = model.encode(query, convert_to_numpy=True).tolist()
    query_str = vector_to_str(query_vec)

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        print("📊 执行查询...")
        cursor.execute("""
            SELECT
                id,
                title,
                authors,
                categories,
                year,
                1 - (embedding <=> %s::vector) as similarity
            FROM papers
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (query_str, query_str, top_k))

        rows = cursor.fetchall()

        print(f"\n{'='*60}")
        print(f"找到 {len(rows)} 篇相关论文:")
        print(f"{'='*60}\n")

        for i, row in enumerate(rows, 1):
            similarity = float(row[5]) * 100
            authors = row[2] if row[2] else []
            categories = row[3] if row[3] else []
            print(f"{i}. [{row[0]}] 相似度: {similarity:.1f}%")
            print(f"   标题: {row[1][:80]}...")
            print(f"   作者: {', '.join(authors[:3])}")
            print(f"   类别: {', '.join(categories[:3])}")
            print(f"   年份: {row[4]}")
            print()

    finally:
        cursor.close()
        conn.close()


def fulltext_search(query: str, top_k: int = 10):
    """全文搜索"""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        print(f"🔍 全文搜索: {query}")
        cursor.execute("""
            SELECT
                id,
                title,
                authors,
                categories,
                year,
                ts_rank(
                    to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(abstract, '')),
                    plainto_tsquery('english', %s)
                ) as rank
            FROM papers
            WHERE to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(abstract, ''))
                  @@ plainto_tsquery('english', %s)
            ORDER BY rank DESC
            LIMIT %s
        """, (query, query, top_k))

        rows = cursor.fetchall()

        print(f"\n{'='*60}")
        print(f"找到 {len(rows)} 篇相关论文:")
        print(f"{'='*60}\n")

        for i, row in enumerate(rows, 1):
            authors = row[2] if row[2] else []
            print(f"{i}. [{row[0]}] 相关度: {row[5]:.3f}")
            print(f"   标题: {row[1][:80]}...")
            print(f"   作者: {', '.join(authors[:3])}")
            print(f"   年份: {row[4]}")
            print()

    finally:
        cursor.close()
        conn.close()


def hybrid_search(query: str, top_k: int = 10):
    """混合搜索：向量 + 全文"""
    print(f"📥 加载模型...")
    model = SentenceTransformer(MODEL_NAME, device='cpu')

    print(f"🔍 混合搜索: {query}")
    query_vec = model.encode(query, convert_to_numpy=True).tolist()
    query_str = vector_to_str(query_vec)

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            WITH vector_results AS (
                SELECT
                    id,
                    1 - (embedding <=> %s::vector) as vector_score
                FROM papers
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s * 2
            ),
            text_results AS (
                SELECT
                    id,
                    ts_rank(
                        to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(abstract, '')),
                        plainto_tsquery('english', %s)
                    ) as text_score
                FROM papers
                WHERE to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(abstract, ''))
                      @@ plainto_tsquery('english', %s)
                ORDER BY text_score DESC
                LIMIT %s * 2
            )
            SELECT
                p.id,
                p.title,
                p.authors,
                p.categories,
                p.year,
                v.vector_score,
                COALESCE(t.text_score, 0) as text_score,
                (v.vector_score * 0.7 + COALESCE(t.text_score, 0) * 0.3) as hybrid_score
            FROM vector_results v
            JOIN papers p ON v.id = p.id
            LEFT JOIN text_results t ON v.id = t.id
            ORDER BY hybrid_score DESC
            LIMIT %s
        """, (query_str, query_str, top_k, query, query, top_k, top_k))

        rows = cursor.fetchall()

        print(f"\n{'='*60}")
        print(f"找到 {len(rows)} 篇相关论文 (向量+全文):")
        print(f"{'='*60}\n")

        for i, row in enumerate(rows, 1):
            authors = row[2] if row[2] else []
            print(f"{i}. [{row[0]}] 混合得分: {row[7]:.3f}")
            print(f"   向量: {row[5]:.3f}, 文本: {row[6]:.3f}")
            print(f"   标题: {row[1][:80]}...")
            print(f"   作者: {', '.join(authors[:3])}")
            print(f"   年份: {row[4]}")
            print()

    finally:
        cursor.close()
        conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="查询arXiv论文")
    parser.add_argument("query", help="查询文本")
    parser.add_argument("-k", "--top-k", type=int, default=10, help="返回结果数")
    parser.add_argument("--fulltext", action="store_true", help="全文搜索")
    parser.add_argument("--hybrid", action="store_true", help="混合搜索")
    args = parser.parse_args()

    print("=" * 60)
    print("arXiv 论文查询工具")
    print("=" * 60)

    if args.hybrid:
        hybrid_search(args.query, args.top_k)
    elif args.fulltext:
        fulltext_search(args.query, args.top_k)
    else:
        search_similar(args.query, args.top_k)


if __name__ == "__main__":
    main()
