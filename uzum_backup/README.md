# Uzum.uz Enterprise Scraper

**Production-grade scraping system** for Uzbekistan's largest marketplace.

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Link Crawler   │────▶│    Redis Queue  │────▶│   Downloader    │
│  (Playwright)   │     │   (Product IDs) │     │ (aiohttp+proxy) │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                        ┌────────────────────────────────▼────────┐
                        │           storage/raw/                  │
                        │     (Raw JSON files - never delete!)    │
                        └────────────────────────────────┬────────┘
                                                         │
                        ┌────────────────────────────────▼────────┐
                        │            Processor                    │
                        │   (Offline - validates & normalizes)    │
                        └────────────────────────────────┬────────┘
                                                         │
┌─────────────────┐     ┌────────────────────────────────▼────────┐
│   Analytics API │◀────│           PostgreSQL                    │
│    (FastAPI)    │     │   (Products, Sellers, Price History)   │
└─────────────────┘     └─────────────────────────────────────────┘
```

## 🚀 Quick Start

### 1. Start Infrastructure
```bash
docker-compose up -d postgres redis
```

### 2. Run Category Crawler
```bash
# Collect product IDs from Electronics category
python -m crawlers.category_crawler --category elektronika-10020 --save-file
```

### 3. Download Products
```bash
# Download products from Redis queue
python -m downloaders.product_downloader --queue --limit 100
```

### 4. Process Data
```bash
# Parse JSON files and save to database
python -m processors.product_processor
```

### 5. Start API
```bash
uvicorn api.main:app --reload
# Open http://localhost:8000/docs
```

## 📁 Project Structure

```
uzum/
├── crawlers/                 # Link discovery (Playwright)
│   └── category_crawler.py   # Collects product IDs → Redis
│
├── downloaders/              # Raw data fetching
│   └── product_downloader.py # API → JSON files (with proxy)
│
├── processors/               # Offline processing
│   └── product_processor.py  # JSON → PostgreSQL (validated)
│
├── api/                      # Analytics API
│   └── main.py               # FastAPI endpoints
│
├── storage/
│   ├── raw/                  # Raw JSON (never delete!)
│   │   └── products/
│   │       └── 2025-12-05/
│   └── exports/              # Generated catalogs
│
├── config.py                 # Centralized configuration
├── init.sql                  # Database schema
├── docker-compose.yml        # Production stack
└── requirements.txt          # Dependencies
```

## 🔑 Key Features

### Decoupled Pipeline
- **Crawler** → Redis → **Downloader** → Raw files → **Processor** → DB
- Each component can fail/restart independently
- Raw JSON files preserved for re-processing

### Data Quality
- Price change validation (alerts on >50% drops)
- Anomaly detection (zero prices, suspicious changes)
- Admin alerts dashboard

### Anti-Detection
- Smart delays with human-like variability
- Proxy rotation (Smartproxy integration)
- Rate limiting (20 req/min default)

### Analytics API
- `GET /api/sellers` - List sellers with stats
- `GET /api/sellers/{id}/products` - Products by seller
- `GET /api/analytics/price-changes` - Recent price changes
- `GET /api/export/catalog.csv` - CSV export

## ⚙️ Configuration

Environment variables:
```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=uzum_scraping
DB_USER=scraper
DB_PASSWORD=scraper123

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Proxy (optional, for production)
PROXY_ENABLED=true
PROXY_USER=sp12345678
PROXY_PASS=your_password

# Scraper settings
SCRAPER_REQUESTS_PER_MINUTE=20
SCRAPER_MIN_DELAY=2.0
SCRAPER_MAX_DELAY=5.0
```

## 📊 Database Schema

### Core Tables
- `products` - Product details, ratings, images
- `sellers` - Seller info, orders, registration
- `skus` - Product variants with prices
- `categories` - Full category taxonomy

### Analytics Tables
- `price_history` - Every price point (never overwrite!)
- `seller_daily_stats` - Daily seller snapshots
- `data_alerts` - Validation issues

### Views
- `v_seller_summary` - Seller aggregated stats
- `v_product_catalog` - Full catalog with prices
- `v_recent_price_changes` - Price change detection

## 🛡️ Best Practices

1. **Always save raw data** - Can re-process if logic changes
2. **Validate before saving** - Don't trust scraped data blindly
3. **Respect rate limits** - Don't DDoS the source
4. **Use residential proxies** - For production at scale
5. **Monitor for changes** - Sites update their structure

## 💰 Cost Estimation

| Component | Monthly Cost |
|-----------|-------------|
| Hetzner VPS (CPX31) | $20 |
| Smartproxy (15GB) | $42 |
| **Total MVP** | **~$62/month** |

## 📈 Scaling

For 10K+ products/day:
1. Add more downloader replicas
2. Use sticky proxy sessions
3. Consider managed PostgreSQL
4. Add Celery Beat for scheduling
