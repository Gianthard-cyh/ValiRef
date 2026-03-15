"""Aggregate search factory."""
from .local import LocalAggregateSearch
from .online import OnlineAggregateSearch


class AggregateSearchFactory:
    """Search aggregator factory, supports local and online modes."""

    @staticmethod
    def create(mode: str = "local"):
        """
        Create search aggregator.

        Args:
            mode: "local" or "online"

        Returns:
            LocalAggregateSearch or OnlineAggregateSearch instance
        """
        if mode == "local":
            return LocalAggregateSearch()
        elif mode == "online":
            return OnlineAggregateSearch()
        else:
            raise ValueError(f"Unknown search mode: {mode}")
