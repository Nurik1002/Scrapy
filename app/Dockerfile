FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (including Playwright deps)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install Playwright browsers (for UZEX session)
RUN playwright install chromium --with-deps || true

# Copy source code
COPY . .

# Set Python path
ENV PYTHONPATH=/app

# Default command (overridden by docker-compose)
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

