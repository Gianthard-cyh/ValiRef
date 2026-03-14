#!/usr/bin/env python3
"""
Minimal arXiv embedding generator with sliding window chunking.
Uses parameterized queries for safe database writes.
"""

import os
import time
import numpy as np
import psycopg2
from psycopg2.extras import execute_values
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

# Config
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
BATCH_SIZE = 64
MAX_TOKENS = 512
OVERLAP = 128
DIMENSION = 384  # all-MiniLM-L6-v2 output dimension

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "user": os.getenv("DB_USER", "valiref"),
    "password": os.getenv("DB_PASSWORD", "valiref_secret"),
    "database": os.getenv("DB_NAME", "arxiv_db"),
}


def sliding_window_encode(
    text: str, model, max_tokens: int = 512, overlap: int = 128
) -> tuple[np.ndarray, int]:
    """
    Encode long text using sliding window + mean pooling.

    Args:
        text: Input text
        model: SentenceTransformer model
        max_tokens: Max tokens per chunk
        overlap: Overlap between consecutive chunks

    Returns:
        Tuple of (mean-pooled embedding vector, token count)
    """
    tokenizer = model.tokenizer
    tokens = tokenizer.encode(text, add_special_tokens=False)
    token_count = len(tokens)

    # Short text: direct encode
    if token_count <= max_tokens:
        embedding = model.encode(text, convert_to_numpy=True, show_progress_bar=False)
        return embedding, token_count

    # Long text: sliding window
    embeddings = []
    step = max_tokens - overlap

    for i in range(0, len(tokens), step):
        chunk_tokens = tokens[i : i + max_tokens]
        chunk_text = tokenizer.decode(chunk_tokens, skip_special_tokens=True)
        emb = model.encode(chunk_text, convert_to_numpy=True, show_progress_bar=False)
        embeddings.append(emb)

        if i + max_tokens >= len(tokens):
            break

    return np.mean(embeddings, axis=0), token_count


def process_batch(rows, model) -> tuple[list, int]:
    """Process a batch of papers and return (id, embedding) tuples and multi-chunk count."""
    results = []
    multi_chunk = 0

    for row in rows:
        paper_id, title, abstract = row
        text = f"{title}\n\n{abstract}" if abstract else title

        # Sliding window encoding - returns embedding and token count
        embedding, token_count = sliding_window_encode(text, model, MAX_TOKENS, OVERLAP)

        # Track multi-chunk papers
        if token_count > MAX_TOKENS:
            multi_chunk += 1

        # Convert to list for pgvector
        results.append((paper_id, embedding.tolist()))

    return results, multi_chunk


def generate_embeddings(limit: int = None):
    """Generate embeddings for papers without them."""
    print("🚀 Embedding Generator")
    print(f"   Model: {MODEL_NAME}")
    print(f"   Strategy: sliding window (max_tokens={MAX_TOKENS}, overlap={OVERLAP})")

    # Load model
    print("\n📥 Loading model...")
    model = SentenceTransformer(MODEL_NAME, device="cpu")
    model.eval()

    # Connect to DB
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        # Count pending
        cursor.execute("SELECT COUNT(*) FROM papers WHERE embedding IS NULL")
        total_pending = cursor.fetchone()[0]

        if limit:
            total_pending = min(total_pending, limit)

        if total_pending == 0:
            print("✅ All papers already have embeddings")
            return

        print(f"📄 Pending papers: {total_pending:,}")

        processed = 0
        multi_chunk = 0
        start_time = time.time()

        with tqdm(total=total_pending, desc="🧠 Encoding", unit="papers") as pbar:
            while processed < total_pending:
                # Fetch batch
                remaining = min(BATCH_SIZE, total_pending - processed)
                cursor.execute(
                    "SELECT id, title, abstract FROM papers WHERE embedding IS NULL LIMIT %s",
                    (remaining,),
                )
                rows = cursor.fetchall()

                if not rows:
                    break

                # Process batch
                batch_results, batch_multi_chunk = process_batch(rows, model)
                multi_chunk += batch_multi_chunk

                # Bulk update using execute_values with parameterized query
                # pgvector accepts array literals like [0.1, 0.2, ...]
                execute_values(
                    cursor,
                    "UPDATE papers AS p SET embedding = v.embedding::vector FROM (VALUES %s) AS v(id, embedding) WHERE p.id = v.id",
                    batch_results,
                    template="(%s, %s::vector)",
                    page_size=len(batch_results),
                )
                conn.commit()

                processed += len(rows)
                pbar.update(len(rows))

        elapsed = time.time() - start_time
        print("\n✅ Done!")
        print(f"   Generated: {processed:,} embeddings")
        print(f"   Multi-chunk: {multi_chunk:,} papers")
        print(f"   Time: {elapsed / 60:.1f} min")
        print(f"   Speed: {processed / elapsed:.1f} papers/sec")

    finally:
        cursor.close()
        conn.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate paper embeddings")
    parser.add_argument(
        "-l", "--limit", type=int, default=None, help="Max papers to process"
    )
    args = parser.parse_args()

    generate_embeddings(args.limit)


if __name__ == "__main__":
    main()
