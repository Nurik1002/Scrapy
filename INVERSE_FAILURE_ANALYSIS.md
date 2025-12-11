# Inverse Failure Analysis
## How This System WILL Fail (And How to Prevent It)

**Philosophy**: Instead of asking "How do we succeed?", ask "How do we fail?" and eliminate those paths.

**Date**: December 11, 2024  
**Methodology**: Inverse Thinking - Identify failure modes, analyze root causes, prevent systematically

---

## 🔴 Critical Failure Modes (System-Killing)

### 1. Database Fills Up → Complete System Halt

**How It Fails**:
```
Day 1:  6.6 GB  ✅
Week 1: 25 GB   ✅
Week 2: 50 GB   ⚠️
Week 3: 80 GB   ⚠️ Disk 90% full
Week 4: CRASH   ❌ PostgreSQL: "No space left on device"
```

**Cascade Effect**:
- PostgreSQL shuts down
- All scrapers fail to insert data
- Workers crash with exceptions
- Data loss (buffered data not flushed)
- **Recovery time**: 2-4 hours minimum

**Root Causes**:
- No disk space monitoring
- No automatic cleanup
- Unbounded price history growth (661K+ records)
- No data retention policy

**Prevention Strategy**:
```bash
# 1. Monitor disk usage
df -h | grep "/$" | awk '{print $5}' | sed 's/%//'
# Alert if > 80%

# 2. Automatic cleanup policy
DELETE FROM price_history 
WHERE recorded_at < NOW() - INTERVAL '90 days';

# 3. Database partitioning (by date)
CREATE TABLE price_history_2024_12 PARTITION OF price_history
FOR VALUES FROM ('2024-12-01') TO ('2025-01-01');

# 4. Archive old data to S3/cold storage
pg_dump --table=price_history_2024_q1 > archive.sql
```

**Early Warning Signals**:
- Disk usage > 70%
- Query performance degradation
- Slow INSERT operations
- WAL segment growth

---

### 2. Memory Exhaustion → Worker Crashes

**How It Fails**:
```
Hour 1:  Worker memory: 500 MB   ✅
Hour 3:  Worker memory: 1.2 GB   ⚠️
Hour 6:  Worker memory: 2.8 GB   ❌
Hour 7:  OOMKiller: Worker killed
```

**Cascade Effect**:
- Continuous scraping stops mid-batch
- Checkpoint not saved (data loss)
- Docker restarts worker
- Loop repeats → thrashing

**Root Causes**:
- **Buffer accumulation** (Uzum downloader, lines 78-81):
  ```python
  self._products_buffer: Dict[int, Dict] = {}
  self._sellers_buffer: Dict[int, Dict] = {}
  self._skus_buffer: Dict[int, Dict] = {}
  ```
  If flush fails, buffers grow indefinitely!

- **No memory limits** in Docker
- **Async task leaks** (unclosed sessions)
- **Large JSON payloads** in raw_data fields

**Prevention Strategy**:
```yaml
# docker-compose.yml
services:
  celery_worker:
    deploy:
      resources:
        limits:
          memory: 2GB  # Hard limit
        reservations:
          memory: 512MB

# Increase flush frequency
if len(self._products_buffer) >= 50:  # was 100
    await self._flush_to_db()

# Force buffer clear on ANY error
finally:
    self._products_buffer.clear()  # ✅ Already added
```

**Early Warning Signals**:
- `docker stats` shows increasing memory
- Swap usage increasing
- OOM messages in logs

---

### 3. IP Blocks → Zero Data Collection

**How It Fails**:
```
Yandex Scraper:
Request 1-10:  ✅ Success
Request 15:    ⚠️ CAPTCHA
Request 20:    ❌ IP BLOCKED (24 hours)
```

**Cascade Effect**:
- Yandex scraper produces 0 products
- Continuous loop retries same IP
- Proxy budget wasted
- **Data gap**: 1-7 days of missing data

**Root Causes**:
- **Yandex enabled WITHOUT proxies** (current state!)
- No IP rotation
- No CAPTCHA detection
- No graceful degradation

**Prevention Strategy**:
```python
# 1. Proxy validation BEFORE starting
if platform.requires_proxy and not settings.PROXY_ENABLED:
    raise ConfigurationError(f"{platform.name} requires proxies!")

# 2. CAPTCHA detection
async def detect_captcha(response):
    if "captcha" in response.text.lower():
        logger.error("CAPTCHA detected - rotating proxy")
        await proxy_pool.mark_bad(current_proxy)
        await proxy_pool.get_next()
        return True
    return False

# 3. Exponential backoff on blocks
if blocked:
    wait = min(3600 * (2 ** attempt), 86400)  # Max 24 hours
    await asyncio.sleep(wait)
```

