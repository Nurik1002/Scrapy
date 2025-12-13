# Quick Script: Start All 6 UZEX Scrapers

Run this to start scraping ALL 1.5M UZEX lots:

```bash
cd /home/ubuntu/Nurgeldi/Retriever/Scrapy/app
./scripts/start_all_uzex_scrapers.sh
```

This will launch 6 scrapers in parallel:
1. auction+completed (200K lots)
2. shop+completed (624K lots) 
3. national+completed (362K lots)
4. auction+active (328K lots)
5. shop+active (14K lots)
6. national+active (7K lots)

Monitor progress:
```bash
# Watch logs
docker logs app-celery_worker-1 -f | grep '✅'

# Check database growth
watch -n 60 'make counts'
```

Filter by lot type:
```sql
-- Query completed deals only
SELECT COUNT(*) FROM procurement.uzex_lots WHERE status = 'completed';

-- Query by lot_type
SELECT lot_type, status, COUNT(*) 
FROM procurement.uzex_lots 
GROUP BY lot_type, status;
```
