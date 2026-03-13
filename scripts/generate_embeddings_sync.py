#!/usr/bin/env python3
"""
arXiv Embedding 生成脚本（同步版，更稳定）
"""

import torch
import numpy as np
import psycopg2
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
BATCH_SIZE = 64  # 模型批处理大小

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "valiref",
    "password": "valiref_secret",
    "database": "arxiv_db"
}


def vector_to_str(vec: list[float]) -> str:
    """将向量转换为PostgreSQL vector格式"""
    return "[" + ",".join(str(v) for v in vec) + "]"


def generate_embeddings(limit: int = 1000):
    """生成embedding并写入数据库"""
    print("🚀 开始生成embedding...")
    print(f"   模型: {MODEL_NAME}")
    print(f"   批次: {BATCH_SIZE}")

    # 加载模型
    print("📥 加载模型...")
    model = SentenceTransformer(MODEL_NAME, device='cpu')
    model.eval()

    # 连接数据库
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        # 获取需要生成embedding的论文
        cursor.execute(
            "SELECT id, title, abstract FROM papers WHERE embedding IS NULL LIMIT %s",
            (limit,)
        )
        rows = cursor.fetchall()

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

                # 更新数据库 - 逐条更新
                for j, row in enumerate(batch):
                    paper_id = row[0]
                    embedding_str = vector_to_str(embeddings[j].tolist())
                    cursor.execute(
                        "UPDATE papers SET embedding = %s::vector WHERE id = %s",
                        (embedding_str, paper_id)
                    )

                conn.commit()
                updated += len(batch)
                pbar.update(len(batch))

        print(f"✅ 完成！共生成 {updated:,} 个embedding")

    finally:
        cursor.close()
        conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="生成论文embedding")
    parser.add_argument("-l", "--limit", type=int, default=1000, help="最多处理多少条")
    args = parser.parse_args()

    print("=" * 50)
    print("arXiv Embedding 生成工具（同步版）")
    print("=" * 50)

    generate_embeddings(args.limit)


if __name__ == "__main__":
    main()
