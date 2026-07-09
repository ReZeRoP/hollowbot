# syntax=docker/dockerfile:1
FROM python:3.12-slim

# System deps (needed by Pillow/qrcode and healthchecks)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libjpeg-dev zlib1g-dev curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt requirements-postgres.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install -r requirements-postgres.txt   # Docker has gcc, so this always builds/installs cleanly

COPY . .

# Ensure data/backups dirs exist for SQLite + backups
RUN mkdir -p /app/data /app/backups

# Run migrations then start the bot
CMD ["sh", "-c", "alembic upgrade head && python bot.py"]
