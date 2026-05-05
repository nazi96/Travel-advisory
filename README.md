# World Travel Advisory

A cloud-deployed Flask web application that aggregates U.S. State Department
travel advisories with real-time weather data and curated points of interest.

**Project Group 2** — Final Project
**Members:** Nazanin Amini · Lorie Blount · Michael Hawkins

## Features

- Location-based travel advisories (Levels 1–4) from travel.state.gov
- Real-time weather via Open-Meteo (no API key required)
- Curated attraction and lodging recommendations
- Clean, responsive web UI (mobile-friendly)
- REST API for programmatic access
- Containerized for Google Cloud Run

## Quick Start (Local)

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate           # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
python main.py
# Visit http://localhost:8080
```

## Run with Docker

```bash
docker build -t travel-advisory .
docker run -p 8080:8080 travel-advisory
```

## Run Tests

```bash
pip install pytest pytest-cov
pytest tests/ -v --cov=app
```

## Deploy to Google Cloud Run

```bash
# Authenticate (one-time)
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Submit Cloud Build (builds + pushes + deploys)
gcloud builds submit --config=cloudbuild.yaml
```

## REST API

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check |
| `GET /api/countries` | List supported countries |
| `GET /api/advisory/<country>` | Travel advisory |
| `GET /api/weather/<country>` | Current weather |
| `GET /api/report/<country>` | Aggregated report |

## Project Structure

```
travel_advisory/
├── app/
│   ├── __init__.py        # Flask factory
│   ├── routes.py          # Web + API endpoints
│   ├── models.py          # Pydantic models
│   ├── services/          # Advisory, Weather, Places services
│   ├── templates/         # Jinja2 templates
│   └── static/            # CSS / JS
├── tests/                 # pytest suite
├── .github/workflows/     # CI/CD pipeline
├── Dockerfile             # Cloud Run container
├── cloudbuild.yaml        # Cloud Build pipeline
├── app.yaml               # App Engine config
├── requirements.txt
└── main.py                # Entry point
```
