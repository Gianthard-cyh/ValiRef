#!/usr/bin/env python3
"""
Benchmark search performance for ParadeDB.
Tests BM25 and vector search under various concurrency levels.

Usage:
    python benchmark_search.py --concurrency 10 50 100 --queries 1000
    python benchmark_search.py --test bm25 --concurrency 10 --queries 500
    python benchmark_search.py --test vector --source arxiv
"""

import os
import time
import argparse
import statistics
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import json

import psycopg2

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "user": os.getenv("DB_USER", "valiref"),
    "password": os.getenv("DB_PASSWORD", "valiref_secret"),
    "database": os.getenv("DB_NAME", "arxiv_db"),
}

# Test queries covering different domains
TEST_QUERIES = [
    "neural network",
    "transformer",
    "attention mechanism",
    "graph neural network",
    "optimization",
    "machine learning",
    "deep learning",
    "natural language processing",
    "computer vision",
    "reinforcement learning",
    "large language model",
    "generative AI",
]


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""

    test_name: str
    concurrency: int
    total_queries: int
    total_time: float
    latencies: List[float] = field(default_factory=list)
    errors: int = 0

    @property
    def qps(self) -> float:
        return self.total_queries / self.total_time if self.total_time > 0 else 0

    @property
    def avg_latency(self) -> float:
        return statistics.mean(self.latencies) if self.latencies else 0

    @property
    def p50_latency(self) -> float:
        return statistics.median(self.latencies) if self.latencies else 0

    @property
    def p95_latency(self) -> float:
        if not self.latencies:
            return 0
        sorted_lat = sorted(self.latencies)
        idx = int(len(sorted_lat) * 0.95)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    @property
    def p99_latency(self) -> float:
        if not self.latencies:
            return 0
        sorted_lat = sorted(self.latencies)
        idx = int(len(sorted_lat) * 0.99)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    def to_dict(self) -> Dict:
        return {
            "test_name": self.test_name,
            "concurrency": self.concurrency,
            "total_queries": self.total_queries,
            "total_time_sec": round(self.total_time, 2),
            "qps": round(self.qps, 2),
            "avg_latency_ms": round(self.avg_latency * 1000, 2),
            "p50_latency_ms": round(self.p50_latency * 1000, 2),
            "p95_latency_ms": round(self.p95_latency * 1000, 2),
            "p99_latency_ms": round(self.p99_latency * 1000, 2),
            "errors": self.errors,
        }