**Early Warning Signals**:
- Success rate drops below 50%
- Response times increase
- 403/429 status codes
- Empty result sets

---

### 4. Database Transaction Errors → Data Loss

**How It Fails** (ALREADY OBSERVED!):
```
[ERROR] DB flush error: current transaction is aborted, 
commands ignored until end of transaction block
```

**What's Happening**:
```python
# Transaction 1 (Worker-1)
BEGIN;
INSERT INTO products ...;  # OK
INSERT INTO categories ...; # FAIL (deadlock)
# Transaction now ABORTED

# Worker continues trying...
INSERT INTO sellers ...;    # IGNORED
INSERT INTO skus ...;        # IGNORED
COMMIT;                      # FAILS
```

**Cascade Effect**:
- 100 products buffered
- Database INSERT fails
- Buffer cleared anyway (to prevent memory leak)
- **100 products LOST**
- Happens repeatedly

**Root Causes**:
```python
# src/platforms/uzum/downloader.py:304
await session.commit()
# NO ROLLBACK on error!
```

**Prevention Strategy**:
```python
# CRITICAL FIX
try:
    await session.commit()
except Exception as e:
    await session.rollback()  # ← ADD THIS
    logger.error(f"Transaction failed: {e}")
    raise  # Re-raise to trigger retry
```

**Already Fixed In**: Lines 306-308 have try/except but missing rollback!

**Early Warning Signals**:
- "transaction is aborted" in logs
- Product count not increasing
- High error rate in metrics

---

### 5. Checkpoint Corruption → Restart from Zero

**How It Fails**:
```
# File-based checkpoint
storage/checkpoints/uzum_continuous.json

Worker-1 writes: {"last_id": 500000}  (partial write)
Power loss / SIGKILL
Worker-2 reads: INVALID JSON

→ Checkpoint lost, restart from ID 1
→ Re-scrape 500K products (wasted)
```

**Root Causes**:
- **File-based checkpoints** with no atomic writes
- **4 worker replicas** writing same file (race condition!)
- No write locks
- No backup/versioning

**Prevention Strategy**:
```python
# 1. Use Redis for checkpoints (atomic operations)
await redis.set(f"checkpoint:{platform}:{task}", json.dumps(data))

# 2. Atomic file writes
temp_file = f"{checkpoint_file}.tmp"
with open(temp_file, 'w') as f:
    json.dump(data, f)
os.rename(temp_file, checkpoint_file)  # Atomic on POSIX

# 3. Worker-specific checkpoints
checkpoint_key = f"{platform}_{task}_{worker_id}"

# 4. Checkpoint versioning
checkpoint_data = {
    "version": 2,
    "last_id": 500000,
    "timestamp": now(),
    "worker_id": worker_id
}
```

**Early Warning Signals**:
- JSON decode errors in logs
- Scraper restarting from beginning
- Duplicate products in database

---

## 🟡 High-Risk Failure Modes (Data Quality)

### 6. API Changes → Parser Breaks

**How It Fails**:
```
Uzum API v2 → v3:
{
  "payload": {
    "data": {
      "id": 123,
      "title": "Product"  # ✅ Works
    }
  }
}

→ NEW FORMAT:
{
  "product": {  # ← Changed!
    "id": 123,
    "name": "Product"  # ← Changed!
  }
}

Parser: KeyError: 'payload'
→ ALL products fail to parse
→ 0 products collected
```

**Cascade Effect**:
- Silent data collection stops
- No alerts (because scraper "runs")
- Days/weeks of missing data
- Competitors overtake you

**Root Causes**:
- No API version monitoring
- No parser test coverage
- No data validation
- No fallback parsing

**Prevention Strategy**:
```python
# 1. Defensive parsing with fallbacks
def extract_title(data):
    # Try new format
    title = data.get("product", {}).get("name")
    if title:
        return title
    
    # Fallback to old format
    title = data.get("payload", {}).get("data", {}).get("title")
    if title:
        logger.warning("Using deprecated API format")
        return title
    
    raise ParsingError("Title not found in any known format")

# 2. Schema validation
from pydantic import BaseModel

class UzumProduct(BaseModel):
    id: int
    title: str
    # Validates structure

# 3. Parser success rate monitoring
metrics.increment('parser.success' if parsed else 'parser.failure')
if success_rate < 0.5:
    alert("Parser failing! API change?")
```

**Early Warning Signals**:
- Parsing errors increase suddenly
- Success rate drops
- Empty fields in database
- New NULL values

---

### 7. Stale Data → Incorrect Analytics

**How It Fails**:
```
Price History:
Product #123:
  2024-12-01: 100,000 UZS  ✅
  2024-12-02: 100,000 UZS  ✅
  ... (scraper stops)
  2024-12-20: Still showing 100,000 UZS

ACTUAL: Price dropped to 80,000 on Dec 10
YOUR DATA: Shows 100,000 (20% ERROR)
```

