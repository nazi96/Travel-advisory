# Production container for Cloud Run deployment
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Cloud Run injects PORT (default 8080)
ENV PORT=8080
EXPOSE 8080

# Run with Gunicorn for production
CMD exec gunicorn --bind :$PORT --workers 2 --threads 4 --timeout 60 main:app
