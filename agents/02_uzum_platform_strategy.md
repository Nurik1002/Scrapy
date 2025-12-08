# 🚀 Uzum Platform Scraping Strategy

## Overview

**Uzum.uz** is an e-commerce marketplace with a **publicly accessible REST API** that allows direct product data retrieval without authentication. This enables extremely high-performance scraping via ID range iteration.

### Key Statistics
- **Throughput**: 100-108 products/sec
- **Success Rate**: 75-80%
- **Concurrency**: 150 async connections (reduced to 60 in production)
- **Target Range**: 1 - 3,000,000 product IDs
- **Method**: Direct PostgreSQL insertion (no intermediate files)

---

## Scraping Strategy

### 1. ID Range Iteration

Instead of crawling links, the system iterates through product IDs:

```python
for id in range(1, 3_000_000):
    product = await client.fetch_product(id)
    if product:
        await insert_to_db(product)
```

**Advantages**:
- ✅ 100x faster than browser scraping
- ✅ Complete coverage (no missed products)
- ✅ Easy resume (save last ID processed)
- ✅ Predictable progress tracking

### 2. High Concurrency Architecture

```python
class UzumDownloader:
    def __init__(self, concurrency=150):
        # 150 parallel async HTTP requests
        self.semaphore = asyncio.Semaphore(concurrency)
        
    async def download_range(self, start_id, end_id):
        tasks = []
        for batch_start in range(start_id, end_id, batch_size):
            batch = list(range(batch_start, batch_start + batch_size))
            task = self.fetch_batch(batch)
            tasks.append(task)
        await asyncio.gather(*tasks)
```

**Connection Pooling**:
- TCP connector limit: 500 connections
- Keep-alive timeout: 30s
- DNS TTL cache: 300s

### 3. Direct Database Insertion

Unlike UZEX, Uzum data is inserted directly to PostgreSQL:

```python
# NO JSON files saved (except for backup)
await bulk_upsert_categories(session, categories)
await bulk_upsert_sellers(session, sellers)
await bulk_upsert_products(session, products)
await bulk_upsert_skus(session, skus)
```

**Benefits**:
- Real-time data availability
- Lower storage requirements (no JSON files)
- Simpler data pipeline

---

## API Structure

### Base URL
```
https://api.uzum.uz/api/v2
```

### Product Endpoint
```
GET /product/{product_id}
```

**Headers Required**:
```python
{
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Accept": "application/json",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"
}
```

### Response Structure
```json
{
  "payload": {
    "data": {
      "id": 123456,
      "title": "Product Name",
      "category": { "id": 1, "title": "Category", "parent": {...} },
      "seller": { "id": 5, "title": "Seller Name", "rating": 4.8, ... },
      "skuList": [
        {
          "fullPrice": 100000,
          "purchasePrice": 80000,
          "availableAmount": 50,
          "characteristics": [...],
          "barcode": "1234567890"
        }
      ],
      "description": "...",
      "photos": ["url1", "url2"]
    }
  }
}
```

---

## Data Extraction

### Parser Logic (`parser.py`)

```python
class UzumParser:
    @staticmethod
    def parse_product(raw_data) -> ProductData:
        # Extract from nested JSON
        payload = raw_data.get("payload", {})
        data = payload.get("data", {})
        
        # Normalize title (for cross-seller comparison)
        normalized_title = normalize_title(data.get("title"))
        
        # Parse category hierarchy
        category_path = extract_category_path(data.get("category"))
        
        # Extract seller info
        seller = extract_seller(data.get("seller"))
        
        # Parse all SKUs (variations)
        skus = extract_skus(data.get("skuList"))
        
        return ProductData(...)
```

### Title Normalization

Critical for detecting the same product across sellers:

```python
def normalize_title(title: str) -> str:
    # Remove brand names, sizes, colors
    # Convert to lowercase
    # Remove special chars
    # Deduplicate words
    return normalized
```

---

## Performance Optimizations

### 1. Batch Processing

```python
# Process 100 IDs at once
batch_size = 500
db_batch_size = 100

# Buffers
products_buffer = []
sellers_buffer = []
skus_buffer = []

# Flush when full
if len(products_buffer) >= db_batch_size:
    await flush_to_db()
```

### 2. Smart Rate Limiting

```python
# Random sleep to avoid pattern detection
await asyncio.sleep(random.uniform(0.01, 0.1))

# Exponential backoff on 429
if response.status == 429:
    wait = (attempt + 1) * 2
    await asyncio.sleep(wait)
```

### 3. Connection Reuse

```python
connector = TCPConnector(
    limit=concurrency,
    limit_per_host=concurrency,
    ttl_dns_cache=300,
    keepalive_timeout=30,
    force_close=False  # Reuse connections
)
```

---

## Checkpoint System

