"""
Search tools for ValiRef Agent.

.. deprecated::
    This module is kept for backward compatibility.
    Please use `src.core.search` instead.
"""
# Re-export everything from the new search module for backward compatibility
from src.core.search import (
    AggregateSearchFactory,
    ArxivSearch,
    DuckDuckGoSearch,
    LocalAggregateSearch,
    LocalDBSearch,
    OnlineAggregateSearch,
    OpenAlexSearch,
    OpenReviewSearch,
    ScholarlySearch,
    SearchResult,
    SearchTool,
    SemanticScholarSearch,
    prune_search_result,
    run_in_executor_cancellable,
)

__all__ = [
    "SearchResult",
    "SearchTool",
    "run_in_executor_cancellable",
    "ArxivSearch",
    "ScholarlySearch",
    "SemanticScholarSearch",
    "OpenReviewSearch",
    "OpenAlexSearch",
    "DuckDuckGoSearch",
    "LocalDBSearch",
    "LocalAggregateSearch",
    "OnlineAggregateSearch",
    "prune_search_result",
    "AggregateSearchFactory",
]
