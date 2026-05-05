"""
Live scraper for travel.state.gov travel-advisory listings.

The State Department publishes its Travel Advisories as an HTML table on
the page below. Each row contains a country link, a level string, a
risk-indicator string, and a date. We parse that table on demand and
cache the result in memory.

This module is intentionally defensive:
  * Network failures, parse errors, and unexpected HTML structures all
    fall through to None so that callers can transparently use the
    curated fallback dataset.
  * A short cache prevents excessive upstream requests if many users
    hit the app in a burst.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime
from typing import Dict, Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

UPSTREAM_URL = (
    "https://travel.state.gov/en/international-travel/travel-advisories.html"
)
USER_AGENT = (
    "Mozilla/5.0 (compatible; WorldTravelAdvisoryBot/1.0; "
    "Educational project; +https://github.com/group2/travel-advisory)"
)

# Map the level prefix string to the integer level
_LEVEL_RE = re.compile(r"Level\s*([1-4])", re.IGNORECASE)


class LiveAdvisoryFetcher:
    """Fetches and parses the live State Department advisory list.

    Results are cached for ``cache_ttl_seconds`` to keep upstream load low.
    The class is thread-safe.
    """

    def __init__(
        self,
        timeout: float = 10.0,
        cache_ttl_seconds: int = 60 * 60,  # one hour
    ):
        self.timeout = timeout
        self.cache_ttl = cache_ttl_seconds
        self._cache: Dict[str, dict] = {}
        self._cache_at: float = 0.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch(self) -> Optional[Dict[str, dict]]:
        """Return a fresh dict of advisories, using cache if still warm.

        On any failure (network, HTTP error, parse error) returns ``None``
        so callers can fall back to a curated dataset.
        """
        with self._lock:
            now = time.time()
            if self._cache and (now - self._cache_at) < self.cache_ttl:
                logger.debug("Returning cached live advisories (%d)", len(self._cache))
                return self._cache

        try:
            html = self._download()
        except Exception as e:  # noqa: BLE001
            logger.warning("Live fetch failed: %s", e)
            return None

        try:
            parsed = self._parse(html)
        except Exception as e:  # noqa: BLE001
            logger.warning("Parse failed: %s", e)
            return None

        if not parsed:
            logger.warning("Parser produced no rows; treating as failure")
            return None

        with self._lock:
            self._cache = parsed
            self._cache_at = time.time()

        logger.info("Refreshed live advisories: %d countries", len(parsed))
        return parsed

    def is_cache_valid(self) -> bool:
        with self._lock:
            return bool(self._cache) and (
                time.time() - self._cache_at < self.cache_ttl
            )

    def cache_age_seconds(self) -> Optional[float]:
        with self._lock:
            if not self._cache:
                return None
            return time.time() - self._cache_at

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _download(self) -> str:
        headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            resp = client.get(UPSTREAM_URL, headers=headers)
            resp.raise_for_status()
            return resp.text

    def _parse(self, html: str) -> Dict[str, dict]:
        """Parse the advisories table from the HTML.

        Expected structure:
        <table>
          <thead><tr><th>Destination</th><th>Level</th>
                     <th>Risk Indicators</th><th>Date Issued</th></tr></thead>
          <tbody>
            <tr><td><a href="...">Country</a></td>
                <td>Level X: Description</td>
                <td>RISK_TOKENS</td>
                <td>MM/DD/YYYY</td></tr>
            ...
          </tbody>
        </table>
        """
        soup = BeautifulSoup(html, "html.parser")

        # Locate the right table by the header signature.
        target_table = None
        for table in soup.find_all("table"):
            header_row = table.find("tr")
            if not header_row:
                continue
            headers = [h.get_text(strip=True).lower()
                       for h in header_row.find_all(["th", "td"])]
            if {"destination", "level"}.issubset(set(headers)):
                target_table = table
                break

        if target_table is None:
            return {}

        results: Dict[str, dict] = {}
        for row in target_table.find_all("tr")[1:]:  # skip header
            cells = row.find_all(["td", "th"])
            if len(cells) < 4:
                continue

            # Destination
            country = cells[0].get_text(strip=True)
            if not country:
                continue

            # Level
            level_text = cells[1].get_text(strip=True)
            m = _LEVEL_RE.search(level_text)
            if not m:
                continue
            level = int(m.group(1))

            # Risk indicators
            risk_text = cells[2].get_text(" ", strip=True)

            # Date issued
            date_text = cells[3].get_text(strip=True)
            iso_date = self._normalize_date(date_text)

            # Detail URL (optional)
            link = cells[0].find("a", href=True)
            url = link["href"] if link else None
            if url and url.startswith("/"):
                url = "https://travel.state.gov" + url

            results[country] = {
                "advisory_level": level,
                "advisory_text": level_text,
                "risk_indicators": risk_text,
                "last_updated": iso_date,
                "url": url,
            }

        return results

    @staticmethod
    def _normalize_date(date_text: str) -> Optional[str]:
        """Convert MM/DD/YYYY to ISO YYYY-MM-DD if possible."""
        if not date_text:
            return None
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%B %d, %Y"):
            try:
                return datetime.strptime(date_text.strip(), fmt).date().isoformat()
            except ValueError:
                continue
        return date_text  # leave as-is if parsing fails
