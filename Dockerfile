FROM python:3.11-slim

WORKDIR /app

# System deps for mplfinance (matplotlib), postgres, and general build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev libfreetype6-dev libpng-dev zlib1g-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps from requirements.txt (no build step needed)
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --pre -r /app/requirements.txt

# Copy application code
COPY backend/ /app/backend/
COPY config/ /app/config/
COPY CLAUDE.md /app/CLAUDE.md

WORKDIR /app/backend

# Create data directory for working memory persistence
RUN mkdir -p /app/data

EXPOSE 8000

# Use shell form so $PORT env var is expanded (Railway sets PORT dynamically)
CMD uvicorn src.dashboard.app:app --host 0.0.0.0 --port ${PORT:-8000}
