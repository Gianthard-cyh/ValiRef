#!/usr/bin/env python3
"""
arXiv 元数据导入脚本（同步版本，更稳定）
支持：进度条、断点续传、全量导入
"""

import json
import psycopg2
from pathlib import Path
from tqdm import tqdm
import time
import argparse
import sys

# 配置
BATCH_SIZE = 1000  # 每批导入数量
MAX_PAPERS = None  # None = 导入全部（约300万条）
JSONL_PATH = Path("/home/cyh/下载/arxiv-metadata-oai-snapshot.json")

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "valiref",
    "password": "valiref_secret",
    "database": "arxiv_db"
}


def count_lines(file_path: Path) -> int:
    """统计文件行数（用于进度条）"""
    print("📊 统计文件行数...")
    count = 0
    with open(file_path, 'rb') as f:
        for _ in tqdm(f, desc="统计行数", unit=" lines"):
            count += 1
    return count


def parse_paper_line(line: str) -> dict | None:
    """解析单行JSONL数据"""
    try:
        data = json.loads(line)

        # 提取年份
        year = None
        if data.get("versions"):
            created = data["versions"][0].get("created", "")
            try:
                year = int(created.split()[-3]) if len(created.split()) > 3 else None
            except (ValueError, IndexError):
                pass

        if year is None and data.get("update_date"):
            try:
                year = int(data["update_date"].split("-")[0])
            except (ValueError, IndexError):
                pass

        categories = data.get("categories", "").split()

        authors = []
        if data.get("authors_parsed"):
            for author in data["authors_parsed"]:
                if isinstance(author, list) and len(author) >= 2:
                    name = f"{author[1]} {author[0]}"
                    authors.append(name.strip())

        return {
            "id": data.get("id"),
            "title": data.get("title", "").strip()[:500],
            "authors": authors,
            "abstract": data.get("abstract", "").strip()[:2000],
            "categories": categories,
            "year": year,
            "doi": data.get("doi"),
            "journal_ref": data.get("journal-ref")
        }
    except json.JSONDecodeError:
        return None


def import_metadata(data_path: Path = None, max_papers: int = None):
    """导入元数据"""
    jsonl_path = data_path or JSONL_PATH
    target_count = max_papers if max_papers else MAX_PAPERS

    print("🚀 开始导入元数据...")

    # 确定导入数量
    total_lines = count_lines(jsonl_path)
    if target_count is None:
        target_count = total_lines
    actual_target = min(target_count, total_lines)
    print(f"   目标: {actual_target:,} / {total_lines:,} 条记录")
    print(f"   批次: {BATCH_SIZE} 条/批")
    print(f"   预计时间: {actual_target / 10000 * 6 / 60:.1f} 分钟\n")

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        batch = []
        imported = 0
        errors = 0
        start_time = time.time()

        with open(jsonl_path, 'r', encoding='utf-8') as f:
            with tqdm(total=actual_target, desc="📥 导入进度",
                     unit=" papers",
                     bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:

                for line in f:
                    if imported >= actual_target:
                        break

                    paper = parse_paper_line(line)
                    if paper and paper["id"]:
                        batch.append(paper)
                    else:
                        errors += 1

                    if len(batch) >= BATCH_SIZE:
                        # 批量插入
                        args_str = ','.join(cursor.mogrify(
                            "(%s, %s, %s, %s, %s, %s, %s, %s)",
                            (p["id"], p["title"], p["authors"], p["abstract"],
                             p["categories"], p["year"], p["doi"], p["journal_ref"])
                        ).decode('utf-8') for p in batch)

                        cursor.execute(f"""
                            INSERT INTO papers (id, title, authors, abstract, categories, year, doi, journal_ref)
                            VALUES {args_str}
                            ON CONFLICT (id) DO NOTHING
                        """)
                        conn.commit()

                        imported += len(batch)
                        pbar.update(len(batch))
                        batch = []

                # 导入最后一批
                if batch:
                    args_str = ','.join(cursor.mogrify(
                        "(%s, %s, %s, %s, %s, %s, %s, %s)",
                        (p["id"], p["title"], p["authors"], p["abstract"],
                         p["categories"], p["year"], p["doi"], p["journal_ref"])
                    ).decode('utf-8') for p in batch)

                    cursor.execute(f"""
                        INSERT INTO papers (id, title, authors, abstract, categories, year, doi, journal_ref)
                        VALUES {args_str}
                        ON CONFLICT (id) DO NOTHING
                    """)
                    conn.commit()

                    imported += len(batch)
                    pbar.update(len(batch))

        elapsed = time.time() - start_time
        print(f"\n✅ 导入完成！")
        print(f"   成功导入: {imported:,} 条")
        print(f"   解析失败: {errors:,} 条")
        print(f"   总耗时: {elapsed / 60:.1f} 分钟")
        print(f"   平均速度: {imported / elapsed:.0f} 条/秒")

        cursor.execute("SELECT COUNT(*) FROM papers")
        count = cursor.fetchone()[0]
        print(f"   数据库当前总计: {count:,} 条")

    finally:
        cursor.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="导入arXiv元数据")
    parser.add_argument("--data", type=Path, default=JSONL_PATH, help="JSONL数据文件路径")
    parser.add_argument("--limit", type=int, default=None, help="最多导入多少条")
    args = parser.parse_args()

    print("=" * 60)
    print("arXiv 元数据导入工具（全量版）")
    print("=" * 60)

    data_path = args.data

    if not data_path.exists():
        print(f"❌ 错误: 找不到文件 {data_path}")
        print(f"   请指定正确的路径: --data /path/to/arxiv-metadata.json")
        return

    file_size = data_path.stat().st_size / (1024**3)
    print(f"📁 数据文件: {data_path.name} ({file_size:.2f} GB)\n")

    import_metadata(data_path, args.limit)


if __name__ == "__main__":
    main()
