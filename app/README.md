# 🚀 Marketplace Analytics Platform

**SaaS analytics for marketplace sellers** - Starting with Uzum.uz, expanding to other platforms.

## Features

- ⚡ **100x faster** - ID range API iteration instead of browser crawling
- 📊 **Price comparison** - Same product across different sellers
- 📈 **Price history** - Track price changes over time
- 🏆 **Seller analytics** - Top sellers, competitors, insights
- 🔄 **Automated** - Celery scheduled tasks for continuous updates
- 🎯 **Multi-platform ready** - Easy to add new marketplaces

## Quick Start

```bash
# Start infrastructure
docker-compose up -d postgres redis

# Install dependencies
pip install -r requirements.txt

# Download products (1000 target)
python -m src.platforms.uzum.downloader --target 1000

# Process into database
celery -A src.workers.celery_app call src.workers.process_tasks.process_raw_files --args='["uzum"]'

# Start API
uvicorn src.api.main:app --reload
```

## Architecture

```
src/
├── core/           # Config, DB, Models, Redis
├── platforms/      # Marketplace adapters
│   └── uzum/       # Uzum.uz implementation
├── workers/        # Celery tasks
└── api/            # FastAPI endpoints
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/products` | List products with filters |
| `GET /api/sellers` | List sellers with stats |
| `GET /api/analytics/price-comparison` | Compare prices across sellers |
| `GET /api/analytics/price-drops` | Recent price drops |
| `GET /api/analytics/top-sellers` | Top sellers by metric |
| `GET /api/analytics/export/catalog.csv` | Export to CSV |

## Commands

```bash
# Download 10,000 products
python -m src.platforms.uzum.downloader --target 10000

# Start Celery worker
celery -A src.workers.celery_app worker --loglevel=info

# Start Celery Beat (scheduler)
celery -A src.workers.celery_app beat --loglevel=info

# Monitor with Flower
celery -A src.workers.celery_app flower
```

## Future Platforms

- [ ] Wildberries
- [ ] Ozon
- [ ] Amazon

## License

MIT
