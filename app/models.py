"""
Pydantic data models for type-safe data handling.
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class TravelAdvisory(BaseModel):
    """Represents a U.S. State Department travel advisory for a country."""
    country: str
    advisory_level: int = Field(..., ge=1, le=4)  # Levels 1-4
    advisory_text: str
    last_updated: Optional[str] = None
    url: Optional[str] = None

    @property
    def level_label(self) -> str:
        labels = {
            1: "Level 1: Exercise Normal Precautions",
            2: "Level 2: Exercise Increased Caution",
            3: "Level 3: Reconsider Travel",
            4: "Level 4: Do Not Travel",
        }
        return labels.get(self.advisory_level, "Unknown")

    @property
    def level_color(self) -> str:
        colors = {1: "#28a745", 2: "#ffc107", 3: "#fd7e14", 4: "#dc3545"}
        return colors.get(self.advisory_level, "#6c757d")


class WeatherInfo(BaseModel):
    """Current weather conditions for a location."""
    location: str
    temperature_c: float
    temperature_f: float
    description: str
    humidity: int
    wind_speed: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PlaceRecommendation(BaseModel):
    """Recommended place / point of interest."""
    name: str
    category: str  # attraction | lodging | restaurant
    rating: Optional[float] = None
    address: Optional[str] = None
    description: Optional[str] = None


class DestinationReport(BaseModel):
    """Aggregated destination report combining advisory + weather + places."""
    country: str
    advisory: Optional[TravelAdvisory] = None
    weather: Optional[WeatherInfo] = None
    recommendations: List[PlaceRecommendation] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
