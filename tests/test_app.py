"""Unit and integration tests for the World Travel Advisory app."""
from unittest.mock import patch
import pytest

from app import create_app
from app.services import AdvisoryService, PlacesService
from app.services.live_advisory_fetcher import LiveAdvisoryFetcher
from app.models import TravelAdvisory


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ====================================================================
# Service tests — Advisory
# ====================================================================

def test_advisory_service_loads_full_fallback():
    """Fallback dataset should cover every continent (~215 destinations)."""
    svc = AdvisoryService(enable_live=False)
    countries = svc.list_countries()
    assert len(countries) >= 200
    # Sanity-check a few across continents
    for must_have in ["France", "Japan", "Brazil", "Kenya", "Australia",
                      "Iceland", "Vietnam"]:
        assert must_have in countries, f"Missing {must_have}"


def test_advisory_service_returns_known_country():
    svc = AdvisoryService(enable_live=False)
    advisory = svc.get_advisory("France")
    assert advisory is not None
    assert advisory.country == "France"
    assert 1 <= advisory.advisory_level <= 4


def test_advisory_service_case_insensitive():
    svc = AdvisoryService(enable_live=False)
    assert svc.get_advisory("japan") is not None
    assert svc.get_advisory("JAPAN") is not None
    assert svc.get_advisory("  japan  ") is not None


def test_advisory_service_unknown_country():
    svc = AdvisoryService(enable_live=False)
    assert svc.get_advisory("Atlantis") is None


def test_advisory_list_countries_sorted():
    svc = AdvisoryService(enable_live=False)
    countries = svc.list_countries()
    assert countries == sorted(countries)
    assert "France" in countries


def test_advisory_source_starts_as_fallback():
    svc = AdvisoryService(enable_live=False)
    assert svc.source() == "fallback"


def test_every_country_has_coords():
    """Every advisory country must have weather coordinates."""
    from app.data.country_coords import COUNTRY_COORDS
    svc = AdvisoryService(enable_live=False)
    missing = [c for c in svc.list_countries() if c not in COUNTRY_COORDS]
    assert not missing, f"Countries without coords: {missing}"


def test_advisory_level_label():
    adv = TravelAdvisory(country="Test", advisory_level=4, advisory_text="x")
    assert "Do Not Travel" in adv.level_label


def test_advisory_level_color_distinct_per_level():
    adv1 = TravelAdvisory(country="A", advisory_level=1, advisory_text="x")
    adv4 = TravelAdvisory(country="B", advisory_level=4, advisory_text="x")
    assert adv1.level_color != adv4.level_color


# ====================================================================
# Service tests — Places
# ====================================================================

def test_places_service_returns_recommendations():
    svc = PlacesService(enable_live=False)
    recs = svc.get_recommendations("Japan")
    assert len(recs) > 0
    assert all(r.category in {"attraction", "lodging", "restaurant"} for r in recs)


def test_places_service_unknown_country_no_live_returns_empty():
    """With live disabled, an uncurated country returns []."""
    svc = PlacesService(enable_live=False)
    assert svc.get_recommendations("Atlantis") == []


def test_places_service_uses_live_for_uncurated_country():
    """For countries not in the curated catalog, the live fetcher is consulted."""
    from unittest.mock import patch
    from app.models import PlaceRecommendation as PR
    svc = PlacesService(enable_live=True)
    fake = [PR(name="Foo Falls", category="attraction", description="A waterfall.")]
    with patch.object(svc._fetcher, "get_places", return_value=fake):
        recs = svc.get_recommendations("Uzbekistan")
    assert len(recs) == 1
    assert recs[0].name == "Foo Falls"


def test_places_service_curated_takes_precedence_over_live():
    """Curated entries should return immediately without consulting live."""
    from unittest.mock import patch
    svc = PlacesService(enable_live=True)
    with patch.object(svc._fetcher, "get_places") as mock_live:
        recs = svc.get_recommendations("France")
    assert len(recs) > 0
    mock_live.assert_not_called()  # curated path skipped the live fetcher


def test_places_service_source_indicator():
    svc = PlacesService(enable_live=False)
    assert svc.source_for("France") == "curated"
    assert svc.source_for("Atlantis") == "none"


def test_live_places_fetcher_handles_network_error():
    from app.services.live_places_fetcher import LivePlacesFetcher
    from unittest.mock import patch
    fetcher = LivePlacesFetcher(timeout=1.0)
    with patch.object(fetcher, "_fetch_for_country", side_effect=Exception("boom")):
        result = fetcher.get_places("Wonderland")
    assert result == []  # graceful failure


