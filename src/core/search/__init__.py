"""Search module for ValiRef.

This module provides search tools and aggregators for querying academic databases.
"""
from .aggregate import (
    AggregateSearchFactory,
    LocalAggregateSearch,
    OnlineAggregateSearch,
    prune_search_result,
)
from .base import SearchResult, SearchTool, run_in_executor_cancellable
from .sources import (
    ArxivSearch,
    DuckDuckGoSearch,
    LocalDBSearch,
    OpenAlexSearch,
    OpenReviewSearch,
    ScholarlySearch,
    SemanticScholarSearch,
)

__all__ = [
    # Base classes
    "SearchResult",
    "SearchTool",
    "run_in_executor_cancellable",
    # Source tools
    "ArxivSearch",
    "DuckDuckGoSearch",
    "LocalDBSearch",
    "OpenAlexSearch",
    "OpenReviewSearch",
    "ScholarlySearch",
    "SemanticScholarSearch",
    # Aggregate tools
    "AggregateSearchFactory",
    "LocalAggregateSearch",
    "OnlineAggregateSearch",
    "prune_search_result",
]
