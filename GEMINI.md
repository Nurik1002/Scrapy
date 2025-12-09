# GEMINI Code Companion Report

This document provides a comprehensive overview of the **Marketplace Analytics Platform** to assist Gemini in understanding the project's structure, purpose, and key components.

## 1. Project Overview

This project is a **SaaS analytics platform for marketplace sellers**. It is designed to be a high-performance, automated system for scraping marketplace data, processing it, and exposing it through a FastAPI-based API for analytics. The initial focus is on the `Uzum.uz` marketplace, with plans to expand to other platforms like Wildberries, Ozon, and Amazon.

### Core Features:
- **High-Speed Data Ingestion:** Utilizes direct API iteration instead of slower browser-based crawling.
- **Comprehensive Analytics:** Provides insights into price comparisons, price history, seller performance, and more.
- **Automated Operations:** Leverages Celery for scheduled, continuous data scraping and processing.
- **Multi-Platform Architecture:** Designed with a modular structure (`src/platforms`) to easily integrate new marketplaces.

### Key Technologies:
- **Backend:** Python
- **API Framework:** FastAPI
- **Database:** PostgreSQL
- **Task Queue:** Celery with Redis as the broker
- **Containerization:** Docker and Docker Compose
- **Core Libraries:** SQLAlchemy (for ORM), Pydantic (for data validation), aiohttp (for async HTTP requests).

## 2. Project Structure

The project is organized into several key directories:

```
/
├── app/                  # Main application source and configuration
│   ├── src/              # Core source code
│   │   ├── api/          # FastAPI application and API endpoints
│   │   ├── core/         # Shared components (DB, config, models)
│   │   ├── platforms/    # Marketplace-specific modules (e.g., uzum)
│   │   └── workers/      # Celery task definitions
│   ├── sql/              # SQL schema and initialization scripts
│   ├── migrations/       # Database migration scripts (Alembic)
│   ├── scripts/          # Helper and automation scripts
│   └── tests/            # Test suite
├── scrape_researches/    # Research and exploratory notebooks/scripts
└── ...
```

## 3. Building and Running the Project

The project is containerized using Docker and can be managed via `docker-compose` and a `Makefile`.

### Key Commands:
- **Start Core Infrastructure (DB & Redis):**
  ```bash
  docker-compose up -d postgres redis
  ```

- **Run the Full Application Stack (API, Workers):**
  ```bash
  docker-compose up -d --build
  ```

- **Install Local Dependencies:**
  ```bash
  pip install -r app/requirements.txt
  ```

- **Run Database Migrations:**
  ```bash
  # Inferred from alembic.ini and standard practice
  alembic upgrade head
  ```

- **Run Tests:**
  ```bash
  # TODO: Test command not explicitly defined, but likely involves pytest
  pytest app/tests/
  ```

## 4. Development Conventions

### Database Schema
- The database schema is located in `app/sql/001_uzum_schema.sql`.
- It is highly normalized and optimized for analytics, with tables for `sellers`, `categories`, `products`, `skus`, and `price_history`.
- It includes several PostgreSQL views (`v_price_comparison`, `v_best_deals`, etc.) to simplify common analytics queries.
- Database migrations appear to be managed with Alembic.

### API Structure
- The API is built with FastAPI and is located in `app/src/api/`.
- It follows a router-based structure, with endpoints organized into `products`, `sellers`, and `analytics`.
- Key endpoints include:
    - `GET /api/products`
    - `GET /api/sellers`
    - `GET /api/analytics/price-comparison`
    - `GET /api/stats`

### Asynchronous Operations
- The codebase makes extensive use of `asyncio`, from the FastAPI endpoints to the database access layer (`asyncpg`, `sqlalchemy[asyncio]`).
- Long-running and scheduled tasks are handled by a Celery worker and beat scheduler, respectively. This is crucial for the automated data scraping and processing pipeline.
