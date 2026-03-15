"""Utility functions for search results."""
from ..base import SearchResult


def prune_search_result(item: SearchResult) -> SearchResult:
    """Prune result attributes to limit context length."""
    if len(item.title) > 150:
        item.title = item.title[:150] + "..."
    if len(item.abstract) > 300:
        item.abstract = item.abstract[:300] + "..."
    if len(item.authors) > 10:
        item.authors = item.authors[:10]
        item.authors.append("et al.")
    return item
