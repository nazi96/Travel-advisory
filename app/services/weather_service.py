"""
Weather service.

Uses Open-Meteo (free, no API key required). All ~215 supported
destinations are mapped to the coordinates of their capital city in
``app.data.country_coords``. Failures (network, unknown country)
return ``None`` so the rest of the destination report still renders.
"""
import logging
from typing import Optional

import httpx

from app.data.country_coords import COUNTRY_COORDS
from app.models import WeatherInfo

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Open-Meteo weather code -> human description
WEATHER_CODE_MAP = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Moderate showers",
    82: "Violent showers",
    95: "Thunderstorm",
    96: "Thunderstorm w/ slight hail",
    99: "Thunderstorm w/ heavy hail",
}


class WeatherService:
    """Fetches current weather using Open-Meteo."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def get_weather(self, country: str) -> Optional[WeatherInfo]:
        """Return current weather for a country's capital city."""
        coords = COUNTRY_COORDS.get(country)
        if not coords:
            logger.warning("No coordinates configured for %s", country)
            return None
        lat, lon, city = coords
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": "true",
            "hourly": "relative_humidity_2m",
            "timezone": "auto",
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(OPEN_METEO_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:  # noqa: BLE001
            logger.error("Weather fetch failed for %s: %s", country, e)
            return None

        cw = data.get("current_weather", {})
        temp_c = float(cw.get("temperature", 0.0))
        temp_f = (temp_c * 9 / 5) + 32
        wind = float(cw.get("windspeed", 0.0))
        code = int(cw.get("weathercode", 0))
        description = WEATHER_CODE_MAP.get(code, "Unknown")

        humidity = 0
        try:
            humidity = int(data["hourly"]["relative_humidity_2m"][0])
        except (KeyError, IndexError, ValueError, TypeError):
            humidity = 0

        return WeatherInfo(
            location=f"{city}, {country}",
            temperature_c=round(temp_c, 1),
            temperature_f=round(temp_f, 1),
            description=description,
            humidity=humidity,
            wind_speed=wind,
        )
