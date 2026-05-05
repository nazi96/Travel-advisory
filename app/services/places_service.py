"""
Places / recommendations service.

Combines two sources to give every supported country a non-empty
recommendation list:

  1. **Curated catalog** of high-quality entries for 15 popular destinations,
     hand-picked for the demo. Always available, fastest to render.

  2. **Live Wikipedia integration** (LivePlacesFetcher) used for the other
     200 countries. Results are cached per-country for 24 hours.

If a country has neither curated entries nor a successful Wikipedia
response, the service returns an empty list and the UI shows a
graceful "no recommendations available" message.
"""
from __future__ import annotations

import logging
from typing import Dict, List

from app.models import PlaceRecommendation
from app.services.live_places_fetcher import LivePlacesFetcher

logger = logging.getLogger(__name__)


# Curated catalog of high-quality recommendations for popular demo countries.
CURATED_PLACES: Dict[str, List[Dict]] = {
    "France": [
        {"name": "Eiffel Tower", "category": "attraction", "rating": 4.6,
         "address": "Champ de Mars, Paris",
         "description": "Iconic 330m wrought-iron tower."},
        {"name": "Louvre Museum", "category": "attraction", "rating": 4.7,
         "address": "Rue de Rivoli, Paris",
         "description": "World's largest art museum."},
        {"name": "Hotel de Crillon", "category": "lodging", "rating": 4.8,
         "address": "10 Pl. de la Concorde, Paris",
         "description": "Historic luxury hotel."},
    ],
    "Japan": [
        {"name": "Senso-ji Temple", "category": "attraction", "rating": 4.5,
         "address": "Asakusa, Tokyo",
         "description": "Tokyo's oldest Buddhist temple."},
        {"name": "Tokyo Skytree", "category": "attraction", "rating": 4.4,
         "address": "Sumida, Tokyo", "description": "634m broadcasting tower."},
        {"name": "Park Hyatt Tokyo", "category": "lodging", "rating": 4.7,
         "address": "Shinjuku, Tokyo",
         "description": "Iconic luxury hotel."},
    ],
    "Mexico": [
        {"name": "Chichen Itza", "category": "attraction", "rating": 4.7,
         "address": "Yucatan", "description": "Ancient Mayan city."},
        {"name": "Frida Kahlo Museum", "category": "attraction", "rating": 4.5,
         "address": "Coyoacan, Mexico City",
         "description": "Casa Azul, the artist's home."},
    ],
    "Italy": [
        {"name": "Colosseum", "category": "attraction", "rating": 4.7,
         "address": "Piazza del Colosseo, Rome",
         "description": "Ancient Roman amphitheater."},
        {"name": "Vatican Museums", "category": "attraction", "rating": 4.7,
         "address": "Vatican City",
         "description": "Sistine Chapel and Renaissance art."},
    ],
    "United Kingdom": [
        {"name": "British Museum", "category": "attraction", "rating": 4.7,
         "address": "Great Russell St, London",
         "description": "Vast collection of world history."},
        {"name": "Tower of London", "category": "attraction", "rating": 4.6,
         "address": "London", "description": "Historic castle on the Thames."},
    ],
    "Germany": [
        {"name": "Brandenburg Gate", "category": "attraction", "rating": 4.7,
         "address": "Pariser Platz, Berlin",
         "description": "18th-century neoclassical monument."},
    ],
    "Spain": [
        {"name": "Sagrada Familia", "category": "attraction", "rating": 4.7,
         "address": "Barcelona",
         "description": "Gaudi's unfinished basilica."},
        {"name": "Prado Museum", "category": "attraction", "rating": 4.7,
         "address": "Madrid", "description": "National Spanish art museum."},
    ],
    "Australia": [
        {"name": "Sydney Opera House", "category": "attraction", "rating": 4.7,
         "address": "Sydney", "description": "Iconic performing arts center."},
    ],
    "Brazil": [
        {"name": "Christ the Redeemer", "category": "attraction", "rating": 4.8,
         "address": "Rio de Janeiro",
         "description": "Art Deco statue atop Corcovado."},
    ],
    "Canada": [
        {"name": "Niagara Falls", "category": "attraction", "rating": 4.7,
         "address": "Ontario", "description": "Massive waterfalls on the border."},
    ],
    "Thailand": [
        {"name": "Grand Palace", "category": "attraction", "rating": 4.6,
         "address": "Bangkok",
         "description": "Royal palace complex since 1782."},
    ],
    "India": [
        {"name": "Taj Mahal", "category": "attraction", "rating": 4.8,
         "address": "Agra", "description": "Iconic white marble mausoleum."},
    ],
    "Egypt": [
        {"name": "Pyramids of Giza", "category": "attraction", "rating": 4.7,
         "address": "Giza", "description": "Ancient wonders of the world."},
    ],
    "South Africa": [
        {"name": "Table Mountain", "category": "attraction", "rating": 4.7,
         "address": "Cape Town",
         "description": "Flat-topped landmark over the city."},
    ],
    "Ukraine": [
        {"name": "St. Sophia's Cathedral", "category": "attraction",
         "rating": 4.7, "address": "Kyiv",
         "description": "UNESCO World Heritage site."},
    ],
}


class PlacesService:
    """Returns curated + live recommendations by country."""

    def __init__(self, enable_live: bool = True, timeout: float = 8.0):
        self.enable_live = enable_live
        self._fetcher = LivePlacesFetcher(timeout=timeout) if enable_live else None

    def get_recommendations(self, country: str) -> List[PlaceRecommendation]:
        """Return recommendations for a country.

        For curated countries: return the curated entries (instant).
        For all other countries: try the live Wikipedia source, with an
        empty list as the final fallback.
        """
        # 1. Curated catalog wins when available — fastest and highest quality.
        curated = CURATED_PLACES.get(country)
        if curated:
            return [PlaceRecommendation(**item) for item in curated]

        # 2. Live Wikipedia integration for the long tail of countries.
        if self._fetcher:
            live = self._fetcher.get_places(country)
            if live:
                return live

        # 3. Empty fallback — UI shows a friendly "no recommendations" message.
        return []

    def source_for(self, country: str) -> str:
        """Return 'curated', 'live', or 'none' for diagnostic display."""
        if country in CURATED_PLACES:
            return "curated"
        if self._fetcher:
            cached = self._fetcher._cache_get(country)
            if cached:
                return "live"
        return "none"
