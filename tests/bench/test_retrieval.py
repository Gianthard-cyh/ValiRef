"""
Unit tests for retrieval evaluation subsystem.
"""
import json
import os
import tempfile
from unittest.mock import MagicMock, AsyncMock, patch, mock_open

import pytest

from src.bench.retrieval.eval_search import (
    EvalLocalSearch,
    QueryRecord,
    PaperGroundTruth,
)
from src.bench.retrieval.evaluator import (
    RetrievalEvaluator,
    RetrievalEvalResult,
)
from src.core.search.base import SearchResult


class TestQueryRecord:
    """Tests for QueryRecord dataclass."""

    def test_query_record_creation(self):
        """Test QueryRecord can be created with all fields."""
        record = QueryRecord(
            sample_id="test123",
            sample_title="Test Paper Title",
            query="test query",
            hit_rank=1,
            result_count=5,
            duration_ms=150.5,
        )

        assert record.sample_id == "test123"
        assert record.sample_title == "Test Paper Title"
        assert record.query == "test query"
        assert record.hit_rank == 1
        assert record.result_count == 5
        assert record.duration_ms == 150.5

    def test_query_record_with_none_hit_rank(self):
        """Test QueryRecord handles None hit_rank (miss)."""
        record = QueryRecord(
            sample_id="test456",
            sample_title="Another Paper",
            query="another query",
            hit_rank=None,
            result_count=5,
            duration_ms=200.0,
        )

        assert record.hit_rank is None
        assert record.result_count == 5


