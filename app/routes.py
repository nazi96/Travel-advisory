"""
Flask routes: server-rendered pages and a REST API.

The application attempts to refresh advisories from the live State
Department source on startup. If that fails, the curated fallback
dataset (~215 countries) is used. A manual refresh endpoint lets
operators trigger a re-fetch on demand.
"""
import logging
import threading

from flask import Blueprint, render_template, request, jsonify
from app.services import AdvisoryService, WeatherService, PlacesService
from app.models import DestinationReport

logger = logging.getLogger(__name__)

# Service singletons
advisory_service = AdvisoryService()
weather_service = WeatherService()
places_service = PlacesService()

# Best-effort live refresh in the background so the first page load is fast.


def _background_refresh():
    try:
        ok = advisory_service.refresh_from_source()
        logger.info("Startup live refresh: %s", "ok" if ok else "fell back")
    except Exception as e:  # noqa: BLE001
        logger.warning("Startup refresh raised: %s", e)


threading.Thread(target=_background_refresh, daemon=True).start()


main_bp = Blueprint("main", __name__)
api_bp = Blueprint("api", __name__)


# ---------- Web pages ----------

@main_bp.route("/")
def home():
    """Landing page."""
    countries = advisory_service.list_countries()
    return render_template(
        "index.html",
        countries=countries,
        source=advisory_service.source(),
    )


@main_bp.route("/advisory")
def advisory_page():
    """Display the destination report for ?country=..."""
    country = request.args.get("country", "").strip()
    if not country:
        return render_template(
            "result.html",
            error="Please select a country.",
            countries=advisory_service.list_countries(),
        )

    advisory = advisory_service.get_advisory(country)
    if not advisory:
        return render_template(
            "result.html",
            error=f"No advisory data available for '{country}'.",
            countries=advisory_service.list_countries(),
        )

    weather = weather_service.get_weather(advisory.country)
    recommendations = places_service.get_recommendations(advisory.country)

    report = DestinationReport(
        country=advisory.country,
        advisory=advisory,
        weather=weather,
        recommendations=recommendations,
    )
    return render_template(
        "result.html",
        report=report,
        countries=advisory_service.list_countries(),
        source=advisory_service.source(),
    )


@main_bp.route("/all")
def all_advisories_page():
    """Display all advisories in a table."""
    advisories = advisory_service.list_all()
    return render_template(
        "all.html",
        advisories=advisories,
        source=advisory_service.source(),
    )


@main_bp.route("/about")
def about_page():
    return render_template("about.html")


# ---------- REST API ----------

@api_bp.route("/health")
def health():
    """Liveness probe used by Cloud Run."""
    return jsonify({
        "status": "ok",
        "advisory_source": advisory_service.source(),
        "country_count": len(advisory_service.list_countries()),
    }), 200


@api_bp.route("/countries")
def api_countries():
    """List all supported countries."""
    return jsonify({
        "countries": advisory_service.list_countries(),
        "count": len(advisory_service.list_countries()),
        "source": advisory_service.source(),
    })


@api_bp.route("/advisory/<country>")
def api_advisory(country):
    advisory = advisory_service.get_advisory(country)
    if not advisory:
        return jsonify({"error": f"No advisory found for '{country}'"}), 404
    return jsonify(advisory.model_dump())


@api_bp.route("/weather/<country>")
def api_weather(country):
    advisory = advisory_service.get_advisory(country)
    if not advisory:
        return jsonify({"error": f"Unknown country '{country}'"}), 404
    weather = weather_service.get_weather(advisory.country)
    if not weather:
        return jsonify({"error": "Weather unavailable"}), 503
    return jsonify(weather.model_dump(mode="json"))


@api_bp.route("/report/<country>")
def api_report(country):
    """Aggregate destination report."""
    advisory = advisory_service.get_advisory(country)
    if not advisory:
        return jsonify({"error": f"Unknown country '{country}'"}), 404
    report = DestinationReport(
        country=advisory.country,
        advisory=advisory,
        weather=weather_service.get_weather(advisory.country),
        recommendations=places_service.get_recommendations(advisory.country),
    )
    return jsonify(report.model_dump(mode="json"))


@api_bp.route("/refresh", methods=["POST"])
def api_refresh():
    """Manually trigger a live refresh from travel.state.gov.

    Returns 200 with the new source on success, 503 when the live
    fetch failed and the fallback dataset is still in use.
    """
    ok = advisory_service.refresh_from_source()
    payload = {
        "ok": ok,
        "source": advisory_service.source(),
        "country_count": len(advisory_service.list_countries()),
    }
    return jsonify(payload), 200 if ok else 503


@main_bp.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404
