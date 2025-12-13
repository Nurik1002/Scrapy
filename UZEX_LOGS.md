# UZEX Scraper Logs

All UZEX scraper logs are written to:

```
/home/ubuntu/Nurgeldi/Retriever/Scrapy/app/logs/
```

## Log Files

### Main UZEX Scrapers Log
- **File**: `uzex_scrapers.log`
- **Size**: Up to 10MB (rotates automatically)
- **Backups**: Keeps 5 old files (uzex_scrapers.log.1, .2, .3, .4, .5)
- **Content**: All 6 UZEX scrapers write here

### View Logs

```bash
# Tail live logs
tail -f /home/ubuntu/Nurgeldi/Retriever/Scrapy/app/logs/uzex_scrapers.log

# View last 100 lines
tail -100 /home/ubuntu/Nurgeldi/Retriever/Scrapy/app/logs/uzex_scrapers.log

# Search for specific scraper
grep "Shop+Completed" /home/ubuntu/Nurgeldi/Retriever/Scrapy/app/logs/uzex_scrapers.log

# Count successful scrapes
grep "✅" /home/ubuntu/Nurgeldi/Retriever/Scrapy/app/logs/uzex_scrapers.log | wc -l
```

### Docker Container Logs (Alternative)

```bash
# View worker logs
docker logs app-celery_worker-1 -f

# Search logs
docker logs app-celery_worker-1 2>&1 | grep "UZEX"
```

## Log Rotation

Logs automatically rotate when they reach 10MB:
- `uzex_scrapers.log` (current)
- `uzex_scrapers.log.1` (previous)
- `uzex_scrapers.log.2` (older)
- `uzex_scrapers.log.3`
- `uzex_scrapers.log.4`
- `uzex_scrapers.log.5` (oldest, gets deleted when new backup created)

## What's Logged

Each scraper logs:
- ✅ Successful batches: "✅ Shop+Completed: 1,000 new, 50,000 total"
- ❌ Errors: "❌ Error in shop+completed: ..."
- 🎯 Startup: "🏪 Starting UZEX shop+completed scraper..."
- 📊 Progress updates

## Troubleshooting

If logs not appearing:
1. Check log directory exists: `ls -la /home/ubuntu/Nurgeldi/Retriever/Scrapy/app/logs/`
2. Check permissions: `chmod 777 /home/ubuntu/Nurgeldi/Retriever/Scrapy/app/logs/`
3. Restart workers: `docker restart app-celery_worker-1`
4. Check for errors: `docker logs app-celery_worker-1 | tail -50`
