# ============================================
# Base Stage - Common dependencies
# ============================================
FROM python:3.11-slim as base

WORKDIR /app

# Install common dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install base packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY config.py .
COPY crawlers/ crawlers/
COPY downloaders/ downloaders/
COPY processors/ processors/
COPY queue/ queue/
COPY api/ api/

# ============================================
# Crawler Stage - Playwright for link discovery
# ============================================
FROM base as crawler

# Install Playwright dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright and browsers
RUN pip install playwright && playwright install chromium

# ============================================
# Downloader Stage - aiohttp for API calls
# ============================================
FROM base as downloader

# Nothing extra needed, aiohttp is in requirements.txt

# ============================================
# Processor Stage - Offline processing
# ============================================
FROM base as processor

# Nothing extra needed

# ============================================
# API Stage - FastAPI
# ============================================
FROM base as api

EXPOSE 8000
