#!/usr/bin/env python3
"""
arXiv Embedding 生成脚本（GPU加速版）
自动检测CUDA，优先使用GPU，回退到CPU
"""

import torch
import numpy as np
import psycopg2
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
import time
import os

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
BATCH_SIZE = 256  # GPU可以处理更大批次

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "valiref",
    "password": "valiref_secret",
    "database": "arxiv_db"
}


def get_device():
    """获取最佳可用设备"""
    if torch.cuda.is_available():
        device = "cuda"
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"🎮 检测到GPU: {gpu_name}")
        print(f"   显存: {gpu_memory:.1f} GB")
        return device
    else:
        print("⚠️  未检测到GPU，使用CPU")
        return "cpu"


def vector_to_str(vec: list[float]) -> str:
    """将向量转换为PostgreSQL vector格式"""
    return "[" + ",".join(str(v) for v in vec) + "]"


def generate_embeddings(limit: int = None, batch_size: int = None):
    """生成embedding并写入数据库"""
    if batch_size is None:
        batch_size = BATCH_SIZE

    # 获取设备
    device = get_device()

    print(f"🚀 开始生成embedding...")
    print(f"   模型: {MODEL_NAME}")
    print(f"   设备: {device}")
    print(f"   批次: {batch_size}")

    # 加载模型
    print("\n📥 加载模型...")
    model = SentenceTransformer(MODEL_NAME, device=device)
    model.eval()

    # 连接数据库
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        # 统计待处理数量
        if limit:
            cursor.execute(
                "SELECT COUNT(*) FROM papers WHERE embedding IS NULL LIMIT %s",
                (limit,)
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM papers WHERE embedding IS NULL")

        total_pending = cursor.fetchone()[0]
        if limit and limit < total_pending:
            total_pending = limit

        if total_pending == 0:
            print("✅ 所有论文已有embedding")
            return

        print(f"📄 待处理论文: {total_pending:,} 条")
        print(f"   预计时间: {total_pending / 1000 * (0.5 if device == 'cuda' else 60) / 60:.1f} 分钟\n")

        processed = 0
        start_time = time.time()

        with tqdm(total=total_pending, desc="🧠 生成embedding",
                 unit=" papers",
                 bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:

            while processed < total_pending:
                # 获取一批待处理数据
                remaining = min(batch_size, total_pending - processed)
                cursor.execute(
                    """
                    SELECT id, title, abstract FROM papers
                    WHERE embedding IS NULL
                    LIMIT %s
                    """,
                    (remaining,)
                )
                rows = cursor.fetchall()

                if not rows:
                    break

                # 准备文本
                texts = []
                for row in rows:
                    title = row[1] if row[1] else ""
                    abstract = row[2] if row[2] else ""
                    text = f"{title}\n\n{abstract}" if abstract else title
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
                for j, row in enumerate(rows):
                    paper_id = row[0]
                    embedding_str = vector_to_str(embeddings[j].tolist())
                    cursor.execute(
                        "UPDATE papers SET embedding = %s::vector WHERE id = %s",
                        (embedding_str, paper_id)
                    )

                conn.commit()
                processed += len(rows)
                pbar.update(len(rows))

        elapsed = time.time() - start_time
        speed = processed / elapsed

        print(f"\n✅ 完成！")
        print(f"   生成数量: {processed:,} 个embedding")
        print(f"   总耗时: {elapsed / 60:.1f} 分钟")
        print(f"   平均速度: {speed:.1f} 条/秒")

        # 统计
        cursor.execute("SELECT COUNT(*), COUNT(embedding) FROM papers")
        total, with_embed = cursor.fetchone()
        print(f"   数据库总计: {total:,} 条，有embedding: {with_embed:,} 条 ({100*with_embed/total:.1f}%)")

    finally:
        cursor.close()
        conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="生成论文embedding（GPU加速）")
    parser.add_argument("-l", "--limit", type=int, default=None,
                       help="最多处理多少条（默认全部）")
    parser.add_argument("-b", "--batch-size", type=int, default=BATCH_SIZE,
                       help=f"批处理大小（默认{BATCH_SIZE}）")
    args = parser.parse_args()

    print("=" * 60)
    print("arXiv Embedding 生成工具（GPU加速版）")
    print("=" * 60)

    generate_embeddings(args.limit, args.batch_size)


if __name__ == "__main__":
    main()
