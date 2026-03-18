"""Test local search with reranking and display BM25 vs CrossEncoder scores."""
import asyncio
import sys
from dataclasses import dataclass

sys.path.insert(0, "/home/cyh/ValiRef")

from src.core.search.sources.local_db import LocalDBSearch
from src.core.search.base import SearchResult


@dataclass
class ScoredResult:
    """Wrapper for result with both BM25 and rerank scores."""
    bm25_rank: int
    bm25_score: float
    rerank_score: float
    title: str
    authors: str
    abstract: str
    source: str


class TestableLocalDBSearch(LocalDBSearch):
    """Extended LocalDBSearch that exposes internal scores."""

    async def search_with_scores(self, query: str, limit: int = 5, candidate_multiplier: int = 4):
        """
        Search and return both BM25 and reranked results with scores.

        Returns:
            Tuple of (bm25_results_with_scores, reranked_results_with_scores)
        """
        import asyncpg
        import json

        pool = await self._get_pool()
        candidate_limit = limit * candidate_multiplier

        async with pool.acquire() as conn:
            escaped_query = f'"{query.replace("\"", "\\\"")}"'

            sql = """
                SELECT
                    id,
                    title,
                    authors,
                    year,
                    venue,
                    source,
                    abstract,
                    journal_ref,
                    doi,
                    paradedb.score(id) as rank
                FROM papers
                WHERE (title || ' ' || COALESCE(abstract, '')) @@@ $1
                ORDER BY rank DESC
                LIMIT $2
            """

            rows = await conn.fetch(sql, escaped_query, candidate_limit)

            bm25_results = []
            for row in rows:
                authors = row["authors"] or []
                if isinstance(authors, str):
                    try:
                        authors = json.loads(authors)
                    except json.JSONDecodeError:
                        authors = [authors]

                source = row["source"] or "unknown"
                if source == "arxiv":
                    url = f"https://arxiv.org/abs/{row['id']}"
                    published_date = str(row["year"]) if row["year"] else "N/A"
                elif source == "dblp":
                    url = f"https://dblp.org/rec/{row['id']}.html"
                    published_date = str(row["year"]) if row["year"] else "N/A"
                else:
                    url = row["doi"] or f"https://arxiv.org/abs/{row['id']}"
                    published_date = str(row["year"]) if row["year"] else "N/A"

                bm25_results.append({
                    "result": SearchResult(
                        title=row["title"],
                        authors=authors if isinstance(authors, list) else [],
                        published_date=published_date,
                        venue=row["venue"] or row["journal_ref"] or "N/A",
                        abstract=row["abstract"] or "N/A",
                        url=url,
                        source=f"local_db_{source}",
                    ),
                    "bm25_score": float(row["rank"]),
                })

            # Get rerank scores
            reranked = self._compute_crossencoder_scores(
                query, [r["result"] for r in bm25_results]
            )

            # Build scored results
            scored_results = []
            for i, (bm25_item, (result, rerank_score)) in enumerate(zip(bm25_results, reranked)):
                scored_results.append(ScoredResult(
                    bm25_rank=i + 1,
                    bm25_score=bm25_item["bm25_score"],
                    rerank_score=rerank_score,
                    title=result.title,
                    authors=", ".join(result.authors[:3]) + ("..." if len(result.authors) > 3 else ""),
                    abstract=result.abstract[:150] + "..." if len(result.abstract) > 150 else result.abstract,
                    source=result.source,
                ))

            # Sort by rerank score
            reranked_sorted = sorted(scored_results, key=lambda x: x.rerank_score, reverse=True)

            return scored_results, reranked_sorted[:limit]


async def main():
    """Run interactive reranking test."""
    if len(sys.argv) < 2:
        query = input("Enter search query: ").strip()
    else:
        query = " ".join(sys.argv[1:])

    if not query:
        print("Please provide a search query.")
        return

    print(f"\n{'='*80}")
    print(f"Search Query: \"{query}\"")
    print(f"{'='*80}\n")

    search = TestableLocalDBSearch()

    print("Searching... (fetching BM25 candidates and computing CrossEncoder scores)")
    bm25_results, reranked_top = await search.search_with_scores(query, limit=5)

    print(f"\n{'─'*80}")
    print("ORIGINAL BM25 RANKING (before rerank)")
    print(f"{'─'*80}")
    print(f"{'Rank':<6} {'BM25 Score':<12} {'Rerank Score':<12} {'Title'}")
    print(f"{'─'*80}")

    for r in bm25_results[:10]:  # Show top 10
        title = r.title[:50] + "..." if len(r.title) > 50 else r.title
        print(f"{r.bm25_rank:<6} {r.bm25_score:<12.4f} {r.rerank_score:<12.4f} {title}")

    print(f"\n{'─'*80}")
    print("RERANKED RESULTS (top 5 after CrossEncoder reranking)")
    print(f"{'─'*80}")
    print(f"{'New Rank':<10} {'Old Rank':<10} {'BM25 Score':<12} {'Rerank Score':<12} {'Source'}")
    print(f"{'─'*80}")

    for i, r in enumerate(reranked_top, 1):
        print(f"{i:<10} {r.bm25_rank:<10} {r.bm25_score:<12.4f} {r.rerank_score:<12.4f} {r.source}")
        print(f"  Title: {r.title}")
        print(f"  Authors: {r.authors}")
        print(f"  Abstract: {r.abstract}")
        print()

    # Show rank changes
    print(f"{'─'*80}")
    print("RANK CHANGES ANALYSIS")
    print(f"{'─'*80}")

    original_top5_ids = {r.title: r.bm25_rank for r in bm25_results[:5]}
    reranked_top5_ids = {r.title: i+1 for i, r in enumerate(reranked_top)}

    for title, new_rank in reranked_top5_ids.items():
        old_rank = original_top5_ids.get(title)
        if old_rank:
            change = old_rank - new_rank
            if change > 0:
                change_str = f"↑{change} (promoted)"
            elif change < 0:
                change_str = f"↓{abs(change)} (demoted)"
            else:
                change_str = "→ (unchanged)"
            print(f"  \"{title[:60]}...\": Rank {old_rank} → {new_rank} {change_str}")
        else:
            print(f"  \"{title[:60]}...\": New entry from outside top-5 BM25")

    print(f"\n{'='*80}")


if __name__ == "__main__":
    asyncio.run(main())
