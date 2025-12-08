# 🏗️ System Architecture Overview

## Executive Summary

The **Marketplace Analytics Platform** is a high-performance web scraping and analytics system designed to collect, process, and analyze product data from multiple e-commerce marketplaces. The system is architected for **24/7 continuous operation** with automatic recovery, checkpoint-based resume capabilities, and horizontal scalability.

### Key Characteristics
- **Performance**: 100+ products/sec scraping rate
- **Scale**: 3.4M+ database rows, 4.5GB data
- **Reliability**: Self-healing with automatic restart
- **Concurrency**: 60 parallel workers (4×15)
- **Platforms**: Uzum.uz, UZEX (government procurement)

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Layer                             │
│  REST API (FastAPI) + Flower Monitoring + Future Web UI     │
└──────────────────────┬────────────────────────────────────────┘
                       │
┌──────────────────────┴────────────────────────────────────────┐
│                   Application Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Workers    │  │  Schedulers  │  │     API      │       │
│  │  (Celery)    │  │ (Celery Beat)│  │  (FastAPI)   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└──────────────────────┬────────────────────────────────────────┘
                       │
┌──────────────────────┴────────────────────────────────────────┐
│                      Data Layer                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  PostgreSQL  │  │    Redis     │  │  File System │       │
│  │  (Primary DB)│  │  (Cache+MQ)  │  │  (Raw JSON)  │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└────────────────────────────────────────────────────────────────┘
                       │
┌──────────────────────┴────────────────────────────────────────┐
│                   External Layer                              │
│  ┌──────────────┐  ┌──────────────┐                          │
│  │   Uzum API   │  │   UZEX Web   │                          │
│  │  (REST API)  │  │  (Playwright)│                          │
│  └──────────────┘  └──────────────┘                          │
└────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. Platform Adapters (`src/platforms/`)

Platform-specific scrapers implementing a common interface:

```
BaseDownloader (Abstract)
├── UzumDownloader (ID Range Iteration)
│   ├── Strategy: Direct API calls
│   ├── Concurrency: 150 async connections
│   └── Output: Direct PostgreSQL insert
│
└── UzexDownloader (Session-based Scraping)
    ├── Strategy: Playwright browser automation
    ├── Concurrency: Limited by session management
    └── Output: Raw JSON + Batch processing
```

**Design Pattern**: Strategy Pattern + Adapter Pattern

### 2. Worker System (`src/workers/`)

Celery-based distributed task queue:

```
celery_app.py (Configuration)
├── download_tasks.py
│   └── scan_id_range() → Download products
├── process_tasks.py
│   └── process_raw_files() → Parse & Insert
├── continuous_scraper.py
│   └── continuous_scan() → 24/7 non-stop
├── maintenance_tasks.py
│   ├── health_check()
│   ├── vacuum_tables()
│   └── ensure_scrapers_running()
└── analytics_tasks.py
    ├── calculate_daily_stats()
    └── detect_price_changes()
```

**Design Patterns**: 
- Task Queue Pattern
- Producer-Consumer Pattern
- Circuit Breaker Pattern (for error recovery)

### 3. Data Layer (`src/core/`)

```
Core Components
├── models.py → SQLAlchemy ORM models
├── database.py → Async session management
├── bulk_ops.py → High-performance bulk inserts
├── checkpoint.py → Resume capability
└── config.py → Centralized configuration
```

**Optimization Strategy**:
- Bulk upserts with `ON CONFLICT DO UPDATE`
- Async PostgreSQL with asyncpg driver
- Connection pooling (NullPool for workers)
- Retry logic with exponential backoff

### 4. API Layer (`src/api/`)

FastAPI REST endpoints:

```
main.py
├── /api/products → Product listings
├── /api/sellers → Seller information
├── /api/analytics/price-comparison
├── /api/analytics/price-drops
├── /api/analytics/top-sellers
└── /api/analytics/export/catalog.csv
```

---

## Data Flow

### Uzum Platform (High-Speed Direct Insert)

