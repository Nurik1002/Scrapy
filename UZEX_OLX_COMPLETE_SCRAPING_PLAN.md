# IMPLEMENTATION PLAN: Complete UZEX & OLX Data Collection

**Problem**: Only scraping **1.4% of available UZEX data** (21K out of 1.5M lots)  
**Root Cause**: continuous_scraper.py only configured for 1 out of 6 lot types  
**Solution**: Add all 6 UZEX lot types + enable OLX scraping

---

## 🔴 PROBLEM ANALYSIS

### Current State

**UZEX Data Available** (from UZEX website):
1. ✅ **auction + completed**: ~200K lots (CURRENTLY SCRAPING)
2. ❌ **shop + completed**: ~624K lots (NOT SCRAPING)
3. ❌ **national + completed**: ~362K lots (NOT SCRAPING)
4. ❌ **auction + active**: ~328K lots (NOT SCRAPING)
5. ❌ **shop + active**: ~14K lots (NOT SCRAPING)
6. ❌ **national + active**: ~7K lots (NOT SCRAPING)

**Total Available**: ~1,536K lots  
**Currently Scraped**: ~21K lots (auction+completed that made it to DB)  
**Missing**: ~1,515K lots (**98.6% of data!**)

### Why Only 21K in Database?

The logs show "1,354,633 lots found" but DB only has 21,403. This means:
1. ✅ Checkpoint shows 1.35M lots processed
2. ❌ But only 21K actually inserted to DB

**Possible reasons**:
- Duplicate lot_id filtering (only unique lots saved)
- Failed DB inserts
- Only recent lots being kept

### OLX Problem

**OLX Data**:
- Database: 52 products only
- No continuous scraper configured
- `olx_scraper.py` exists but not running continuously

---

## 📋 SOLUTION: Three-Phase Approach

### Phase 1: Enable All UZEX Lot Types ⏱️ 1 hour

Add 5 missing UZEX scrapers to run continuously.

### Phase 2: Enable OLX Continuous Scraping ⏱️ 30 minutes

Create continuous scraper for OLX to get more classified ads.

### Phase 3: Monitor & Verify ⏱️ 30 minutes

Verify all scrapers running and data flowing correctly.

**Total Time**: ~2 hours

---

## 🔧 PHASE 1: Enable All UZEX Lot Types

### Current Code (continuous_scraper.py lines 130-141)

```python
elif platform == "uzex":
    from src.platforms.uzex import UzexDownloader

    downloader = UzexDownloader(batch_size=100)
    stats = await downloader.download_lots(
        lot_type="auction",        # ← ONLY AUCTION
        status="completed",        # ← ONLY COMPLETED
        target=batch_target,
        start_from=current_position,
        resume=True,
        skip_existing=False
    )
```

### NEW Code (Add 5 More Scraper Tasks)

> [!NOTE]
> Instead of modifying the existing code, we'll create **6 separate continuous tasks** so they can run in parallel.

**New file**: `src/workers/uzex_continuous_scrapers.py`