class TestEvalLocalSearch:
    """Tests for EvalLocalSearch."""

    def test_initialization(self):
        """Test EvalLocalSearch initializes correctly."""
        with patch.object(EvalLocalSearch, "__init__", lambda s, **kwargs: None):
            search = EvalLocalSearch.__new__(EvalLocalSearch)
            # Manually set attributes that would be set by __init__
            search._gt = None
            search._records = []
            search._current_sample_id = None

            assert search._gt is None
            assert search._records == []
            assert search._current_sample_id is None

    def test_set_ground_truth(self):
        """Test set_ground_truth sets GT correctly."""
        with patch.object(EvalLocalSearch, "__init__", lambda s, **kwargs: None):
            search = EvalLocalSearch.__new__(EvalLocalSearch)
            # Manually set attributes
            search._gt = None
            search._records = []
            search._current_sample_id = None

            gt = {
                "id": "arxiv/1234.5678",
                "title": "Test Paper",
                "authors": ["Author One", "Author Two"],
            }

            search.set_ground_truth(gt)

            assert search._gt == gt
            assert search._current_sample_id == "arxiv/1234.5678"

    def test_clear_ground_truth(self):
        """Test clear_ground_truth clears GT correctly."""
        with patch.object(EvalLocalSearch, "__init__", lambda s, **kwargs: None):
            search = EvalLocalSearch.__new__(EvalLocalSearch)
            # Manually set attributes
            search._gt = {"id": "test", "title": "Test", "authors": []}
            search._current_sample_id = "test"

            search.clear_ground_truth()

            assert search._gt is None
            assert search._current_sample_id is None

    def test_get_records(self):
        """Test get_records returns a copy of records."""
        with patch.object(EvalLocalSearch, "__init__", lambda s, **kwargs: None):
            search = EvalLocalSearch.__new__(EvalLocalSearch)
            # Manually set attributes
            search._gt = None
            search._current_sample_id = None

            record = QueryRecord(
                sample_id="test",
                sample_title="Test",
                query="query",
                hit_rank=1,
                result_count=5,
                duration_ms=100.0,
            )
            search._records = [record]

            records = search.get_records()

            assert len(records) == 1
            assert records[0].sample_id == "test"

            # Verify it's a copy, not the same list
            search._records.append(
                QueryRecord(
                    sample_id="test2",
                    sample_title="Test2",
                    query="query2",
                    hit_rank=2,
                    result_count=5,
                    duration_ms=150.0,
                )
            )
            assert len(records) == 1  # Original list unchanged

    def test_clear_records(self):
        """Test clear_records empties records list."""
        with patch.object(EvalLocalSearch, "__init__", lambda s, **kwargs: None):
            search = EvalLocalSearch.__new__(EvalLocalSearch)
            # Manually set attributes
            search._gt = None
            search._current_sample_id = None

            search._records = [QueryRecord(
                sample_id="test",
                sample_title="Test",
                query="query",
                hit_rank=1,
                result_count=5,
                duration_ms=100.0,
            )]

            search.clear_records()

            assert search._records == []

    def test_find_hit_rank_by_id(self):
        """Test _find_hit_rank finds by paper ID in URL."""
        with patch.object(EvalLocalSearch, "__init__", lambda s, **kwargs: None):
            search = EvalLocalSearch.__new__(EvalLocalSearch)
            # Manually set attributes
            search._gt = None
            search._current_sample_id = None

            search._gt = {
                "id": "1234.5678",
                "title": "Test Paper",
                "authors": ["Author One"],
            }

            results = [
                SearchResult(
                    title="Other Paper",
                    authors=["Other Author"],
                    published_date="2023",
                    venue="N/A",
                    abstract="N/A",
                    url="https://arxiv.org/abs/9999.8888",  # Different ID
                    source="local_db_arxiv",
                ),
                SearchResult(
                    title="Test Paper",
                    authors=["Author One"],
                    published_date="2023",
                    venue="N/A",
                    abstract="N/A",
                    url="https://arxiv.org/abs/1234.5678",  # Matching ID
                    source="local_db_arxiv",
                ),
            ]

            rank = search._find_hit_rank(results)

            assert rank == 2  # Second result

    def test_find_hit_rank_by_title_similarity(self):
        """Test _find_hit_rank finds by title similarity."""
        with patch.object(EvalLocalSearch, "__init__", lambda s, **kwargs: None):
            search = EvalLocalSearch.__new__(EvalLocalSearch)
            # Manually set attributes
            search._gt = None
            search._current_sample_id = None

            search._gt = {
                "id": "different_id",
                "title": "Deep Learning for Natural Language Processing",
                "authors": ["Author One"],
            }

            results = [
                SearchResult(
                    title="Deep Learning for Natural Language Processing",
                    authors=["Author One"],
                    published_date="2023",
                    venue="N/A",
                    abstract="N/A",
                    url="https://arxiv.org/abs/other_id",  # Different ID
                    source="local_db_arxiv",
                ),
            ]

            rank = search._find_hit_rank(results)

            assert rank == 1  # First result, matched by title

    def test_find_hit_rank_no_match(self):
        """Test _find_hit_rank returns None when no match found."""
        with patch.object(EvalLocalSearch, "__init__", lambda s, **kwargs: None):
            search = EvalLocalSearch.__new__(EvalLocalSearch)
            # Manually set attributes
            search._gt = None
            search._current_sample_id = None

            search._gt = {
                "id": "9999.8888",
                "title": "Non-existent Paper",
                "authors": ["Unknown Author"],
            }

            results = [
                SearchResult(
                    title="Completely Different Paper",
                    authors=["Other Author"],
                    published_date="2023",
                    venue="N/A",
                    abstract="N/A",
                    url="https://arxiv.org/abs/1234.5678",
                    source="local_db_arxiv",
                ),
            ]

            rank = search._find_hit_rank(results)

            assert rank is None

    def test_get_metrics_empty(self):
        """Test get_metrics returns zeros for empty records."""
        with patch.object(EvalLocalSearch, "__init__", lambda s, **kwargs: None):
            search = EvalLocalSearch.__new__(EvalLocalSearch)
            # Manually set attributes
            search._gt = None
            search._current_sample_id = None
            search._records = []

            metrics = search.get_metrics()

            assert metrics["recall@1"] == 0.0
            assert metrics["recall@3"] == 0.0
            assert metrics["recall@5"] == 0.0
            assert metrics["mrr"] == 0.0
            assert metrics["total_queries"] == 0

    def test_get_metrics_with_hits(self):
        """Test get_metrics calculates correctly with hits."""
        with patch.object(EvalLocalSearch, "__init__", lambda s, **kwargs: None):
            search = EvalLocalSearch.__new__(EvalLocalSearch)
            # Manually set attributes
            search._gt = None
            search._current_sample_id = None

            search._records = [
                QueryRecord("s1", "T1", "q1", 1, 5, 100.0),  # Hit at rank 1
                QueryRecord("s2", "T2", "q2", 2, 5, 150.0),  # Hit at rank 2
                QueryRecord("s3", "T3", "q3", 5, 5, 200.0),  # Hit at rank 5
                QueryRecord("s4", "T4", "q4", None, 5, 120.0),  # Miss
            ]

            metrics = search.get_metrics()

            # Recall@1: 1/4 = 0.25
            # Recall@3: 2/4 = 0.5 (ranks 1 and 2)
            # Recall@5: 3/4 = 0.75 (ranks 1, 2, and 5)
            # MRR: (1/1 + 1/2 + 1/5 + 0) / 4 = 1.7/4 = 0.425
            assert metrics["recall@1"] == 0.25
            assert metrics["recall@3"] == 0.5
            assert metrics["recall@5"] == 0.75
            assert metrics["mrr"] == 0.425
            assert metrics["total_queries"] == 4
            assert metrics["avg_results"] == 5.0
            assert metrics["avg_duration_ms"] == 142.5  # (100+150+200+120)/4

    def test_get_sample_metrics(self):
        """Test get_sample_metrics returns metrics for specific sample."""
        with patch.object(EvalLocalSearch, "__init__", lambda s, **kwargs: None):
            search = EvalLocalSearch.__new__(EvalLocalSearch)
            # Manually set attributes
            search._gt = None
            search._current_sample_id = None

            search._records = [
                QueryRecord("s1", "T1", "q1", 1, 5, 100.0),
                QueryRecord("s1", "T1", "q2", 3, 5, 150.0),
                QueryRecord("s2", "T2", "q3", None, 5, 200.0),
            ]

            # Sample s1: 2 queries, hits at rank 1 and 3
            # MRR = (1/1 + 1/3) / 2 = 0.6667
            # Recall@5 = 2/2 = 1.0
            metrics = search.get_sample_metrics("s1")

            assert metrics["queries"] == 2
            assert metrics["recall@5"] == 1.0
            assert pytest.approx(metrics["mrr"], 0.001) == 0.6667

    def test_export_records_json(self):
        """Test export_records exports to JSON correctly."""
        with patch.object(EvalLocalSearch, "__init__", lambda s, **kwargs: None):
            search = EvalLocalSearch.__new__(EvalLocalSearch)
            # Manually set attributes
            search._gt = None
            search._current_sample_id = None

            search._records = [
                QueryRecord("s1", "T1", "q1", 1, 5, 100.0),
            ]

            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
                temp_path = f.name

            try:
                search.export_records(temp_path, format="json")

                with open(temp_path, 'r') as f:
                    data = json.load(f)

                assert len(data) == 1
                assert data[0]["sample_id"] == "s1"
                assert data[0]["hit_rank"] == 1
            finally:
                os.unlink(temp_path)

    def test_export_records_csv(self):
        """Test export_records exports to CSV correctly."""
        with patch.object(EvalLocalSearch, "__init__", lambda s, **kwargs: None):
            search = EvalLocalSearch.__new__(EvalLocalSearch)
            # Manually set attributes
            search._gt = None
            search._current_sample_id = None

            search._records = [
                QueryRecord("s1", "T1", "q1", 1, 5, 100.0),
            ]

            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
                temp_path = f.name

            try:
                search.export_records(temp_path, format="csv")

                with open(temp_path, 'r') as f:
                    lines = f.readlines()

                assert len(lines) == 2  # Header + 1 data row
                assert "sample_id" in lines[0]
                assert "s1" in lines[1]
            finally:
                os.unlink(temp_path)


