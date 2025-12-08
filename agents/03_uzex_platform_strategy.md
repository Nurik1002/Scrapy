# 🏛️ UZEX Platform Scraping Strategy

## Overview

**UZEX (Uzbekistan Electronic Procurement Exchange)** is a government procurement platform requiring **authenticated sessions** and **browser-based interaction**. Unlike Uzum's simple REST API, UZEX requires sophisticated session management and dynamic content handling.

### Key Statistics
- **Throughput**: 8-10 lots/sec
- **Method**: Playwright browser automation
- **Authentication**: Cookie-based sessions
- **Storage**: Raw JSON files → Batch processing
- **Target Range**: Government procurement lots (auctions, e-shop, national shop)

---

## Why Different from Uzum?

| Aspect | Uzum | UZEX |
|--------|------|------|
| API Type | Public REST | Session-authenticated |
| Access | No auth required | Cookie-based session |
| Content | Static JSON | Dynamic JavaScript |
| Speed | 100+ products/sec | 8-10 lots/sec |
| Approach | Direct DB insert | Save JSON → Process |

---

## Session Management Strategy

### 1. Playwright Integration

```python
from playwright.async_api import async_playwright

async def initialize_session():
    browser = await playwright.chromium.launch()
    context = await browser.new_context()
    page = await context.new_page()
    
    # Navigate to trigger session creation
    await page.goto("https://uzex.uz")
    
    # Extract cookies
    cookies = await context.cookies()
    return cookies
```

### 2. Cookie Persistence

```python
class UzexClient:
    def __init__(self):
        self.session_cookies = None
        
    async def refresh_session(self):
        # Use Playwright to get fresh cookies
        cookies = await get_session_cookies()
        self.session_cookies = cookies
        
    async def make_request(self, url):
        # Use cookies in requests
        headers = {"Cookie": format_cookies(self.session_cookies)}
        return await httpx.get(url, headers=headers)
```

### 3. Session Lifecycle

```
1. Initial Session Creation (Playwright)
   └─> Open browser → Navigate → Extract cookies

2. Session Reuse (HTTP Client)
   └─> Use cookies for API calls (much faster)

3. Session Refresh (When expired)
   └─> Detect 401/403 → Re-run Playwright → Update cookies
```

---

## API Structure

### Base URL
```
https://uzex.uz/api
```

### Key Endpoints

#### 1. Completed Auctions
```python
async def get_completed_auctions(from_idx, to_idx):
    url = "https://uzex.uz/api/uzex/online/auction/getCompletedAuctionsList"
    params = {
        "fromIndex": from_idx,
        "toIndex": to_idx
    }
    return await session.post(url, json=params, cookies=cookies)
```

#### 2. Auction Products  
```python
async def get_auction_products(lot_id):
    url = f"https://uzex.uz/api/uzex/online/auction/getWinnerProductList/{lot_id}"
    return await session.get(url, cookies=cookies)
```

#### 3. E-Shop Lots
```python
async def get_completed_shop(from_idx, to_idx, nat ional=False):
    endpoint = "getNationalShopList" if national else "getCompletedShopList"
    url = f"https://uzex.uz/api/uzex/online/eshop/{endpoint}"
    # Similar params as auctions
```

---

## Data Structure

### Lot Data
```json
{
  "lot_id": 12345,
  "display_no": "LOT-2024-001",
  "lot_type": "auction",
  "status": "completed",
  "is_budget": true,
  "start_cost": 1000000,
  "deal_cost": 950000,
  "customer_name": "Ministry of Health",
  "customer_inn": "123456789",
  "provider_name": "ABC Company",
  "provider_inn": "987654321",
  "deal_date": "2024-12-01",
  "pcp_count": 5,  // Number of items
  "category_name": "Medical Equipment"
}
```

### Lot Items
```json
{
  "product_name": "Hospital Bed",
  "description": "Electric adjustable bed",
  "quantity": 50,
  "amount": 50000,
  "price": 1000,
  "cost": 50000,
  "measure_name": "piece",
  "country_name": "Uzbekistan"
}
```

---

## Scraping Flow

### 1. Download Phase (Save Raw JSON)

```python
async def download_lots(lot_type="auction", status="completed"):
    # Initialize client with session
    client = UzexClient()
    await client.refresh_session()
    
    # Iterate through pagination
    from_idx = 1
    batch_size = 100
    
    while True:
        to_idx = from_idx + batch_size
        
        # Fetch batch
        lots = await client.get_completed_auctions(from_idx, to_idx)
        
        if not lots:
            break
            
        for lot in lots:
            # Save raw JSON to file
            filepath = f"/storage/raw/uzex/auction/{date}/{lot_id}.json"
            with open(filepath, 'w') as f:
                json.dump(lot, f)
                
            # Mark as seen
            await checkpoint.mark_seen(lot_id)
            
        from_idx = to_idx
```

### 2. Processing Phase (Parse & Insert)

```python
async def process_raw_files(platform="uzex"):
    # Find all unprocessed JSON files
    json_files = Path("/storage/raw/uzex").rglob("*.json")
    
    lots_buffer = []
    items_buffer = []
    
    for json_file in json_files:
        # Read and parse
        with open(json_file) as f:
            raw_data = json.load(f)
            
        # Parse lot
        lot = parser.parse_lot(raw_data)
        lots_buffer.append(lot)
        
        # Parse items
        if lot.items:
            items_buffer.extend(lot.items)
            
        # Flush when buffer full
        if len(lots_buffer) >= 100:
            await bulk_upsert_uzex_lots(session, lots_buffer)
            await bulk_insert_uzex_items(session, items_buffer)
            lots_buffer = []
            items_buffer = []
```