```
1. ID Range Generator
   └─> [1, 2, 3, ..., 3,000,000]

2. Async HTTP Requests (150 concurrent)
   └─> Uzum API: /api/v2/product/{id}

3. Parser (In-Memory)
   ├─> Product data
   ├─> Seller data
   ├─> SKU data
   └─> Category data

4. Buffer Accumulation (100 items)
   └─> When buffer full:

5. Bulk Database Insert
   ├─> bulk_upsert_categories()
   ├─> bulk_upsert_sellers()
   ├─> bulk_upsert_products()
   └─> bulk_upsert_skus()

6. Checkpoint Save (Redis)
   └─> {"last_id": N, "total_found": M}
```

**Throughput**: 100-108 products/sec with 15 workers

### UZEX Platform (Session-based with Raw Storage)

```
1. Session Initialization (Playwright)
   └─> Browser context with cookies

2. API Requests (Session-authenticated)
   └─> UZEX API: get_completed_auctions()

3. Raw JSON Storage
   └─> /storage/raw/uzex/auction/YYYY-MM-DD/{lot_id}.json

4. Batch Processing (Separate Task)
   ├─> Read JSON files
   ├─> Parse lot data
   └─> Extract lot items

5. Bulk Database Insert
   ├─> bulk_upsert_uzex_lots()
   └─> bulk_insert_uzex_items()

6. Checkpoint Save (Redis)
   └─> {"last_index": N, "found": M}
```

**Throughput**: 8-10 lots/sec (limited by session)

---

## Database Schema Design

### Uzum Tables

```sql
sellers (16K rows)
  ├─→ products (586K rows)
      ├─→ categories (4.9K rows)
      └─→ skus (1.9M rows)

price_history (661K rows)
  └─→ tracks historical prices
```

**Normalization**: 3NF with denormalization for performance
**Indexes**: Strategic B-tree indexes on foreign keys and query columns

### UZEX Tables

```sql
uzex_lots (14K rows)
  ├─→ uzex_lot_items (168K rows)
  ├─→ uzex_categories (reference)
  └─→ uzex_products (catalog)
```

**Key Features**:
- JSONB for flexible lot properties
- Cascade deletes for referential integrity
- Specialized indexes for government procurement queries

---

## Deployment Architecture

### Docker Compose Services

```yaml
Infrastructure:
  postgres (32GB RAM, 8 CPU)
  redis (Alpine, persistent)

Application:
  api (4 Uvicorn workers)
  celery_worker (4 replicas × 15 concurrency)
  celery_beat (1 scheduler)

Monitoring:
  flower (5555 port)
```

### Resource Allocation

| Service | CPU | Memory | Instances |
|---------|-----|--------|-----------|
| PostgreSQL | 8 cores | 32 GB | 1 |
| Redis | 0.5 cores | 1 GB | 1 |
| API | 2 cores | 2 GB | 1 (4 workers) |
| Celery Workers | 2 cores | 2 GB | 4 |
| Total | ~17 cores | ~43 GB | - |

---

## Scalability Strategy

### Horizontal Scaling
- **Workers**: Add more celery_worker replicas
- **API**: Add more API service instances
- **Database**: Read replicas for analytics queries

### Vertical Scaling
- **PostgreSQL**: Increase shared_buffers, work_mem
- **Workers**: Increase concurrency per worker

### Performance Optimizations Applied

1. **Reduced Concurrency**: 200 → 60 workers (70% reduction)
   - Prevents database deadlocks
   - Improves data save rate to 100%

2. **Retry Logic**: Exponential backoff on deadlocks
   - Auto-retry up to 3 times
   - 1-10 second delays

3. **Bulk Operations**: Batch inserts
   - 100 items per batch
   - PostgreSQL `ON CONFLICT DO UPDATE`

4. **Async I/O**: Throughout the stack
   - AsyncPg for database
   - AsyncIO for HTTP requests
   - Celery async tasks

---

## Key Design Decisions

### 1. Direct DB Insert vs. File-based (Uzum)
**Decision**: Direct PostgreSQL insertion  
**Rationale**: 
- 3x faster than JSON → Parse → Insert
- Lower latency (real-time data availability)
- Reduced storage requirements