class SearchBenchmark:
    """Benchmark runner for search queries."""

    def __init__(self):
        self.db_url = (
            f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
            f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        )

    def _get_connection(self):
        """Get synchronous database connection."""
        return psycopg2.connect(**DB_CONFIG)

    def bm25_search(self, query: str, source: Optional[str] = None) -> float:
        """Execute BM25 search and return latency in seconds."""
        start = time.perf_counter()

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            where_clauses = ["(title || ' ' || COALESCE(abstract, '')) @@@ %s"]
            params = [query]

            if source:
                where_clauses.append("source = %s")
                params.append(source)

            sql = f"""
                SELECT id, title, paradedb.score(id) as rank
                FROM papers
                WHERE {" AND ".join(where_clauses)}
                ORDER BY rank DESC
                LIMIT 10
            """
            cursor.execute(sql, params)
            cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

        return time.perf_counter() - start

    def bm25_with_filters(
        self, query: str, year_from: int = 2020, source: str = "arxiv"
    ) -> float:
        """Execute BM25 search with year and source filters."""
        start = time.perf_counter()

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            sql = """
                SELECT id, title, paradedb.score(id) as rank
                FROM papers
                WHERE (title || ' ' || COALESCE(abstract, '')) @@@ %s
                  AND year >= %s
                  AND source = %s
                ORDER BY rank DESC
                LIMIT 10
            """
            cursor.execute(sql, (query, year_from, source))
            cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

        return time.perf_counter() - start

    def run_concurrent_benchmark(
        self, test_func, concurrency: int, total_queries: int, test_name: str
    ) -> BenchmarkResult:
        """Run benchmark with specified concurrency level."""
        print(
            f"\n🔥 Running {test_name} with concurrency={concurrency}, queries={total_queries}"
        )

        latencies = []
        errors = 0

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            # Submit all tasks
            futures = []
            for i in range(total_queries):
                query = TEST_QUERIES[i % len(TEST_QUERIES)]
                future = executor.submit(test_func, query)
                futures.append(future)

            # Collect results
            for future in as_completed(futures):
                try:
                    latency = future.result()
                    latencies.append(latency)
                except Exception as e:
                    errors += 1
                    if errors <= 5:  # Only print first 5 errors
                        print(f"   Error: {e}")

        total_time = time.time() - start_time

        result = BenchmarkResult(
            test_name=test_name,
            concurrency=concurrency,
            total_queries=total_queries,
            total_time=total_time,
            latencies=latencies,
            errors=errors,
        )

        self._print_result(result)
        return result

    def _print_result(self, result: BenchmarkResult):
        """Print benchmark result."""
        print(f"   QPS: {result.qps:.1f}")
        print(f"   Avg latency: {result.avg_latency * 1000:.1f}ms")
        print(f"   P50 latency: {result.p50_latency * 1000:.1f}ms")
        print(f"   P95 latency: {result.p95_latency * 1000:.1f}ms")
        print(f"   P99 latency: {result.p99_latency * 1000:.1f}ms")
        if result.errors > 0:
            print(f"   Errors: {result.errors}")

    def benchmark_bm25_simple(
        self, concurrency_levels: List[int], queries: int
    ) -> List[BenchmarkResult]:
        """Benchmark simple BM25 search."""
        print("\n" + "=" * 70)
        print("TEST 1: BM25 Simple Search (no filters)")
        print("=" * 70)

        results = []
        for concurrency in concurrency_levels:
            result = self.run_concurrent_benchmark(
                test_func=lambda q: self.bm25_search(q),
                concurrency=concurrency,
                total_queries=queries,
                test_name="BM25 Simple",
            )
            results.append(result)

        return results

    def benchmark_bm25_filtered(
        self, concurrency_levels: List[int], queries: int
    ) -> List[BenchmarkResult]:
        """Benchmark BM25 with filters."""
        print("\n" + "=" * 70)
        print("TEST 2: BM25 with Filters (year >= 2020, source = arxiv)")
        print("=" * 70)

        results = []
        for concurrency in concurrency_levels:
            result = self.run_concurrent_benchmark(
                test_func=lambda q: self.bm25_with_filters(
                    q, year_from=2020, source="arxiv"
                ),
                concurrency=concurrency,
                total_queries=queries,
                test_name="BM25 Filtered",
            )
            results.append(result)

        return results

    def benchmark_bm25_by_source(
        self, concurrency_levels: List[int], queries: int
    ) -> List[BenchmarkResult]:
        """Benchmark BM25 searching only arXiv or only DBLP."""
        print("\n" + "=" * 70)
        print("TEST 3: BM25 by Source (arxiv vs dblp)")
        print("=" * 70)

        results = []

        # arXiv only
        print("\n   --- arXiv only ---")
        for concurrency in concurrency_levels:
            result = self.run_concurrent_benchmark(
                test_func=lambda q: self.bm25_search(q, source="arxiv"),
                concurrency=concurrency,
                total_queries=queries,
                test_name="BM25 arXiv",
            )
            results.append(result)

        # DBLP only
        print("\n   --- DBLP only ---")
        for concurrency in concurrency_levels:
            result = self.run_concurrent_benchmark(
                test_func=lambda q: self.bm25_search(q, source="dblp"),
                concurrency=concurrency,
                total_queries=queries,
                test_name="BM25 DBLP",
            )
            results.append(result)

        return results

    def get_database_stats(self) -> Dict:
        """Get database statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {}
        try:
            # Total counts
            cursor.execute("SELECT COUNT(*) FROM papers")
            stats["total_papers"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM papers WHERE source = 'arxiv'")
            stats["arxiv_papers"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM papers WHERE source = 'dblp'")
            stats["dblp_papers"] = cursor.fetchone()[0]

            # Year range
            cursor.execute("""
                SELECT MIN(year), MAX(year)
                FROM papers WHERE year IS NOT NULL
            """)
            min_year, max_year = cursor.fetchone()
            stats["year_range"] = f"{min_year} - {max_year}"

            # Table size
            cursor.execute("""
                SELECT pg_size_pretty(pg_total_relation_size('papers'))
            """)
            stats["table_size"] = cursor.fetchone()[0]

            # Index sizes
            cursor.execute("""
                SELECT indexname, pg_size_pretty(pg_relation_size(indexrelid))
                FROM pg_indexes
                JOIN pg_stat_user_indexes ON pg_indexes.indexname = pg_stat_user_indexes.indexrelname
                WHERE tablename = 'papers'
            """)
            stats["indexes"] = {row[0]: row[1] for row in cursor.fetchall()}

        finally:
            cursor.close()
            conn.close()

        return stats


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark ParadeDB search performance"
    )
    parser.add_argument(
        "-c",
        "--concurrency",
        type=int,
        nargs="+",
        default=[10, 50, 100],
        help="Concurrency levels to test (default: 10 50 100)",
    )
    parser.add_argument(
        "-q",
        "--queries",
        type=int,
        default=1000,
        help="Total number of queries per test (default: 1000)",
    )
    parser.add_argument(
        "-t",
        "--test",
        type=str,
        choices=["all", "bm25", "bm25-filtered", "bm25-source"],
        default="all",
        help="Which test to run (default: all)",
    )
    parser.add_argument(
        "-o", "--output", type=str, default=None, help="Output file for JSON results"
    )
    args = parser.parse_args()

    print("🚀 ParadeDB Search Benchmark")
    print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Concurrency levels: {args.concurrency}")
    print(f"   Queries per test: {args.queries}")

    benchmark = SearchBenchmark()

    # Get database stats
    print("\n📊 Database Statistics:")
    stats = benchmark.get_database_stats()
    print(f"   Total papers: {stats['total_papers']:,}")
    print(f"   arXiv papers: {stats['arxiv_papers']:,}")
    print(f"   DBLP papers: {stats['dblp_papers']:,}")
    print(f"   Year range: {stats['year_range']}")
    print(f"   Table size: {stats['table_size']}")
    print("   Indexes:")
    for idx_name, idx_size in stats["indexes"].items():
        print(f"      {idx_name}: {idx_size}")

    all_results = []

    # Run selected tests
    if args.test in ("all", "bm25"):
        results = benchmark.benchmark_bm25_simple(args.concurrency, args.queries)
        all_results.extend(results)

    if args.test in ("all", "bm25-filtered"):
        results = benchmark.benchmark_bm25_filtered(args.concurrency, args.queries)
        all_results.extend(results)

    if args.test in ("all", "bm25-source"):
        results = benchmark.benchmark_bm25_by_source(args.concurrency, args.queries)
        all_results.extend(results)

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'Test':<25} {'Conc':>6} {'QPS':>10} {'Avg(ms)':>10} {'P99(ms)':>10}")
    print("-" * 70)
    for r in all_results:
        print(
            f"{r.test_name:<25} {r.concurrency:>6} {r.qps:>10.1f} {r.avg_latency * 1000:>10.1f} {r.p99_latency * 1000:>10.1f}"
        )

    # Save results to file
    if args.output:
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "database_stats": stats,
            "benchmark_results": [r.to_dict() for r in all_results],
        }
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"\n💾 Results saved to: {args.output}")

    print(f"\n⏱️  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
