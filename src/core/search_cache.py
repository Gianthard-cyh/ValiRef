"""
Simple file-based cache for search results.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .logger import logger


class SearchCache:
    """
    File-based cache for search tool results.

    Cache structure:
    {
        "cache_key": {
            "timestamp": 1234567890,
            "data": [...search results...]
        }
    }
    """

    def __init__(self, ttl_seconds: int = 7 * 24 * 60 * 60):  # Default 7 days
        self.ttl_seconds = ttl_seconds
        self.cache_dir = Path.home() / ".cache" / "valiref"
        self.cache_file = self.cache_dir / "search_cache.json"
        self._cache: Dict[str, Any] = {}
        self._ensure_cache_dir()
        self._load_cache()

    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _load_cache(self):
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
                logger.debug("Loaded cached entries", entry_count=len(self._cache))
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Failed to load cache", error=str(e))
                self._cache = {}

    def _save_cache(self):
        """Save cache to disk."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.warning("Failed to save cache", error=str(e))

    def _make_key(self, tool_name: str, query: str, limit: int) -> str:
        """Generate cache key from search parameters."""
        key_str = f"{tool_name}:{query}:{limit}"
        return hashlib.sha256(key_str.encode()).hexdigest()[:32]

    def get(self, tool_name: str, query: str, limit: int) -> Optional[List[Dict]]:
        """
        Get cached result if it exists and is not expired.

        Returns:
            Cached data or None if not found/expired
        """
        key = self._make_key(tool_name, query, limit)
        entry = self._cache.get(key)

        if entry is None:
            return None

        # Check TTL
        age = time.time() - entry.get("timestamp", 0)
        if age > self.ttl_seconds:
            logger.debug("Cache entry expired", tool_name=tool_name, query=query[:50])
            del self._cache[key]
            return None

        logger.debug("Cache hit", tool_name=tool_name, query=query[:50])
        return entry.get("data")

    def set(self, tool_name: str, query: str, limit: int, data: List[Dict]):
        """
        Store result in cache.
        """
        key = self._make_key(tool_name, query, limit)
        self._cache[key] = {
            "timestamp": time.time(),
            "tool": tool_name,
            "query": query[:100],  # Store truncated query for debugging
            "data": data,
        }
        self._save_cache()
        logger.debug("Cached result", tool_name=tool_name, query=query[:50])

    def clear(self):
        """Clear all cached entries."""
        self._cache = {}
        if self.cache_file.exists():
            self.cache_file.unlink()
        logger.info("Search cache cleared")

    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        now = time.time()
        valid = sum(
            1
            for entry in self._cache.values()
            if now - entry.get("timestamp", 0) <= self.ttl_seconds
        )
        return {
            "total_entries": len(self._cache),
            "valid_entries": valid,
            "expired_entries": len(self._cache) - valid,
        }


# Global cache instance
_search_cache: Optional[SearchCache] = None


def get_cache() -> SearchCache:
    """Get or create global cache instance."""
    global _search_cache
    if _search_cache is None:
        _search_cache = SearchCache()
    return _search_cache


def clear_cache():
    """Clear the global cache."""
    cache = get_cache()
    cache.clear()