### 2. Session Management (UZEX)
**Decision**: Playwright with cookie persistence  
**Rationale**:
- UZEX requires authenticated sessions
- Browser automation handles dynamic content
- Cookie reuse reduces session overhead

### 3. Checkpoint System
**Decision**: Redis-based checkpoints  
**Rationale**:
- Fast read/write for frequent updates
- Atomic operations prevent corruption
- TTL for auto-cleanup

### 4. Task Queue Architecture
**Decision**: Celery with Redis backend  
**Rationale**:
- Battle-tested for distributed systems
- Built-in retry and error handling
- Easy horizontal scaling

### 5. Database Optimizations
**Decision**: `synchronous_commit=off`, `fsync=off`  
**Rationale**:
- 3-5x write performance improvement
- Acceptable for analytics workload (not financial)
- Regular backups mitigate risk

---

## Error Handling & Resilience

### Circuit Breaker Pattern
```python
consecutive_errors = 0
max_consecutive_errors = 10

if consecutive_errors >= max:
    sleep(300)  # 5-minute cooldown
    consecutive_errors = 0
```

### Deadlock Retry Decorator
```python
@deadlock_retry  # Auto-retry with exponential backoff
async def bulk_upsert_products(...):
    # Database operation
```

### Checkpoint-based Resume
```python
checkpoint = await get_checkpoint_manager("uzum", "continuous")
saved = await checkpoint.load_checkpoint()
start_from = saved.get("last_id", 1)
```

---

## Monitoring & Observability

### Health Checks
- **Database**: `pg_isready` every 5s
- **Redis**: `redis-cli ping` every 5s
- **Workers**: Celery event monitoring
- **Application**: HTTP health endpoints

### Metrics Tracked
- Scraping rate (products/sec)
- Success rate (% valid products)
- Database insert rate
- Deadlock occurrences
- Worker status

### Dashboards
- **Flower**: Real-time task monitoring (port 5555)
- **PostgreSQL Stats**: pg_stat_user_tables
- **Redis**: Checkpoint values

---

## Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| **Language** | Python | 3.12 |
| **Web Framework** | FastAPI | Latest |
| **Task Queue** | Celery | 5.6.0 |
| **Database** | PostgreSQL | 17 |
| **Cache/MQ** | Redis | Alpine |
| **ORM** | SQLAlchemy | 2.0+ |
| **HTTP Client** | aiohttp | Latest |
| **Browser** | Playwright | Latest |
| **Containerization** | Docker Compose | Latest |

---

## Security Considerations

### Current State
- ⚠️ Workers running as root (not recommended)
- ⚠️ Database passwords in environment variables
- ⚠️ No API authentication
- ⚠️ No rate limiting on API

### Recommendations
1. Run workers with `--uid` parameter
2. Use Docker secrets for credentials
3. Implement JWT authentication for API
4. Add rate limiting (e.g., slowapi)

---

## Future Architecture Enhancements

### Planned Improvements
1. **Read Replicas**: Separate analytics queries from write operations
2. **Message Queue**: Replace Redis with RabbitMQ for better durability
3. **Caching Layer**: Redis cache for API responses
4. **Event Sourcing**: Append-only event log for audit trail
5. **GraphQL API**: More flexible queries for frontend

### Platform Expansion
- Wildberries integration
- Ozon integration
- Amazon integration

---

## Summary

This architecture achieves **high-throughput data collection** (100+ products/sec) with **high reliability** (self-healing, checkpoints) while maintaining **operational simplicity** (Docker Compose, minimal dependencies). The separation of concerns (platform adapters, workers, API) enables **independent scaling** and **easy platform addition**.

**Trade-offs Made**:
- ✅ Performance over strong consistency (PostgreSQL optimizations)
- ✅ Operational simplicity over microservices complexity
- ✅ Direct insertion over eventual consistency (Uzum)
- ✅ File-based storage over direct insertion (UZEX, due to session requirements)
