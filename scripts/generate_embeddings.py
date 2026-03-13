#!/usr/bin/env python3
"""
arXiv Embedding 生成脚本（多进程加速版）
使用 sentence-transformers + multiprocessing 加速
"""

import asyncio
import asyncpg
import torch
import numpy as np
from pathlib import Path
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
import multiprocessing as mp
from multiprocessing import Pool, cpu_count
import sys

# 配置
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
BATCH_SIZE = 128  # 模型批处理大小
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "valiref",
    "password": "valiref_secret",
    "database": "arxiv_db"
}

# 全局模型（worker进程内）
_model = None


def init_worker():
    """worker进程初始化 - 加载模型"""
    global _model
    print(f"[Worker {mp.current_process().name}] 加载模型...")
    _model = SentenceTransformer(MODEL_NAME, device='cpu')
    _model.eval()


def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """批量生成embedding"""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME, device='cpu')

    # 清理文本
    texts = [t.strip().replace('\n', ' ')[:3000] for t in texts]  # 截断到3000字符

    with torch.no_grad():
        embeddings = _model.encode(
            texts,
            batch_size=len(texts),
            show_progress_bar=False,
            convert_to_numpy=True
        )

    # 转换为Python列表
    return embeddings.tolist()


def process_batch(batch_data: list[tuple]) -> list[tuple]:
    """处理一批论文，返回 (id, embedding) 列表"""
    ids = [item[0] for item in batch_data]
    texts = [item[1] for item in batch_data]

    embeddings = generate_embeddings_batch(texts)

    return list(zip(ids, embeddings))


async def generate_embeddings_parallel(limit: int = 10000, num_workers: int = None):
    """
    并行生成embedding

    Args:
        limit: 最多处理多少条记录
        num_workers: 并行进程数，默认CPU核心数
    """
    if num_workers is None:
        num_workers = min(cpu_count(), 4)  # 最多4个进程，避免内存爆炸

    print(f"🚀 启动 {num_workers} 个进程并行生成embedding...")
    print(f"   模型: {MODEL_NAME}")
    print(f"   批次: {BATCH_SIZE} 条/批")

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # 获取需要生成embedding的论文
        rows = await conn.fetch(
            """
            SELECT id, title, abstract
            FROM papers
            WHERE embedding IS NULL
            LIMIT $1
            """,
            limit
        )

        if not rows:
            print("✅ 所有论文已有embedding")
            return

        print(f"📄 待处理论文: {len(rows):,} 条")

        # 准备数据
        batch_data = []
        for row in rows:
            # 组合标题和摘要作为输入
            text = f"{row['title']}\n\n{row['abstract']}" if row['abstract'] else row['title']
            batch_data.append((row['id'], text))

        # 分批次
        batches = [
            batch_data[i:i+BATCH_SIZE]
            for i in range(0, len(batch_data), BATCH_SIZE)
        ]

        print(f"   分成 {len(batches)} 个批次")

        # 并行处理
        results = []
        with Pool(processes=num_workers, initializer=init_worker) as pool:
            with tqdm(total=len(batches), desc="生成embedding") as pbar:
                for batch_result in pool.imap(process_batch, batches):
                    results.extend(batch_result)
                    pbar.update(1)

        # 批量更新数据库
        print("💾 写入数据库...")
        await conn.executemany(
            "UPDATE papers SET embedding = $2 WHERE id = $1",
            results
        )

        print(f"✅ 完成！共生成 {len(results):,} 个embedding")

    finally:
        await conn.close()


async def generate_embeddings_sequential(limit: int = 1000):
    """
    顺序生成embedding（内存友好，适合低配置机器）
    """
    print("🚀 顺序生成embedding（内存友好模式）...")

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # 加载模型
        print(f"📥 加载模型: {MODEL_NAME}")
        model = SentenceTransformer(MODEL_NAME, device='cpu')
        model.eval()

        # 获取需要生成embedding的论文
        rows = await conn.fetch(
            """
            SELECT id, title, abstract
            FROM papers
            WHERE embedding IS NULL
            LIMIT $1
            """,
            limit
        )

        if not rows:
            print("✅ 所有论文已有embedding")
            return

        print(f"📄 待处理论文: {len(rows):,} 条")

        updated = 0
        with tqdm(total=len(rows), desc="生成embedding") as pbar:
            for i in range(0, len(rows), BATCH_SIZE):
                batch = rows[i:i+BATCH_SIZE]

                # 准备文本
                texts = []
                for row in batch:
                    text = f"{row['title']}\n\n{row['abstract']}" if row['abstract'] else row['title']
                    texts.append(text.strip().replace('\n', ' ')[:3000])

                # 生成embedding
                with torch.no_grad():
                    embeddings = model.encode(
                        texts,
                        batch_size=len(texts),
                        show_progress_bar=False,
                        convert_to_numpy=True
                    )

                # 更新数据库
                values = [
                    (row['id'], embeddings[j].tolist())
                    for j, row in enumerate(batch)
                ]
                await conn.executemany(
                    "UPDATE papers SET embedding = $2 WHERE id = $1",
                    values
                )

                updated += len(batch)
                pbar.update(len(batch))

        print(f"✅ 完成！共生成 {updated:,} 个embedding")

    finally:
        await conn.close()


def main():
    print("=" * 50)
    print("arXiv Embedding 生成工具")
    print("=" * 50)

    import argparse
    parser = argparse.ArgumentParser(description="生成论文embedding")
    parser.add_argument(
        "-l", "--limit",
        type=int,
        default=1000,
        help="最多处理多少条记录 (默认: 1000)"
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=None,
        help="并行进程数 (默认: CPU核心数)"
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="使用顺序模式（内存友好）"
    )
    args = parser.parse_args()

    if args.sequential:
        asyncio.run(generate_embeddings_sequential(args.limit))
    else:
        asyncio.run(generate_embeddings_parallel(args.limit, args.workers))


if __name__ == "__main__":
    # Windows/macOS需要这行
    mp.set_start_method('spawn', force=True)
    main()
