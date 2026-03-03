import pytest
from src.core.tools import ArxivSearch, OpenReviewSearch, OpenAlexSearch


@pytest.mark.integration
class TestSearchToolsIntegration:
    """
    Live API integration tests for search tools.
    WARNING: These tests make real network requests and may be slow or rate-limited.
    """

    def test_arxiv_live(self):
        """Test ArXiv API with a real query."""
        tool = ArxivSearch()
        # "Attention Is All You Need" is a classic paper
        query = "Attention Is All You Need"
        results = tool.search(query, limit=3)

        assert len(results) > 0, "ArXiv should return results for a known paper"

        # Check the first result
        first = results[0]
        assert "title" in first
        assert "authors" in first
        assert first["source"] == "arxiv"

        # Basic content check
        assert "Attention" in first["title"]
        print(f"✅ ArXiv found: {first['title']} ({first['arxiv_id']})")

    def test_openalex_live(self):
        """Test OpenAlex API with a real query."""
        tool = OpenAlexSearch()
        query = "Attention Is All You Need"
        results = tool.search(query, limit=3)

        assert len(results) > 0, "OpenAlex should return results"

        first = results[0]
        assert "title" in first
        assert first["source"] == "openalex"
        print(f"✅ OpenAlex found: {first['title']} (Year: {first['published']})")

    def test_openreview_live(self):
        """Test OpenReview API with a real query."""
        tool = OpenReviewSearch()

        # Try exact title match for OpenReview API
        # "Language Models are Few-Shot Learners" - NeurIPS 2020
        query = "Language Models are Few-Shot Learners"
        results = tool.search(query, limit=5)

        # OpenReview MUST return results now
        assert isinstance(results, list)
        assert len(results) > 0, f"OpenReview returned no results for query: '{query}'"

        first = results[0]
        assert "source" in first
        # OpenReview returns v1 or v2 sources
        assert first["source"].startswith("openreview")
        print(f"✅ OpenReview found: {first['title']} (Source: {first['source']})")