### Resume Capability

```python
# Save every 1000 products
checkpoint = {
    "last_id": 258501,
    "total_found": 131239,
    "cycles": 0,
    "last_run": "2025-12-08T11:04:21Z",
    "rate": 103.6
}
await redis.set("checkpoint:uzum:continuous", json.dumps(checkpoint))

# Resume from saved position
saved = await redis.get("checkpoint:uzum:continuous")
start_from = saved["last_id"] + 1
```

**Stored in Redis**:
- Key: `checkpoint:uzum:continuous`
- TTL: Persistent (no expiration)
- Format: JSON string

---

## Error Handling

### 1. HTTP Status Codes

```python
if status == 200:
    return data  # Valid product
elif status == 404:
    return None  # Product doesn't exist
elif status == 429:
    await asyncio.sleep(backoff)  # Rate limited
else:
    return None  # Other error
```

### 2. Timeout Handling

```python
try:
    async with timeout(15):  # 15 second timeout
        response = await session.get(url)
except asyncio.TimeoutError:
    # Log and continue
    logger.debug(f"Timeout for ID {product_id}")
    return None
```

### 3. Database Deadlocks

```python
@deadlock_retry  # Auto-retry decorator
async def bulk_upsert_products(session, products):
    stmt = insert(Product).values(products)
    stmt = stmt.on_conflict_do_update(...)
    await session.execute(stmt)
```

---

## Data Models

### Product
- **Primary Key**: `id` (from API)
- **Unique Together**: (`title`, `seller_id`)
- **Indexes**: `category_id`, `seller_id`, `normalized_title`

### SKU (Stock Keeping Unit)
- **Primary Key**: `id` (auto-increment)
- **Foreign Keys**: `product_id`, `seller_id`
- **Purpose**: Track product variations (size, color)

### Category
- **Hierarchy**: Self-referential (`parent_id`)
- **Indexes**: `platform`, `parent_id`

### Seller
- **Primary Key**: `id` (from API)
- **Tracked**: Rating, reviews, orders, registration date

---

## Continuous Scraping

### 24/7 Operation

```python
@shared_task(max_retries=None)
def continuous_scan(platform="uzum"):
    while True:  # Never stops
        # Scan chunk (100K IDs)
        stats = await download_range(
            start=current_position,
            end=current_position + 100000,
            target=20000  # Stop after 20K products found
        )
        
        # Save checkpoint
        await save_checkpoint(stats)
        
        # Cycle complete?
        if current_position >= 3_000_000:
            cycles += 1
            current_position = 1  # Restart
            await asyncio.sleep(300)  # 5 min pause
```

### Auto-Restart on Crash

```python
# Celery Beat ensures scraper is always running
'ensure-uzum-running': {
    'task': 'ensure_scrapers_running',
    'schedule': crontab(hour='*/2'),  # Every 2 hours
}
```

---

## Performance Metrics

### Current Stats (After Optimization)
- **Rate**: 108 products/sec
- **Position**: ID 1,070,001 / 3,000,000 (36%)
- **Total Found**: 709,555 products
- **Database**: 586,551 products saved
- **Concurrency**: 60 workers (4×15)

### Historical Comparison
- **Before Fix**: 50% data loss due to deadlocks
- **After Fix**: 100% save rate

---

## Advantages vs. UZEX

| Feature | Uzum | UZEX |
|---------|------|------|
| **Authentication** | None | Required (session) |
| **Speed** | 100+ products/sec | 8-10 lots/sec |
| **Method** | REST API | Browser automation |
| **Storage** | Direct DB | Raw JSON first |
| **Complexity** | Low | High |
| **Reliability** | Excellent | Good |

---

## Future Enhancements

1. **GraphQL API**: More efficient data fetching
2. **Image Download**: Store product images locally
3. **Review Scraping**: Collect customer reviews
4. **Real-time Updates**: WebSocket for price changes
5. **Multi-region**: Support different Uzum regions

---

## Code Structure

```
src/platforms/uzum/
├── __init__.py
├── client.py        # HTTP client (aiohttp)
├── parser.py        # JSON → ProductData
├── downloader.py    # Orchestrator (main logic)
└── models.py        # Data classes
```

---

## Best Practices

1. **Always use checkpoints** - Never lose progress
2. **Monitor rate limits** - Respect 429 responses
3. **Validate data** - Check for required fields
4. **Log selectively** - Too many logs slow down scraping
5. **Batch inserts** - 100 items per DB operation

---

## Summary

Uzum scraping strategy prioritizes **speed and simplicity** by leveraging the public REST API. The ID range iteration approach combined with high async concurrency enables **100x faster** data collection compared to traditional browser-based scraping. Direct database insertion eliminates intermediate storage overhead, making the pipeline extremely efficient.
