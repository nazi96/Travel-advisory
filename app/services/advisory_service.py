"""
Service for retrieving U.S. State Department travel advisories.

The service combines two sources:

  1. A curated fallback dataset of ~215 countries (data/fallback_advisories.py),
     compiled from a snapshot of travel.state.gov. Always available, never
     fails. This is the default source.

  2. A live HTML scraper of travel.state.gov (live_advisory_fetcher) which,
     when reachable, overrides the fallback with current data. A successful
     live fetch is cached for one hour.

Lookups are case-insensitive. Failures of the live source are completely
transparent to callers — the fallback dataset always answers.
"""
from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional

from app.data.fallback_advisories import FALLBACK_ADVISORIES
from app.models import TravelAdvisory
from app.services.live_advisory_fetcher import LiveAdvisoryFetcher, UPSTREAM_URL

logger = logging.getLogger(__name__)


class AdvisoryService:
    """Serves travel advisories from a live source with a fallback."""

    def __init__(self, enable_live: bool = True, timeout: float = 10.0):
        self.enable_live = enable_live
        self._lock = threading.Lock()
        self._cache: Dict[str, TravelAdvisory] = {}
        self._source: str = "fallback"  # "fallback" or "live"
        self._fetcher = LiveAdvisoryFetcher(timeout=timeout) if enable_live else None
        self._load_fallback()

    # ------------------------------------------------------------------
    # Cache loaders
    # ------------------------------------------------------------------
    def _load_fallback(self) -> None:
        with self._lock:
            self._cache.clear()
            for country, data in FALLBACK_ADVISORIES.items():
                self._cache[country.lower()] = TravelAdvisory(
                    country=country,
                    advisory_level=data["advisory_level"],
                    advisory_text=data["advisory_text"],
                    last_updated=data.get("last_updated"),
                    url=UPSTREAM_URL,
                )
            self._source = "fallback"
        logger.info("Loaded %d advisories from fallback dataset", len(self._cache))

    def refresh_from_source(self) -> bool:
        """Attempt to refresh advisories from travel.state.gov.

        Returns True on a successful live fetch, False otherwise. On
        failure the curated fallback dataset remains in effect.
        """
        if not self._fetcher:
            return False

        live = self._fetcher.fetch()
        if not live:
            return False

        with self._lock:
            self._cache.clear()
            for country, data in live.items():
                # Build a TravelAdvisory; level was already validated in parser
                self._cache[country.lower()] = TravelAdvisory(
                    country=country,
                    advisory_level=data["advisory_level"],
                    advisory_text=data["advisory_text"],
                    last_updated=data.get("last_updated"),
                    url=data.get("url") or UPSTREAM_URL,
                )
            self._source = "live"
        logger.info("Refreshed %d advisories from live source", len(self._cache))
        return True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_advisory(self, country: str) -> Optional[TravelAdvisory]:
        if not country:
            return None
        return self._cache.get(country.strip().lower())

    def list_countries(self) -> List[str]:
        return sorted(adv.country for adv in self._cache.values())

    def list_all(self) -> List[TravelAdvisory]:
        return sorted(self._cache.values(), key=lambda a: a.country)

    def source(self) -> str:
        """Return 'live' or 'fallback' to indicate which dataset is active."""
        return self._source

    def cache_age_seconds(self) -> Optional[float]:
        if self._fetcher:
            return self._fetcher.cache_age_seconds()
        return None