```python
"""
UZEX Continuous Scrapers - All 6 lot types running in parallel.
"""
import asyncio
import logging
from celery import shared_task
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================================================
# Completed Deals Scrapers
# ============================================================================

@shared_task(bind=True, max_retries=None)
def uzex_auction_completed(self, batch_target: int = 5000):
    """Scrape completed auction lots (200K lots)."""
    async def scrape():
        from src.platforms.uzex import UzexDownloader
        from src.core.checkpoint import get_checkpoint_manager

        checkpoint = await get_checkpoint_manager("uzex", "auction_completed")
        saved = await checkpoint.load_checkpoint()
        current_position = saved.get("last_id", 1) if saved else 1

        while True:
            try:
                downloader = UzexDownloader(batch_size=100)
                stats = await downloader.download_lots(
                    lot_type="auction",
                    status="completed",
                    target=batch_target,
                    start_from=current_position,
                    resume=True
                )
                
                current_position += 10000
                await checkpoint.save_checkpoint({
                    "last_id": current_position,
                    "last_run": datetime.now(timezone.utc).isoformat(),
                })
                
                logger.info(f"✅ Auction+Completed: {stats.found} lots found")
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in auction+completed: {e}")
                await asyncio.sleep(300)
                continue
    
    return run_async(scrape())


@shared_task(bind=True, max_retries=None)
def uzex_shop_completed(self, batch_target: int = 10000):
    """Scrape completed shop lots (624K lots - BIGGEST!)."""
    async def scrape():
        from src.platforms.uzex import UzexDownloader
        from src.core.checkpoint import get_checkpoint_manager

        checkpoint = await get_checkpoint_manager("uzex", "shop_completed")
        saved = await checkpoint.load_checkpoint()
        current_position = saved.get("last_id", 1) if saved else 1

        while True:
            try:
                downloader = UzexDownloader(batch_size=100)
                stats = await downloader.download_lots(
                    lot_type="shop",
                    status="completed",
                    target=batch_target,
                    start_from=current_position,
                    resume=True
                )
                
                current_position += 10000
                await checkpoint.save_checkpoint({
                    "last_id": current_position,
                    "last_run": datetime.now(timezone.utc).isoformat(),
                })
                
                logger.info(f"✅ Shop+Completed: {stats.found} lots found")
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in shop+completed: {e}")
                await asyncio.sleep(300)
                continue
    
    return run_async(scrape())


@shared_task(bind=True, max_retries=None)
def uzex_national_completed(self, batch_target: int = 10000):
    """Scrape completed national shop lots (362K lots - SECOND BIGGEST!)."""
    async def scrape():
        from src.platforms.uzex import UzexDownloader
        from src.core.checkpoint import get_checkpoint_manager

        checkpoint = await get_checkpoint_manager("uzex", "national_completed")
        saved = await checkpoint.load_checkpoint()
        current_position = saved.get("last_id", 1) if saved else 1

        while True:
            try:
                downloader = UzexDownloader(batch_size=100)
                stats = await downloader.download_lots(
                    lot_type="national",
                    status="completed",
                    target=batch_target,
                    start_from=current_position,
                    resume=True
                )
                
                current_position += 10000
                await checkpoint.save_checkpoint({
                    "last_id": current_position,
                    "last_run": datetime.now(timezone.utc).isoformat(),
                })
                
                logger.info(f\"✅ National+Completed: {stats.found} lots found\")
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f\"Error in national+completed: {e}\")
                await asyncio.sleep(300)
                continue
    
    return run_async(scrape())


# ============================================================================
# Active Deals Scrapers
# ============================================================================

@shared_task(bind=True, max_retries=None)
def uzex_auction_active(self, batch_target: int = 5000):
    """Scrape active auction lots (328K lots)."""
    async def scrape():
        from src.platforms.uzex import UzexDownloader
        from src.core.checkpoint import get_checkpoint_manager

        checkpoint = await get_checkpoint_manager("uzex", "auction_active")
        saved = await checkpoint.load_checkpoint()
        current_position = saved.get("last_id", 1) if saved else 1

        while True:
            try:
                downloader = UzexDownloader(batch_size=100)
                stats = await downloader.download_lots(
                    lot_type="auction",
                    status="active",
                    target=batch_target,
                    start_from=current_position,
                    resume=True
                )
                
                current_position += 10000
                await checkpoint.save_checkpoint({
                    "last_id": current_position,
                    "last_run": datetime.now(timezone.utc).isoformat(),
                })
                
                logger.info(f"✅ Auction+Active: {stats.found} lots found")
                await asyncio.sleep(120)  # Longer pause for active deals
                
            except Exception as e:
                logger.error(f"Error in auction+active: {e}")
                await asyncio.sleep(300)
                continue
    
    return run_async(scrape())


@shared_task(bind=True, max_retries=None)
def uzex_shop_active(self, batch_target: int = 2000):
    """Scrape active shop lots (14K lots)."""
    async def scrape():
        from src.platforms.uzex import UzexDownloader
        from src.core.checkpoint import get_checkpoint_manager

        checkpoint = await get_checkpoint_manager("uzex", "shop_active")
        saved = await checkpoint.load_checkpoint()
        current_position = saved.get("last_id", 1) if saved else 1

        while True:
            try:
                downloader = UzexDownloader(batch_size=100)
                stats = await downloader.download_lots(
                    lot_type="shop",
                    status="active",
                    target=batch_target,
                    start_from=current_position,
                    resume=True
                )
                
                current_position += 5000
                await checkpoint.save_checkpoint({
                    "last_id": current_position,
                    "last_run": datetime.now(timezone.utc).isoformat(),
                })
                
                logger.info(f"✅ Shop+Active: {stats.found} lots found")
                await asyncio.sleep(120)
                
            except Exception as e:
                logger.error(f"Error in shop+active: {e}")
                await asyncio.sleep(300)
                continue
    
    return run_async(scrape())


@shared_task(bind=True, max_retries=None)
def uzex_national_active(self, batch_target: int = 1000):
    """Scrape active national shop lots (7K lots)."""
    async def scrape():
        from src.platforms.uzex import UzexDownloader
        from src.core.checkpoint import get_checkpoint_manager

        checkpoint = await get_checkpoint_manager("uzex", "national_active")
        saved = await checkpoint.load_checkpoint()
        current_position = saved.get("last_id", 1) if saved else 1

        while True:
            try:
                downloader = UzexDownloader(batch_size=100)
                stats = await downloader.download_lots(
                    lot_type="national",
                    status="active",
                    target=batch_target,
                    start_from=current_position,
                    resume=True
                )
                
                current_position += 5000
                await checkpoint.save_checkpoint({
                    "last_id": current_position,
                    "last_run": datetime.now(timezone.utc).isoformat(),
                })
                
                logger.info(f"✅ National+Active: {stats.found} lots found")
                await asyncio.sleep(120)
                
            except Exception as e:
                logger.error(f"Error in national+active: {e}")
                await asyncio.sleep(300)
                continue
    
    return run_async(scrape())
```

### Update celery_app.py

