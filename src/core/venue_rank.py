"""CCF rank lookup for academic venues."""

import json
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from .logger import logger

_DATA_FILE = Path(__file__).parent / "venue_rank_data.json"


@dataclass
class VenueRank:
    ccf_rank: str  # "A", "B", or "C"
    full_name: str  # Official CCF full name


def _word_boundary_match(short: str, long: str) -> bool:
    """Check if short appears as a whole word (or phrase) in long."""
    pattern = r'(?<![A-Z0-9])' + re.escape(short) + r'(?![A-Z0-9])'
    return bool(re.search(pattern, long))


class VenueRankLookup:
    """Lookup CCF rank by venue name (abbreviation or full name)."""

    def __init__(self):
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self):
        if not _DATA_FILE.exists():
            logger.warning("Venue rank data file not found", path=str(_DATA_FILE))
            return
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # Normalize keys to uppercase for case-insensitive lookup
        self._data = {k.upper(): v for k, v in raw.items()}
        logger.info("Loaded venue rank data", entries=len(self._data))

    def lookup(self, venue: Optional[str]) -> Optional[VenueRank]:
        """Look up CCF rank for a venue name.

        Matching strategy (in order):
        1. Exact match (case-insensitive)
        2. Word-boundary substring match
        """
        if not venue or not venue.strip():
            return None

        venue_upper = venue.strip().upper()

        # 1. Exact match
        if venue_upper in self._data:
            entry = self._data[venue_upper]
            return VenueRank(ccf_rank=entry["rank"], full_name=entry.get("full_name", ""))

        # 2. Word-boundary substring match
        # For short keys (abbreviations like "NeurIPS", "CVPR"), word-boundary match is safe.
        # For longer keys, require length ratio >= 0.3 to avoid false positives
        # (e.g., "Nature" matching "PARALLEL PROBLEM SOLVING FROM NATURE").
        for key in sorted(self._data, key=len, reverse=True):
            if len(key) < 3:
                continue
            if not (_word_boundary_match(key, venue_upper) or _word_boundary_match(venue_upper, key)):
                continue
            if len(key) >= 10:
                shorter, longer = sorted([len(key), len(venue_upper)])
                if shorter < longer * 0.3:
                    continue
            entry = self._data[key]
            return VenueRank(ccf_rank=entry["rank"], full_name=entry.get("full_name", ""))

        return None


# Module-level singleton
_lookup: Optional[VenueRankLookup] = None


def get_venue_rank_lookup() -> VenueRankLookup:
    global _lookup
    if _lookup is None:
        _lookup = VenueRankLookup()
    return _lookup
