"""Aggregate search module."""
from .factory import AggregateSearchFactory
from .local import LocalAggregateSearch
from .online import OnlineAggregateSearch
from .utils import prune_search_result

__all__ = [
    "AggregateSearchFactory",
    "LocalAggregateSearch",
    "OnlineAggregateSearch",
    "prune_search_result",
]