**Business Impact**:
- Users get wrong price alerts
- Miss best deals
- Lose trust
- Churn

**Root Causes**:
- No data freshness checks
- Scraper running but not updating
- No alerting on stale data

**Prevention Strategy**:
```sql
-- 1. Data freshness monitoring
SELECT 
    platform,
    MAX(updated_at) as last_update,
    NOW() - MAX(updated_at) as age
FROM products
GROUP BY platform
HAVING NOW() - MAX(updated_at) > INTERVAL '6 hours';
-- Alert if any platform stale > 6 hours

-- 2. Active product tracking
SELECT COUNT(*) 
FROM products 
WHERE updated_at > NOW() - INTERVAL '24 hours';
-- Should be > 100K/day for Uzum

-- 3. Price change velocity
SELECT COUNT(*)
FROM price_history
WHERE recorded_at > NOW() - INTERVAL '1 day';
-- Should have 10K+ new records daily
```

**Early Warning Signals**:
- Product count not growing
- Price history stagnant
- Last update timestamp old

---

### 8. Duplicate Data → Database Bloat

**How It Fails**:
```
SKU Table:
ID     Product_ID  Price    Created
123    9          229000   2024-12-01
123    9          229000   2024-12-01  ← DUPLICATE
123    9          229000   2024-12-02  ← DUPLICATE
...
(2.3M SKUs, should be 1M)
```

**Cascade Effect**:
- Database 2x larger than needed
- Queries slower
- Costs higher
- Analytics incorrect

**Root Causes**:
- Upsert logic failing
- Missing UNIQUE constraints
- Worker race conditions

**Prevention Strategy**:
```sql
-- 1. Add UNIQUE constraints
ALTER TABLE skus 
ADD CONSTRAINT uq_sku_id UNIQUE (id);

-- 2. Upsert with ON CONFLICT
INSERT INTO skus (id, product_id, price)
VALUES (123, 9, 229000)
ON CONFLICT (id) DO UPDATE
SET price = EXCLUDED.price,
    updated_at = NOW();

-- 3. Periodic deduplication
DELETE FROM skus a
USING skus b
WHERE a.id = b.id 
  AND a.ctid < b.ctid;  -- Keep newer
```

**Early Warning Signals**:
- Table size growing faster than expected
- COUNT(*) vs COUNT(DISTINCT id) mismatch

---

## 🟠 Medium-Risk Failure Modes (Performance)

### 9. N+1 Query Problem → API Timeouts

**How It Fails**:
```python
# GET /api/products (returns 100 products)
for product in products:
    seller = db.query(Seller).filter_by(id=product.seller_id).first()
    # ← 100 separate queries!

# Total: 101 queries for 1 API request
# Response time: 5+ seconds → timeout
```

**Cascade Effect**:
- API unusable
- Users leave
- No SaaS revenue

**Root Causes**:
- No eager loading
- Lazy relationship loading

**Prevention Strategy**:
```python
# Use joinedload
from sqlalchemy.orm import joinedload

products = db.query(Product)\
    .options(joinedload(Product.seller))\
    .options(joinedload(Product.category))\
    .all()
# Only 1 query with JOINs
```

**Early Warning Signals**:
- API response time > 2 seconds
- Database connection pool exhausted

---

### 10. Missing Database Indexes → Slow Queries

**How It Fails**:
```sql
-- User searches: "iPhone"
SELECT * FROM products 
WHERE title LIKE '%iPhone%'
LIMIT 10;

-- Without index on title:
Seq Scan on products (cost=0.00..150000.00 rows=10)
Planning time: 0.5 ms
Execution time: 45000 ms  ❌ 45 SECONDS!
```

**Prevention Strategy**:
```sql
-- Critical indexes
CREATE INDEX idx_products_title ON products USING gin(to_tsvector('english', title));
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_seller ON products(seller_id);
CREATE INDEX idx_products_updated ON products(updated_at DESC);
CREATE INDEX idx_price_history_product_date ON price_history(product_id, recorded_at DESC);

-- Analyze query plans
EXPLAIN ANALYZE SELECT ...;
```

---

### 11. Unbounded Worker Concurrency → Resource Exhaustion

**How It Fails**:
```
Uzum: 150 connections
UZEX: 5 connections
OLX:  20 connections
Yandex: 10 connections
────────────────────
Total: 185 concurrent HTTP connections

+ 4 Celery worker replicas
────────────────────
= 740 concurrent connections

PostgreSQL max_connections: 100  ❌
Redis max_connections: 200       ❌
```

**Prevention Strategy**:
```python
# Global semaphore across all platforms
global_semaphore = asyncio.Semaphore(100)

async def scrape():
    async with global_semaphore:
        await platform.scrape()
```

