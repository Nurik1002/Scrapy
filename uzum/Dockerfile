FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright and Postgres
RUN apt-get update && apt-get install -y \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps chromium

COPY . .

CMD ["scrapy", "crawl", "uzum"]