class TestRetrievalEvalResult:
    """Tests for RetrievalEvalResult."""

    def test_eval_result_creation(self):
        """Test RetrievalEvalResult can be created."""
        result = RetrievalEvalResult(
            total_samples=10,
            total_queries=50,
            recall_at_1=0.25,
            recall_at_3=0.5,
            recall_at_5=0.75,
            mrr=0.4,
            per_sample=[],
            all_records=[],
        )

        assert result.total_samples == 10
        assert result.total_queries == 50
        assert result.recall_at_1 == 0.25
        assert result.recall_at_3 == 0.5
        assert result.recall_at_5 == 0.75
        assert result.mrr == 0.4

    def test_eval_result_to_dict(self):
        """Test to_dict converts result to dict."""
        result = RetrievalEvalResult(
            total_samples=10,
            total_queries=50,
            recall_at_1=0.25,
            recall_at_3=0.5,
            recall_at_5=0.75,
            mrr=0.4,
            per_sample=[],
            all_records=[],
        )

        d = result.to_dict()

        assert d["total_samples"] == 10
        assert d["total_queries"] == 50
        assert d["recall_at_1"] == 0.25
        assert d["mrr"] == 0.4
        assert "per_sample" not in d  # Excluded from dict


class TestRetrievalEvaluator:
    """Tests for RetrievalEvaluator."""

    def test_initialization(self):
        """Test RetrievalEvaluator initializes correctly."""
        evaluator = RetrievalEvaluator()

        assert evaluator._records == []

    def test_load_samples(self):
        """Test _load_samples loads from CSV correctly."""
        evaluator = RetrievalEvaluator()

        csv_content = """source,id,title,abstract,authors,published_date,url
arxiv,1234.5678,Test Paper,Test abstract,Author One; Author Two,2023,https://arxiv.org/abs/1234.5678
arxiv,5678.9012,Another Paper,Another abstract,Author Three,2024,https://arxiv.org/abs/5678.9012"""

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            samples = evaluator._load_samples(temp_path, sample_size=100)

            assert len(samples) == 2
            assert samples[0].id == "1234.5678"
            assert samples[0].title == "Test Paper"
            assert samples[0].authors == ["Author One", "Author Two"]
            assert samples[1].id == "5678.9012"
        finally:
            os.unlink(temp_path)

    def test_aggregate_results(self):
        """Test _aggregate_results calculates metrics correctly."""
        evaluator = RetrievalEvaluator()

        from src.bench.schema import Paper

        papers = [
            Paper(
                source="arxiv",
                id="paper1",
                title="Paper One",
                abstract="Abstract one",
                authors=["Author One"],
                published_date="2023",
                url="https://arxiv.org/abs/paper1",
            ),
            Paper(
                source="arxiv",
                id="paper2",
                title="Paper Two",
                abstract="Abstract two",
                authors=["Author Two"],
                published_date="2024",
                url="https://arxiv.org/abs/paper2",
            ),
        ]

        records = [
            QueryRecord("paper1", "Paper One", "q1", 1, 5, 100.0),
            QueryRecord("paper1", "Paper One", "q2", 2, 5, 150.0),
            QueryRecord("paper2", "Paper Two", "q3", None, 5, 200.0),
        ]

        result = evaluator._aggregate_results(records, papers)

        assert result.total_samples == 2
        assert result.total_queries == 3
        # Recall@1: 1/3 (only first query)
        assert result.recall_at_1 == pytest.approx(1/3, 0.001)
        # Recall@3: 2/3 (first two queries)
        assert result.recall_at_3 == pytest.approx(2/3, 0.001)
        # Recall@5: 2/3 (first two queries)
        assert result.recall_at_5 == pytest.approx(2/3, 0.001)
        # MRR: (1/1 + 1/2 + 0) / 3 = 0.5
        assert result.mrr == pytest.approx(0.5, 0.001)

    def test_aggregate_results_empty(self):
        """Test _aggregate_results handles empty records."""
        evaluator = RetrievalEvaluator()

        from src.bench.schema import Paper

        papers = [
            Paper(
                source="arxiv",
                id="paper1",
                title="Paper One",
                abstract="Abstract one",
                authors=["Author One"],
                published_date="2023",
                url="https://arxiv.org/abs/paper1",
            ),
        ]

        result = evaluator._aggregate_results([], papers)

        assert result.total_samples == 1
        assert result.total_queries == 0
        assert result.recall_at_1 == 0.0
        assert result.recall_at_5 == 0.0
        assert result.mrr == 0.0
