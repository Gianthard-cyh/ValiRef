"""Local ParadeDB search tool implementation with CrossEncoder reranking."""

import json
from typing import Optional

import asyncpg
from sentence_transformers import CrossEncoder

from ...config import (
    CROSSENCODER_DEVICE,
    CROSSENCODER_MODEL_NAME,
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    RERANK_CANDIDATE_MULTIPLIER,
)
from ...logger import logger
from ..base import SearchResult, SearchTool, run_in_executor_cancellable


class LocalDBSearch(SearchTool):
    """Local ParadeDB BM25 search with CrossEncoder semantic reranking."""

    token_bucket_rate = 20.0  # Local database can support higher QPS

    MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANK_CANDIDATE_MULTIPLIER = 4  # Get 4x candidates for reranking

    def __init__(self):
        super().__init__()
        self.db_config = {
            "host": DB_HOST,
            "port": DB_PORT,
            "user": DB_USER,
            "password": DB_PASSWORD,
            "database": DB_NAME,
        }
        self._pool: Optional[asyncpg.Pool] = None
        self._model: Optional[CrossEncoder] = None

    def _get_model(self) -> CrossEncoder:
        """Lazy load the CrossEncoder model."""
        if self._model is None:
            logger.info(
                f"[LocalDBSearch] Loading CrossEncoder model: {self.MODEL_NAME}"
            )
            self._model = CrossEncoder(self.MODEL_NAME, device="cpu", max_length=512)
            logger.info(f"[LocalDBSearch] CrossEncoder model loaded successfully")
        return self._model

    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=self.db_config["host"],
                port=self.db_config["port"],
                user=self.db_config["user"],
                password=self.db_config["password"],
                database=self.db_config["database"],
                min_size=2,
                max_size=10,
            )
        return self._pool

    def _compute_crossencoder_scores(
        self, query: str, results: list[SearchResult]
    ) -> list[tuple[SearchResult, float]]:
        """
        Compute relevance scores using CrossEncoder.

        CrossEncoder takes (query, document) pairs and outputs a relevance score,
        which is more accurate than BiEncoder cosine similarity for reranking.

        Args:
            query: The search query
            results: List of search results

        Returns:
            List of (result, relevance_score) tuples
        """
        if not results:
            return []

        model = self._get_model()

        # Prepare query-document pairs
        # CrossEncoder expects list of [query, text] pairs
        pairs = []
        for r in results:
            # Combine title and abstract for document text
            doc_text = r.title
            if r.abstract and r.abstract != "N/A":
                # Truncate abstract if too long (CrossEncoder has max_length limit)
                abstract = r.abstract[:2000] if len(r.abstract) > 2000 else r.abstract
                doc_text += " " + abstract
            pairs.append([query, doc_text])

        # Compute scores in batch (more efficient)
        scores = model.predict(
            pairs, batch_size=32, show_progress_bar=False, convert_to_numpy=True
        )

        # Pair results with scores
        return [(r, float(s)) for r, s in zip(results, scores)]

    def _rerank_results(
        self, query: str, results: list[SearchResult], limit: int
    ) -> list[SearchResult]:
        """
        Rerank BM25 results using CrossEncoder.

        Args:
            query: The search query
            results: BM25 search results
            limit: Number of top results to return

        Returns:
            Reranked list of search results
        """
        if len(results) <= 1:
            return results[:limit]

        # Compute CrossEncoder scores
        scored_results = self._compute_crossencoder_scores(query, results)

        # Sort by relevance score (descending)
        scored_results.sort(key=lambda x: x[1], reverse=True)

        # Log reranking info
        if len(scored_results) >= 2:
            logger.info(
                f"[LocalDBSearch] CrossEncoder reranked {len(results)} results: "
                f"top_score={scored_results[0][1]:.4f}, "
                f"min_score={scored_results[-1][1]:.4f}"
            )

        # Return top-k results
        return [r for r, _ in scored_results[:limit]]

    async def _perform_asearch(self, query: str, limit: int = 5) -> list[SearchResult]:
        """Search local ParadeDB using BM25 with CrossEncoder reranking."""
        pool = await self._get_pool()

        try:
            async with pool.acquire() as conn:
                # Escape the query for ParadeDB: wrap in double quotes to treat as phrase
                escaped_query = f'"{query.replace('"', '\\"')}"'

                # Fetch more candidates for reranking
                candidate_limit = limit * self.RERANK_CANDIDATE_MULTIPLIER

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

                results = []
                for row in rows:
                    # Parse authors (stored as array in PostgreSQL)
                    authors = row["authors"] or []
                    if isinstance(authors, str):
                        try:
                            authors = json.loads(authors)
                        except json.JSONDecodeError:
                            authors = [authors]

                    # Build URL based on source
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

                    results.append(
                        SearchResult(
                            title=row["title"],
                            authors=authors if isinstance(authors, list) else [],
                            published_date=published_date,
                            venue=row["venue"] or row["journal_ref"] or "N/A",
                            abstract=row["abstract"] or "N/A",
                            url=url,
                            source=f"local_db_{source}",
                        )
                    )

                reranked_results = self._rerank_results(query, results, limit)

                return reranked_results

        except Exception as e:
            logger.error(f"[LocalDBSearch] Database query failed: {e}")
            raise