# ====================================================================
# Live scraper tests
# ====================================================================

SAMPLE_HTML = """
<html><body>
<table>
  <tr><th>Destination</th><th>Level</th><th>Risk Indicators</th><th>Date Issued</th></tr>
  <tr>
    <td><a href="/foo/france.html">France</a></td>
    <td>Level 2: Exercise increased caution</td>
    <td>UNREST (U) TERRORISM (T)</td>
    <td>05/28/2025</td>
  </tr>
  <tr>
    <td><a href="/foo/japan.html">Japan</a></td>
    <td>Level 1: Exercise normal precautions</td>
    <td></td>
    <td>05/15/2025</td>
  </tr>
</table>
</body></html>
"""


def test_live_fetcher_parses_well_formed_html():
    fetcher = LiveAdvisoryFetcher()
    parsed = fetcher._parse(SAMPLE_HTML)
    assert "France" in parsed
    assert parsed["France"]["advisory_level"] == 2
    assert parsed["Japan"]["advisory_level"] == 1
    assert parsed["France"]["last_updated"] == "2025-05-28"


def test_live_fetcher_handles_garbage():
    fetcher = LiveAdvisoryFetcher()
    assert fetcher._parse("<html>not a table</html>") == {}
    assert fetcher._parse("") == {}


def test_live_fetcher_returns_none_on_network_error():
    fetcher = LiveAdvisoryFetcher(timeout=0.001)
    # Patch the download to raise; full-network failure is gracefully handled
    with patch.object(fetcher, "_download", side_effect=Exception("boom")):
        assert fetcher.fetch() is None


def test_advisory_service_falls_back_when_live_fails():
    """If the live fetcher raises, the service stays on fallback data."""
    svc = AdvisoryService(enable_live=True)
    with patch.object(svc._fetcher, "fetch", return_value=None):
        ok = svc.refresh_from_source()
    assert ok is False
    assert svc.source() == "fallback"
    # Service is still usable
    assert svc.get_advisory("France") is not None


def test_advisory_service_uses_live_when_available():
    svc = AdvisoryService(enable_live=True)
    fake_live = {
        "France": {
            "advisory_level": 3,
            "advisory_text": "Level 3: Reconsider travel",
            "last_updated": "2026-05-01",
            "url": "https://travel.state.gov/foo",
        }
    }
    with patch.object(svc._fetcher, "fetch", return_value=fake_live):
        ok = svc.refresh_from_source()
    assert ok is True
    assert svc.source() == "live"
    advisory = svc.get_advisory("France")
    assert advisory is not None
    assert advisory.advisory_level == 3
    # Other countries dropped because live fetch only contained France
    assert svc.get_advisory("Japan") is None


# ====================================================================
# Route tests
# ====================================================================

def test_home_route(client):
    rv = client.get("/")
    assert rv.status_code == 200
    assert b"World Travel Advisory" in rv.data


def test_health_endpoint(client):
    rv = client.get("/api/health")
    assert rv.status_code == 200
    payload = rv.get_json()
    assert payload["status"] == "ok"
    assert payload["country_count"] >= 200
    assert payload["advisory_source"] in {"live", "fallback"}


def test_api_countries(client):
    rv = client.get("/api/countries")
    assert rv.status_code == 200
    data = rv.get_json()
    assert "countries" in data
    assert data["count"] == len(data["countries"])
    assert data["count"] >= 200


def test_api_advisory_known(client):
    rv = client.get("/api/advisory/France")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["country"] == "France"


def test_api_advisory_unknown(client):
    rv = client.get("/api/advisory/Atlantis")
    assert rv.status_code == 404


def test_api_report_includes_recommendations(client):
    rv = client.get("/api/report/Japan")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["country"] == "Japan"
    assert "recommendations" in data


def test_advisory_page_with_country(client):
    rv = client.get("/advisory?country=France")
    assert rv.status_code == 200
    assert b"France" in rv.data


def test_advisory_page_missing_country(client):
    rv = client.get("/advisory")
    assert rv.status_code == 200
    assert b"Please select" in rv.data


def test_all_advisories_page(client):
    rv = client.get("/all")
    assert rv.status_code == 200
    assert b"All Travel Advisories" in rv.data


def test_security_headers_set(client):
    rv = client.get("/")
    assert rv.headers.get("X-Content-Type-Options") == "nosniff"
    assert rv.headers.get("X-Frame-Options") == "DENY"
