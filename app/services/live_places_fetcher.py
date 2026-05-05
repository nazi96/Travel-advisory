"""
Live places fetcher using Wikipedia's MediaWiki REST API.

Strategy:
  1. For a given country, query Wikipedia for "Tourism in <country>" or
     "<country>" pages.
  2. Extract candidate place names from the article's link structure
     (filtering down to plausible attractions using heuristics).
  3. Fetch a short description for each candidate via the page-summary
     endpoint.
  4. Cache results per country for 24 hours.

This module is intentionally defensive: any error path returns an empty
list so the AdvisoryService can fall back to the curated catalog or to a
graceful "no recommendations available" message.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from typing import Dict, List, Optional, Tuple

import httpx

from app.models import PlaceRecommendation

logger = logging.getLogger(__name__)

WIKI_API_URL = "https://en.wikipedia.org/w/api.php"
WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/"
USER_AGENT = (
    "WorldTravelAdvisoryBot/1.0 (Educational project; "
    "+https://github.com/group2/travel-advisory)"
)

# Words that disqualify a candidate as an attraction
_BLOCKLIST_TOKENS = {
    "list of", "history of", "geography of", "economy of", "politics of",
    "demographics of", "culture of", "religion in", "education in",
    "transport in", "languages of", "music of", "cuisine of",
    "outline of", "index of", "wikipedia", "category:",
}

# Tokens likely to indicate an attraction or tourism-relevant entity
_GOOD_TOKENS = (
    "park", "museum", "temple", "cathedral", "church", "mosque",
    "palace", "castle", "fortress", "monument", "tower", "lake",
    "mountain", "beach", "island", "valley", "falls", "ruins",
    "national park", "world heritage", "historic", "tomb", "shrine",
    "garden", "square", "basilica", "abbey", "memorial", "bridge",
    "harbor", "harbour", "old city", "old town",
)


class LivePlacesFetcher:
    """Fetches tourism recommendations per country via Wikipedia."""

    def __init__(
        self,
        timeout: float = 8.0,
        cache_ttl_seconds: int = 24 * 60 * 60,  # 24 hours
        max_per_country: int = 5,
    ):
        self.timeout = timeout
        self.cache_ttl = cache_ttl_seconds
        self.max_per_country = max_per_country
        self._cache: Dict[str, Tuple[float, List[PlaceRecommendation]]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_places(self, country: str) -> List[PlaceRecommendation]:
        """Return up to ``max_per_country`` attractions for the country.

        On any failure (network, parse, no results) returns an empty list
        so callers can fall back gracefully.
        """
        cached = self._cache_get(country)
        if cached is not None:
            return cached

        try:
            places = self._fetch_for_country(country)
        except Exception as e:  # noqa: BLE001
            logger.warning("Live places fetch failed for %s: %s", country, e)
            places = []

        self._cache_put(country, places)
        return places

    def cache_size(self) -> int:
        with self._lock:
            return len(self._cache)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _cache_get(self, country: str) -> Optional[List[PlaceRecommendation]]:
        with self._lock:
            entry = self._cache.get(country)
            if entry is None:
                return None
            ts, value = entry
            if (time.time() - ts) >= self.cache_ttl:
                del self._cache[country]
                return None
            return value

    def _cache_put(self, country: str, value: List[PlaceRecommendation]) -> None:
        with self._lock:
            self._cache[country] = (time.time(), value)

    def _fetch_for_country(self, country: str) -> List[PlaceRecommendation]:
        """Fetch attraction candidates for one country."""
        candidates = self._candidate_titles(country)
        if not candidates:
            return []

        # Limit candidates to the top N to keep API usage bounded.
        candidates = candidates[: self.max_per_country * 2]

        results: List[PlaceRecommendation] = []
        for title in candidates:
            if len(results) >= self.max_per_country:
                break
            summary = self._fetch_summary(title)
            if not summary:
                continue
            results.append(
                PlaceRecommendation(
                    name=summary["title"],
                    category="attraction",
                    rating=None,
                    address=country,
                    description=summary["extract"],
                )
            )
        return results

    def _candidate_titles(self, country: str) -> List[str]:
        """Return candidate attraction page titles for a country.

        Strategy: query the "Tourism in <country>" page for outbound
        wikilinks, filter, and return the most likely ones first.
        """
        seed_title = f"Tourism in {country}"
        params = {
            "action": "query",
            "format": "json",
            "titles": seed_title,
            "prop": "links",
            "pllimit": "max",
            "plnamespace": "0",  # main namespace only
        }
        headers = {"User-Agent": USER_AGENT}

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(WIKI_API_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return []

        # First (and only) page returned
        page = next(iter(pages.values()))
        if "missing" in page:
            # No "Tourism in X" article. Fall back to the country article.
            return self._candidate_titles_from_country_page(country)

        links = page.get("links", [])
        titles = [link.get("title", "") for link in links if link.get("title")]
        return self._rank_candidates(titles, country)

    def _candidate_titles_from_country_page(self, country: str) -> List[str]:
        """Fallback: pull links from the country's main Wikipedia page."""
        params = {
            "action": "query",
            "format": "json",
            "titles": country,
            "prop": "links",
            "pllimit": "max",
            "plnamespace": "0",
        }
        headers = {"User-Agent": USER_AGENT}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(WIKI_API_URL, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception:  # noqa: BLE001
            return []

        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return []
        page = next(iter(pages.values()))
        links = page.get("links", [])
        titles = [link.get("title", "") for link in links if link.get("title")]
        return self._rank_candidates(titles, country)

    def _rank_candidates(self, titles: List[str], country: str) -> List[str]:
        """Heuristically rank candidate titles for attraction-likelihood."""
        good: List[str] = []
        country_lc = country.lower()
        for title in titles:
            tlc = title.lower()
            # Skip blocklisted titles
            if any(tok in tlc for tok in _BLOCKLIST_TOKENS):
                continue
            # Skip the country's own name
            if tlc == country_lc:
                continue
            # Score: titles containing tourism-relevant tokens go first
            if any(tok in tlc for tok in _GOOD_TOKENS):
                good.insert(0, title)
            else:
                good.append(title)
        return good

    def _fetch_summary(self, title: str) -> Optional[Dict]:
        """Fetch the short summary for a Wikipedia page title.

        Returns a dict with 'title' and 'extract' keys, or None.
        """
        url = WIKI_SUMMARY_URL + httpx.URL("/" + title).path.lstrip("/")
        # Encode title for URL safely:
        safe_title = re.sub(r"\s+", "_", title.strip())
        url = WIKI_SUMMARY_URL + safe_title
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=headers, follow_redirects=True)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                data = resp.json()
        except Exception:  # noqa: BLE001
            return None

        # Skip disambiguation pages and items that aren't proper attractions
        if data.get("type") == "disambiguation":
            return None
        extract = data.get("extract", "").strip()
        if not extract or len(extract) < 30:
            return None
        # Truncate the extract to a sensible length for the UI
        if len(extract) > 240:
            # Cut at the nearest sentence boundary
            cut = extract[:240].rsplit(". ", 1)
            extract = cut[0] + "." if len(cut) > 1 else extract[:240] + "..."
        return {
            "title": data.get("title", title),
            "extract": extract,
        }