---

## Checkpoint System

### UZEX Checkpoints

Stored in Redis with different keys per lot type:

```python
# Auction lots
checkpoint:uzex:auction_completed
{
    "last_index": 101301,
    "found": 10899,
    "processed": 100000
}

# Overall progress
checkpoint:uzex:continuous
{
    "last_id": 190001,
    "total_found": 1351476,
    "cycles": 2
}
```

---

## Performance Characteristics

### Why Slower than Uzum?

1. **Session Overhead**: Playwright browser startup (3-5s)
2. **Authentication**: Cookie refresh needed periodically
3. **Dynamic Content**: JavaScript execution required
4. **Pagination**: API returns batches, not individual items
5. **Items per Lot**: Need secondary API call for lot details

### Optimization Strategies

```python
# 1. Session Reuse
session_cookies = None  # Global cache
if not session_cookies or is_expired(session_cookies):
    session_cookies = await refresh_session()

# 2. Parallel Processing (Limited)
# Can't go too high due to session limits
max_concurrent = 5

# 3. Skip Already Seen
if await checkpoint.is_seen(lot_id):
    continue  # Don't re-download
```

---

## Error Handling

### 1. Session Expiration

```python
try:
    lots = await client.get_lots()
except Unauthorized:
    # Re-authenticate
    await client.refresh_session()
    lots = await client.get_lots()  # Retry
```

### 2. Timeout Handling

```python
try:
    await page.goto(url, timeout=30000)
except TimeoutError:
    logger.warning("Page load timeout, refreshing session...")
    await refresh_session()
```

### 3. Missing Data

```python
# UZEX data can be incomplete
lot_data = {
    "customer_name": data.get("customer_name") or "Unknown",
    "provider_name": data.get("provider_name") or "Unknown",
    "deal_cost": data.get("deal_cost") or 0
}
```

---

## Data Models

### UZEX Lots
```sql
CREATE TABLE uzex_lots (
    id BIGINT PRIMARY KEY,
    display_no VARCHAR(50),
    lot_type VARCHAR(20),  -- auction, shop, national
    status VARCHAR(20),    -- completed, active
    customer_name VARCHAR(500),
    provider_name VARCHAR(500),
    deal_cost NUMERIC(18,2),
    category_name VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### UZEX Lot Items
```sql
CREATE TABLE uzex_lot_items (
    id BIGSERIAL PRIMARY KEY,
    lot_id BIGINT REFERENCES uzex_lots(id) ON DELETE CASCADE,
    product_name TEXT,
    quantity NUMERIC(12,2),
    price NUMERIC(18,2),
    cost NUMERIC(18,2),
    measure_name VARCHAR(100),
    properties JSONB
);
```

---

## Why Raw JSON Storage?

### Rationale

1. **Audit Trail**: Keep original data for reprocessing
2. **Schema Evolution**: Can reparse with new logic
3. **Error Recovery**: Failed processing can retry from files
4. **Compliance**: Government data retention requirements

### Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| **Direct DB** | Faster, simpler | No audit trail |
| **Raw JSON** | Audit, reprocess | Slower, more storage |

UZEX uses raw JSON due to:
- Complex data structure (nested lots/items)
- Government procurement regulations
- Need for data validation before insertion

---

## Continuous Scraping

### Implementation

```python
@shared_task
def continuous_scan(platform="uzex"):
    while True:
        # Download batch
        stats = await downloader.download_lots(
            lot_type="auction",
            status="completed",
            target=5000,
            resume=True
        )
        
        # 60-second pause (avoid overloading)
        await asyncio.sleep(60)
        
        # Process saved files (separate task)
        await process_raw_files.delay("uzex")
```

### Current Status
- **Files Saved**: 11,117 JSON files
- **Lots in DB**: 14,120
- **Items in DB**: 167,938
- **Last Run**: 18 hours ago (needs restart)

---

## Future Enhancements

1. **Headless Mode**: Run Playwright in headless mode for speed
2. **Session Pool**: Maintain multiple sessions for parallelism
3. **Incremental Updates**: Only fetch new lots (delta scraping)
4. **Real-time Monitoring**: WebSocket for live auction updates
5. **Category Mapping**: Link UZEX categories to standard classification

---

## Code Structure

```
src/platforms/uzex/
├── __init__.py
├── client.py         # Session management + HTTP
├── parser.py         # JSON → LotData
├── downloader.py     # Orchestrator
├── models.py         # Data classes (LotData)
└── session.py        # Playwright session handler
```

---

## Best Practices

1. **Always refresh sessions** before long scraping runs
2. **Save raw JSON** for government data compliance
3. **Check `is_seen`** to avoid duplicate downloads
4. **Process in batches** separate from download
5. **Monitor session health** (cookie expiration)

---

## Summary

UZEX platform requires a fundamentally different approach than Uzum due to authentication requirements and dynamic content. The two-phase strategy (download → process) ensures data integrity and provides an audit trail, albeit at the cost of increased complexity and reduced throughput (8 lots/sec vs. 100+ products/sec for Uzum).

The session management complexity is justified by the need to access authenticated government procurement data that would otherwise be unavailable.
