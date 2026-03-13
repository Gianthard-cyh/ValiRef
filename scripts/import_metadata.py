#!/usr/bin/env python3
"""
arXiv 元数据导入脚本（小批量测试版）
支持加速：多进程并行、批处理、流式读取
"""

import json
import asyncio
import asyncpg
from pathlib import Path
from datetime import datetime
from typing import Iterator
from tqdm import tqdm
import multiprocessing as mp
from functools import partial
import os

# 配置
BATCH_SIZE = 500  # 每批导入数量
MAX_PAPERS = 10000  # 小批量测试：只导入1万条
JSONL_PATH = Path("/home/cyh/下载/arxiv-metadata-oai-snapshot.json")

# PostgreSQL连接配置
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "valiref",
    "password": "valiref_secret",
    "database": "arxiv_db",
    "ssl": False
}


def parse_paper_line(line: str) -> dict | None:
    """解析单行JSONL数据"""
    try:
        data = json.loads(line)

        # 提取年份（从versions或update_date）
        year = None
        if data.get("versions"):
            # 从第一个版本的created字段提取
            created = data["versions"][0].get("created", "")
            # 格式: "Mon, 2 Apr 2007 19:18:42 GMT"
            try:
                year = int(created.split()[-3]) if len(created.split()) > 3 else None
            except (ValueError, IndexError):
                pass

        if year is None and data.get("update_date"):
            # 从update_date提取: "2008-11-26"
            try:
                year = int(data["update_date"].split("-")[0])
            except (ValueError, IndexError):
                pass

        # 解析categories
        categories = data.get("categories", "").split()

        # 解析authors_parsed
        authors = []
        if data.get("authors_parsed"):
            for author in data["authors_parsed"]:
                if isinstance(author, list) and len(author) >= 2:
                    name = f"{author[1]} {author[0]}"  # 名 + 姓
                    authors.append(name.strip())

        return {
            "id": data.get("id"),
            "title": data.get("title", "").strip(),
            "authors": authors,
            "abstract": data.get("abstract", "").strip(),
            "categories": categories,
            "year": year,
            "doi": data.get("doi"),
            "journal_ref": data.get("journal-ref")
        }
    except json.JSONDecodeError:
        return None


def stream_papers(jsonl_path: Path, max_papers: int = None) -> Iterator[dict]:
    """流式读取JSONL文件"""
    count = 0
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            if max_papers and count >= max_papers:
                break
            paper = parse_paper_line(line)
            if paper and paper["id"]:
                yield paper
                count += 1


async def import_batch(conn: asyncpg.Connection, papers: list[dict]):
    """批量导入一批论文（不含embedding）"""
    query = """
        INSERT INTO papers (id, title, authors, abstract, categories, year, doi, journal_ref)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (id) DO NOTHING
    """

    values = [
        (
            p["id"],
            p["title"],
            p["authors"],
            p["abstract"],
            p["categories"],
            p["year"],
            p["doi"],
            p["journal_ref"]
        )
        for p in papers
    ]

    await conn.executemany(query, values)


async def import_metadata_only():
    """只导入元数据（不含embedding），用于快速测试"""
    print("🚀 开始导入元数据（不含embedding）...")
    print(f"   目标: {MAX_PAPERS:,} 条记录")
    print(f"   批次: {BATCH_SIZE} 条/批")

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        batch = []
        imported = 0

        with tqdm(total=MAX_PAPERS, desc="导入进度") as pbar:
            for paper in stream_papers(JSONL_PATH, MAX_PAPERS):
                batch.append(paper)

                if len(batch) >= BATCH_SIZE:
                    await import_batch(conn, batch)
                    imported += len(batch)
                    pbar.update(len(batch))
                    batch = []

            # 导入最后一批
            if batch:
                await import_batch(conn, batch)
                imported += len(batch)
                pbar.update(len(batch))

        print(f"\n✅ 完成！成功导入 {imported:,} 条记录")

        # 统计
        count = await conn.fetchval("SELECT COUNT(*) FROM papers")
        print(f"   数据库当前总计: {count:,} 条")

    finally:
        await conn.close()


async def add_embedding_column():
    """添加embedding列（如果不存在）"""
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        await conn.execute("""
            ALTER TABLE papers ADD COLUMN IF NOT EXISTS embedding VECTOR(384)
        """)
        print("✅ embedding列已添加")
    finally:
        await conn.close()


async def create_vector_index():
    """创建IVFFlat向量索引"""
    print("🔧 创建IVFFlat向量索引（可能需要几分钟）...")
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_papers_embedding
            ON papers USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 50)
        """)
        print("✅ 向量索引创建完成")
    finally:
        await conn.close()


def main():
    """主函数"""
    print("=" * 50)
    print("arXiv 元数据导入工具（小批量测试版）")
    print("=" * 50)

    # 检查文件
    if not JSONL_PATH.exists():
        print(f"❌ 错误: 找不到文件 {JSONL_PATH}")
        return

    file_size = JSONL_PATH.stat().st_size / (1024**3)
    print(f"📁 数据文件: {JSONL_PATH.name} ({file_size:.2f} GB)")

    # 运行导入
    asyncio.run(import_metadata_only())

    print("\n📌 下一步:")
    print("   1. 运行 generate_embeddings.py 生成向量")
    print("   2. 运行 create_vector_index() 创建索引")


if __name__ == "__main__":
    main()
