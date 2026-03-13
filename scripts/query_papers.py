#!/usr/bin/env python3
"""
arXiv 论文相似度查询示例
"""

import asyncio
import asyncpg
from sentence_transformers import SentenceTransformer

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "valiref",
    "password": "valiref_secret",
    "database": "arxiv_db"
}

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


async def search_similar_papers(
    query: str,
    top_k: int = 10,
    category_filter: str = None,
    year_from: int = None
):
    """
    搜索相似论文

    Args:
        query: 查询文本
        top_k: 返回结果数
        category_filter: 类别过滤，如 "cs.AI"
        year_from: 起始年份
    """
    # 加载模型
    print(f"📥 加载模型...")
    model = SentenceTransformer(MODEL_NAME, device='cpu')

    # 生成查询向量
    print(f"🔍 查询: {query}")
    query_embedding = model.encode(query, convert_to_numpy=True).tolist()

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # 构建查询
        conditions = []
        params = [query_embedding, top_k]

        if category_filter:
            conditions.append(f"categories @> ARRAY['{category_filter}']")

        if year_from:
            conditions.append(f"year >= {year_from}")

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        sql = f"""
            SELECT
                id,
                title,
                authors,
                categories,
                year,
                1 - (embedding <=> $1) as similarity
            FROM papers
            {where_clause}
            ORDER BY embedding <=> $1
            LIMIT $2
        """

        print(f"📊 执行查询...")
        rows = await conn.fetch(sql, *params)

        print(f"\n{'='*60}")
        print(f"找到 {len(rows)} 篇相关论文:")
        print(f"{'='*60}\n")

        for i, row in enumerate(rows, 1):
            similarity = row['similarity'] * 100
            print(f"{i}. [{row['id']}] 相似度: {similarity:.1f}%")
            print(f"   标题: {row['title'][:80]}...")
            print(f"   作者: {', '.join(row['authors'][:3]) if row['authors'] else 'N/A'}")
            print(f"   类别: {', '.join(row['categories'][:3]) if row['categories'] else 'N/A'}")
            print(f"   年份: {row['year']}")
            print()

    finally:
        await conn.close()


async def fulltext_search(query: str, top_k: int = 10):
    """使用PostgreSQL全文搜索"""
    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        sql = """
            SELECT
                id,
                title,
                authors,
                categories,
                year,
                ts_rank(
                    to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(abstract, '')),
                    plainto_tsquery('english', $1)
                ) as rank
            FROM papers
            WHERE to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(abstract, ''))
                  @@ plainto_tsquery('english', $1)
            ORDER BY rank DESC
            LIMIT $2
        """

        print(f"🔍 全文搜索: {query}")
        rows = await conn.fetch(sql, query, top_k)

        print(f"\n{'='*60}")
        print(f"找到 {len(rows)} 篇相关论文:")
        print(f"{'='*60}\n")

        for i, row in enumerate(rows, 1):
            print(f"{i}. [{row['id']}] 相关度: {row['rank']:.3f}")
            print(f"   标题: {row['title'][:80]}...")
            print(f"   作者: {', '.join(row['authors'][:3]) if row['authors'] else 'N/A'}")
            print(f"   年份: {row['year']}")
            print()

    finally:
        await conn.close()


async def hybrid_search(query: str, top_k: int = 10):
    """混合搜索：向量相似度 + 全文搜索 + 重排序"""
    # 加载模型
    model = SentenceTransformer(MODEL_NAME, device='cpu')
    query_embedding = model.encode(query, convert_to_numpy=True).tolist()

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # 同时获取向量搜索结果和全文搜索结果
        sql = """
            WITH vector_results AS (
                SELECT
                    id,
                    title,
                    authors,
                    abstract,
                    categories,
                    year,
                    1 - (embedding <=> $1) as vector_score
                FROM papers
                ORDER BY embedding <=> $1
                LIMIT $2 * 2
            ),
            text_results AS (
                SELECT
                    id,
                    ts_rank(
                        to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(abstract, '')),
                        plainto_tsquery('english', $3)
                    ) as text_score
                FROM papers
                WHERE to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(abstract, ''))
                      @@ plainto_tsquery('english', $3)
                ORDER BY text_score DESC
                LIMIT $2 * 2
            )
            SELECT
                v.id,
                v.title,
                v.authors,
                v.categories,
                v.year,
                v.vector_score,
                COALESCE(t.text_score, 0) as text_score,
                (v.vector_score * 0.7 + COALESCE(t.text_score, 0) * 0.3) as hybrid_score
            FROM vector_results v
            LEFT JOIN text_results t ON v.id = t.id
            ORDER BY hybrid_score DESC
            LIMIT $2
        """

        print(f"🔍 混合搜索: {query}")
        rows = await conn.fetch(sql, query_embedding, top_k, query)

        print(f"\n{'='*60}")
        print(f"找到 {len(rows)} 篇相关论文 (向量+全文):")
        print(f"{'='*60}\n")

        for i, row in enumerate(rows, 1):
            print(f"{i}. [{row['id']}] 混合得分: {row['hybrid_score']:.3f}")
            print(f"   向量得分: {row['vector_score']:.3f}, 文本得分: {row['text_score']:.3f}")
            print(f"   标题: {row['title'][:80]}...")
            print(f"   作者: {', '.join(row['authors'][:3]) if row['authors'] else 'N/A'}")
            print(f"   年份: {row['year']}")
            print()

    finally:
        await conn.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="查询arXiv论文")
    parser.add_argument("query", help="查询文本")
    parser.add_argument("-k", "--top-k", type=int, default=10, help="返回结果数")
    parser.add_argument("-c", "--category", help="类别过滤，如 cs.AI")
    parser.add_argument("-y", "--year-from", type=int, help="起始年份")
    parser.add_argument("--fulltext", action="store_true", help="使用全文搜索")
    parser.add_argument("--hybrid", action="store_true", help="使用混合搜索")
    args = parser.parse_args()

    print("=" * 60)
    print("arXiv 论文查询工具")
    print("=" * 60)

    if args.hybrid:
        asyncio.run(hybrid_search(args.query, args.top_k))
    elif args.fulltext:
        asyncio.run(fulltext_search(args.query, args.top_k))
    else:
        asyncio.run(search_similar_papers(
            args.query,
            args.top_k,
            args.category,
            args.year_from
        ))


if __name__ == "__main__":
    main()
