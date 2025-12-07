# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Marketplace Analytics Platform - SaaS analytics for marketplace sellers, starting with Uzum.uz (e-commerce) and UZEX (government procurement). Uses ID range API iteration instead of browser crawling (100x faster).

## Commands

### Infrastructure
```bash
# Start all services (PostgreSQL, Redis, API, Celery workers, Flower)
make up

# Start only database and cache
make infra
docker-compose up -d postgres redis

# Database shell
make db-shell

# Apply migrations
make migrate

# Show table row counts
make counts
```

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Start API server (FastAPI with hot reload)
make api
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
make test
pytest tests/ -v
```

### Data Collection
```bash
# Download Uzum products (specify target count)
make uzum-download N=1000
python -m src.platforms.uzum.downloader --target 1000

# Download UZEX lots
make uzex-download N=100
python -m src.platforms.uzex.downloader --type auction --target 100

# Process downloaded files into database
celery -A src.workers.celery_app call src.workers.process_tasks.process_raw_files --args='["uzum"]'
```

### Task Queue (Celery)
```bash
# Start worker
make worker
celery -A src.workers.celery_app worker --loglevel=info

# Start scheduler (for automated tasks)
make beat
celery -A src.workers.celery_app beat --loglevel=info

# Monitor tasks with Flower UI (http://localhost:5555)
make flower
celery -A src.workers.celery_app flower --port=5555
```

### Database Management
```bash
# Show table row counts
make counts

# Backup database
make dump

# Restore from backup
make restore FILE=backups/uzum_scraping_2025-01-01.sql

# Clean Python cache files
make clean
```

## Architecture

### Core Components

**src/core/**
- `config.py` - Central configuration using dataclasses. Settings for database (PostgreSQL), Redis, Celery, downloader concurrency/rate limits. Environment variables: `DB_HOST`, `DB_PORT`, `REDIS_HOST`, `DOWNLOAD_CONCURRENCY`, `RPS_LIMIT`
- `database.py` - Async SQLAlchemy engine with NullPool (required for Celery workers to avoid connection pool issues). Use `get_session()` context manager
- `bulk_ops.py` - High-performance bulk database operations (5x faster than individual merges). Functions: `bulk_upsert_products()`, `bulk_upsert_sellers()`, `bulk_upsert_skus()`, `bulk_insert_price_history()`. Uses PostgreSQL `ON CONFLICT DO UPDATE`. CRITICAL: Call `bulk_upsert_categories()` BEFORE `bulk_upsert_products()` to avoid FK violations
- `models.py` - SQLAlchemy ORM models for all tables
- `checkpoint.py` - Redis-based checkpoint system for resumable downloads
- `redis_client.py` - Redis connection management

### Platform Adapters

**src/platforms/base.py**
- Abstract base class `MarketplacePlatform` - implement for each marketplace
- Key methods: `download_product()`, `parse_product()`, `download_range()`, `get_id_range()`
- `ProductData` dataclass - standardized parsed product structure

**src/platforms/uzum/**
- `downloader.py` - Async downloader with checkpoint-based resume, ID range iteration
- `parser.py` - Parse Uzum API responses into `ProductData`
- `client.py` - HTTP client with rate limiting

**src/platforms/uzex/**
- `downloader.py` - Government procurement lot downloader
- `parser.py` - Parse UZEX API responses
- `models.py` - UZEX-specific models (`UzexLot`, `UzexLotItem`)
- `session.py` - Authentication session management
- `client.py` - API client

### Workers (Celery Tasks)

**src/workers/celery_app.py**
- Celery configuration with infinite retries, 6-hour soft time limit for long-running tasks
- Beat schedule for 24/7 operation:
  - `ensure-uzum-running` - Every 2 hours, restarts stale scrapers (see maintenance_tasks)
  - `hourly-health-check` - Health monitoring
  - `daily-vacuum-4am` - Database maintenance
  - `daily-analytics-3am` - Stats calculation
  - `price-alerts-6h` - Price change detection

**src/workers/continuous_scraper.py**
- `continuous_scan()` - Endless loop that cycles through all product IDs with automatic checkpoint resume. Runs 6+ hours per task, self-heals from crashes
- `check_continuous_status()` - Monitor scraper health
- `restart_if_stale()` - Auto-restart if no updates for max_stale_seconds

**src/workers/process_tasks.py**
- `process_raw_files()` - Process JSON files from storage into database using bulk operations
- `process_pending()` - Process unprocessed `RawSnapshot` records from database

**src/workers/maintenance_tasks.py**
- `ensure_scrapers_running()` - Ensures continuous scrapers are active, restarts if stale
- `health_check()` - System health monitoring
- `vacuum_tables()` - PostgreSQL VACUUM for performance

**src/workers/download_tasks.py**
- Single-run download tasks (non-continuous)

**src/workers/analytics_tasks.py**
- `calculate_daily_stats()` - Daily analytics calculation
- `detect_price_changes()` - Price change alerts

### API (FastAPI)

**src/api/main.py** - FastAPI app entry point
**src/api/routers/**
- `products.py` - Product listing and filters
- `sellers.py` - Seller stats and rankings
- `analytics.py` - Price comparison, price drops, top sellers, CSV export

## Key Patterns

### Async/Sync Context Bridging
Celery tasks are synchronous but most code is async. Use helper:
```python
def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
```

### Bulk Operations Strategy
ALWAYS use bulk operations from `src/core/bulk_ops.py` instead of individual inserts/merges:
1. Accumulate records in buffers (500-1000 records)
2. Deduplicate by ID (keeps last occurrence to avoid CardinalityViolationError)
3. Call bulk functions: `bulk_upsert_sellers()`, `bulk_upsert_products()`, `bulk_upsert_skus()`
4. Commit after each batch
5. ORDER MATTERS: Upsert categories before products (FK constraint)

### Checkpoint-Based Resume
All downloaders use Redis checkpoints for crash recovery:
```python
from src.core.checkpoint import get_checkpoint_manager