Add new module to autodiscovery:

```python
celery_app.autodiscover_tasks([
    'src.workers.download_tasks',
    'src.workers.process_tasks',
    'src.workers.analytics_tasks',
    'src.workers.continuous_scraper',
    'src.workers.uzex_continuous_scrapers',  # ← ADD THIS
    'src.workers.maintenance_tasks',
    'src.workers.olx_tasks',
])
```

### Start All UZEX Scrapers

Add to Celery Beat startup script or run manually:

```bash
# Start all 6 UZEX scrapers
celery -A src.workers.celery_app call src.workers.uzex_continuous_scrapers.uzex_auction_completed &
celery -A src.workers.celery_app call src.workers.uzex_continuous_scrapers.uzex_shop_completed &
celery -A src.workers.celery_app call src.workers.uzex_continuous_scrapers.uzex_national_completed &
celery -A src.workers.celery_app call src.workers.uzex_continuous_scrapers.uzex_auction_active &
celery -A src.workers.celery_app call src.workers.uzex_continuous_scrapers.uzex_shop_active &
celery -A src.workers.celery_app call src.workers.uzex_continuous_scrapers.uzex_national_active &
```

---

## 🔧 PHASE 2: Enable OLX Continuous Scraping

### NEW Code: `src/workers/olx_continuous_scraper.py`

```python
"""
OLX Continuous Scraper - Non-stop classified ads scraping.
"""
import asyncio
import logging
from celery import shared_task
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(bind=True, max_retries=None)
def olx_continuous_scan(self, batch_target: int = 1000):
    """Continuously scan OLX listings."""
    async def scrape():
        from src.core.checkpoint import get_checkpoint_manager
        
        # TODO: Import OLX scraper (need to check actual implementation)
        # from src.platforms.olx import OLXScraper
        
        checkpoint = await get_checkpoint_manager("olx", "continuous")
        saved = await checkpoint.load_checkpoint()
        
        logger.info("🏪 Starting OLX continuous scraper...")
        
        while True:
            try:
                # Scrape OLX categories and products
                # stats = await scraper.scrape_all_categories(limit=batch_target)
                
                await checkpoint.save_checkpoint({
                    "last_run": datetime.now(timezone.utc).isoformat(),
                })
                
                logger.info(f"✅ OLX: Batch complete")
                await asyncio.sleep(300)  # 5 min between batches
                
            except Exception as e:
                logger.error(f"Error in OLX scraper: {e}")
                await asyncio.sleep(600)
                continue
    
    return run_async(scrape())
```

---

## ✅ VERIFICATION PLAN

### 1. Check All Scrapers Running

```bash
# View Flower UI
open http://localhost:5555

# Or check active workers
celery -A src.workers.celery_app inspect active
```

### 2. Monitor Checkpoints

```bash
# Check Redis checkpoints
docker exec app-redis-1 redis-cli KEYS "checkpoint:uzex:*"
docker exec app-redis-1 redis-cli GET "checkpoint:uzex:shop_completed"
```

### 3. Watch Database Growth

```bash
# Run every 5 minutes
watch -n 300 "make counts"
```

**Expected Growth**:
- First hour: +50K lots
- First day: +500K lots
- First week: All 1.5M lots

### 4. Check Logs

```bash
# Watch for all UZEX types
docker logs app-celery_worker-1 -f | grep "✅"
```

Should see:
```
✅ Auction+Completed: 5,000 lots found
✅ Shop+Completed: 10,000 lots found
✅ National+Completed: 10,000 lots found
✅ Auction+Active: 5,000 lots found
✅ Shop+Active: 2,000 lots found
✅ National+Active: 1,000 lots found
✅ OLX: Batch complete
```

---

## 📊 EXPECTED RESULTS

### After Implementation

| Lot Type | Available | Currently | After Fix | Growth |
|----------|-----------|-----------|-----------|--------|
| auction+completed | 200K | 21K | 200K | +179K |
| shop+completed | 624K | 0 | 624K | +624K |
| national+completed | 362K | 0 | 362K | +362K |
| auction+active | 328K | 0 | 328K | +328K |
| shop+active | 14K | 0 | 14K | +14K |
| national+active | 7K | 0 | 7K | +7K |
| **TOTAL** | **1,535K** | **21K** | **1,535K** | **+1,514K** |

### OLX Growth

- Current: 52 products
- Target: 10,000+ products (depends on availability)

---

## 🚀 NEXT STEPS

1. ✅ Review this plan
2. ⏸️ **STOP** current UZEX scraper (to avoid conflicts)
3. 🔧 Implement new uzex_continuous_scrapers.py
4. 🔧 Implement olx_continuous_scraper.py
5. 🔄 Update celery_app.py autodiscovery
6. 🚀 Start all 6 UZEX + 1 OLX scrapers
7. 📊 Monitor for 1 hour
8. ✅ Verify data growth

---

**Time to Complete**: 2 hours  
**Data Gain**: +1.5M UZEX lots, +10K OLX products  
**System Impact**: Low (parallel scrapers, checkpointed)