---

## ⚫ Low-Risk Failure Modes (Operational)

### 12. No Monitoring → Silent Failures

**How It Fails**:
- Scraper stops on Dec 1
- Developer notices on Dec 15
- 2 weeks of data lost

**Prevention Strategy**:
```python
# 1. Sentry for errors
import sentry_sdk
sentry_sdk.init(dsn="...")

# 2. Prometheus metrics
from prometheus_client import Counter, Gauge

scraper_success = Counter('scraper_success_total', 'Successful scrapes')
scraper_errors = Counter('scraper_errors_total', 'Failed scrapes')
products_scraped = Gauge('products_total', 'Total products in DB')

# 3. Healthcheck endpoint
@app.get("/health")
async def health():
    age = db.query(func.max(Product.updated_at)).scalar()
    if datetime.now() - age > timedelta(hours=6):
        raise HTTPException(503, "Data stale")
    return {"status": "healthy"}
```

---

### 13. Hardcoded Credentials → Security Breach

**How It Fails** (ALREADY EXISTS!):
```python
# src/core/config.py
DB_USER: str = Field(default="scraper")      ❌
DB_PASSWORD: str = Field(default="scraper123") ❌
```

**If exposed**:
- Attacker gains database access
- Steals all data
- Deletes tables
- Game over

**Prevention Strategy**:
```python
DB_USER: str = Field(..., env="DB_USER")  # Required
DB_PASSWORD: str = Field(..., env="DB_PASSWORD")  # Required
# No defaults!
```

---

## 📊 Failure Probability Matrix

| Failure Mode | Probability | Impact | Priority |
|-------------|-------------|--------|----------|
| **Database fills up** | 90% (guaranteed in 4 weeks) | CRITICAL | P0 |
| **Memory exhaustion** | 70% (buffer accumulation) | HIGH | P0 |
| **IP blocks (Yandex)** | 95% (no proxies)  | HIGH | P0 |
| **Transaction errors** | 50% (already occurring) | HIGH | P0 |
| **Checkpoint corruption** | 30% (4 workers, file-based) | MEDIUM | P1 |
| **API changes** | 20% per year | MEDIUM | P1 |
| **Stale data** | 40% (no monitoring) | MEDIUM | P1 |
| **Duplicate data** | 10% (has constraints) | LOW | P2 |
| **N+1 queries** | 60% (no eager loading) | MEDIUM | P1 |
| **Missing indexes** | 80% (not added yet) | MEDIUM | P1 |
| **No monitoring** | 100% (current state) | MEDIUM | P1 |
| **Hardcoded creds** | 100% (current state) | HIGH | P0 |

---

## 🔧 Critical Fixes (This Week)

### P0 - System Will Fail Without These

1. **Add transaction rollback** (5 minutes)
   ```python
   except Exception as e:
       await session.rollback()
   ```

2. **Remove hardcoded credentials** (10 minutes)
   ```python
   DB_PASSWORD: str = Field(..., env="DB_PASSWORD")
   ```

3. **Add disk space monitoring** (15 minutes)
   ```bash
   # Cron job
   */30 * * * * /check_disk.sh
   ```

4. **Add database connection pooling** (10 minutes)
   ```python
   NullPool → AsyncAdaptedQueuePool(pool_size=20)
   ```

5. **Configure Yandex proxies OR disable** (30 minutes)
   ```bash
   # Either configure or:
   YANDEX_ENABLED=false
   ```

6. **Add memory limits to Docker** (5 minutes)
   ```yaml
   limits:
     memory: 2GB
   ```

---

## 🎯 Prevention Checklist

Before deploying to production:

- [ ] All database transactions have rollback
- [ ] No hardcoded credentials
- [ ] Disk space monitoring configured
- [ ] Memory limits set on all containers
- [ ] Database connection pooling enabled
- [ ] Database indexes created
- [ ] Yandex proxies configured OR disabled
- [ ] Checkpoint system switched to Redis
- [ ] Sentry/monitoring configured
- [ ] Healthcheck endpoints working
- [ ] Data freshness alerts configured
- [ ] Backup strategy implemented
- [ ] Disaster recovery plan documented

---

## 💡 Key Insight

**Traditional Thinking**: "How do we make this work?"  
**Inverse Thinking**: "How will this break?"

The system is currently running, but it WILL fail in predictable ways:
1. **Database fills up** (4 weeks)
2. **Yandex gets blocked** (immediately when run without proxies)
3. **Transaction errors lose data** (already happening)
4. **Memory leaks crash workers** (within days of continuous operation)

**Fix these 4, prevent 90% of catastrophic failures.**

---

*Inverse Analysis Completed: December 11, 2024*  
*Methodology: Premortem Analysis + Fault Tree Analysis*  
*Next: Implement P0 fixes before continuing data collection*