checkpoint = await get_checkpoint_manager("uzum", "continuous")
saved = await checkpoint.load_checkpoint()
current_id = saved.get("last_id", 1) if saved else 1

# ... download logic ...

await checkpoint.save_checkpoint({
    "last_id": current_id,
    "total_found": total_found,
    "last_run": datetime.now(timezone.utc).isoformat(),
})
```

### Database Sessions
Always use async context manager:
```python
from src.core.database import get_session

async with get_session() as session:
    # ... operations ...
    await session.commit()  # Auto-rollback on exception
```

### Continuous Scraping Model
- `continuous_scan()` task runs 6+ hours, cycles through all IDs (1 to max_id)
- On reaching max_id, increments cycle counter and restarts from ID 1
- Celery Beat runs `ensure_scrapers_running()` every 2 hours to restart if stale
- Stale = no checkpoint update for >1 hour

## Database

**Connection Details:**
- Host: `localhost` (or `postgres` in Docker)
- Port: `5434` (external), `5432` (internal)
- Database: `uzum_scraping`
- User: `scraper`
- Password: `scraper123`

**Main Tables:**
- `sellers`, `categories`, `products`, `skus`, `price_history` (Uzum e-commerce)
- `raw_snapshots` (optional raw API storage)
- `uzex_lots`, `uzex_lot_items`, `uzex_categories`, `uzex_products` (UZEX government)

**Migrations:** SQL files in `sql/` directory (`001_uzum_schema.sql`, `002_uzex_schema.sql`)

## Docker Compose Services

- `postgres` - PostgreSQL 17 with performance tuning (16GB shared_buffers, 32GB RAM limit, fsync=off for speed)
- `redis` - Redis for Celery broker/backend and checkpoints
- `api` - FastAPI with 4 workers
- `celery_worker` - 4 replicas, 100 concurrency each (400 threads total), 16GB RAM limit
- `celery_beat` - Scheduler for automated tasks (uses `scripts/start_beat.sh`)
- `flower` - Monitoring UI on port 5555

## File Storage

- `storage/raw/uzum/` - Downloaded Uzum JSON files
- `storage/raw/uzex/` - Downloaded UZEX JSON files (nested by lot type)
- `backups/` - Database dumps

## Environment Variables

Set in `.env` or Docker environment:
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`
- `DOWNLOAD_CONCURRENCY` (default: 50)
- `RPS_LIMIT` (requests per second, default: 100)
- `DEBUG`, `LOG_LEVEL`

## Adding New Platforms

1. Create `src/platforms/PLATFORM/` directory
2. Implement `MarketplacePlatform` base class in `downloader.py`
3. Create `parser.py` with `parse_product()` returning `ProductData`
4. Add platform config to `src/core/config.py` PLATFORMS dict
5. Create SQL migration in `sql/` if custom tables needed
6. Add processing logic to `process_tasks.py`
7. Register tasks in `celery_app.py` autodiscover_tasks

## Performance Notes

- Bulk operations are 5x faster than individual merges
- NullPool is REQUIRED for Celery workers (avoids connection pool exhaustion)
- PostgreSQL tuned for write-heavy workloads (synchronous_commit=off, fsync=off)
- Celery worker concurrency=100 per replica for I/O-bound tasks
- Rate limiting via `requests_per_second` in DownloaderConfig
- Checkpoint saves reduce re-work after crashes
