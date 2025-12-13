"""
UZEX Continuous Scrapers - All 6 lot types running in parallel.

Scrapes ALL UZEX data:
- auction + completed (200K lots)
- shop + completed (624K lots) 
- national + completed (362K lots)
- auction + active (328K lots)
- shop + active (14K lots)
- national + active (7K lots)

Total: 1.5M lots
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
        total_found = saved.get("total_found", 0) if saved else 0

        logger.info("🎯 Starting UZEX auction+completed scraper...")

        while True:
            try:
                downloader = UzexDownloader(batch_size=100)
                stats = await downloader.download_lots(
                    lot_type="auction",
                    status="completed",
                    target=batch_target,
                    start_from=current_position,
                    resume=True,
                    skip_existing=False
                )
                
                total_found += stats.found
                current_position += 10000
                
                await checkpoint.save_checkpoint({
                    "last_id": current_position,
                    "total_found": total_found,
                    "last_run": datetime.now(timezone.utc).isoformat(),
                })
                
                logger.info(f"✅ Auction+Completed: {stats.found} new, {total_found:,} total")
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"❌ Error in auction+completed: {e}")
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
        total_found = saved.get("total_found", 0) if saved else 0

        logger.info("🏪 Starting UZEX shop+completed scraper...")

        while True:
            try:
                downloader = UzexDownloader(batch_size=100)
                stats = await downloader.download_lots(
                    lot_type="shop",
                    status="completed",
                    target=batch_target,
                    start_from=current_position,
                    resume=True,
                    skip_existing=False
                )
                
                total_found += stats.found
                current_position += 10000
                
                await checkpoint.save_checkpoint({
                    "last_id": current_position,
                    "total_found": total_found,
                    "last_run": datetime.now(timezone.utc).isoformat(),
                })
                
                logger.info(f"✅ Shop+Completed: {stats.found} new, {total_found:,} total")
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"❌ Error in shop+completed: {e}")
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
        total_found = saved.get("total_found", 0) if saved else 0

        logger.info("🏛️ Starting UZEX national+completed scraper...")

        while True:
            try:
                downloader = UzexDownloader(batch_size=100)
                stats = await downloader.download_lots(
                    lot_type="national",
                    status="completed",
                    target=batch_target,
                    start_from=current_position,
                    resume=True,
                    skip_existing=False
                )
                
                total_found += stats.found
                current_position += 10000
                
                await checkpoint.save_checkpoint({
                    "last_id": current_position,
                    "total_found": total_found,
                    "last_run": datetime.now(timezone.utc).isoformat(),
                })
                
                logger.info(f"✅ National+Completed: {stats.found} new, {total_found:,} total")
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"❌ Error in national+completed: {e}")
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
        total_found = saved.get("total_found", 0) if saved else 0

        logger.info("🔥 Starting UZEX auction+active scraper...")

        while True:
            try:
                downloader = UzexDownloader(batch_size=100)
                stats = await downloader.download_lots(
                    lot_type="auction",
                    status="active",
                    target=batch_target,
                    start_from=current_position,
                    resume=True,
                    skip_existing=False
                )
                
                total_found += stats.found
                current_position += 10000
                
                await checkpoint.save_checkpoint({
                    "last_id": current_position,
                    "total_found": total_found,
                    "last_run": datetime.now(timezone.utc).isoformat(),
                })
                
                logger.info(f"✅ Auction+Active: {stats.found} new, {total_found:,} total")
                await asyncio.sleep(120)  # Longer pause for active deals
                
            except Exception as e:
                logger.error(f"❌ Error in auction+active: {e}")
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
        total_found = saved.get("total_found", 0) if saved else 0

        logger.info("🛍️ Starting UZEX shop+active scraper...")

        while True:
            try:
                downloader = UzexDownloader(batch_size=100)
                stats = await downloader.download_lots(
                    lot_type="shop",
                    status="active",
                    target=batch_target,
                    start_from=current_position,
                    resume=True,
                    skip_existing=False
                )
                
                total_found += stats.found
                current_position += 5000
                
                await checkpoint.save_checkpoint({
                    "last_id": current_position,
                    "total_found": total_found,
                    "last_run": datetime.now(timezone.utc).isoformat(),
                })
                
                logger.info(f"✅ Shop+Active: {stats.found} new, {total_found:,} total")
                await asyncio.sleep(120)
                
            except Exception as e:
                logger.error(f"❌ Error in shop+active: {e}")
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
        total_found = saved.get("total_found", 0) if saved else 0

        logger.info("🏢 Starting UZEX national+active scraper...")

        while True:
            try:
                downloader = UzexDownloader(batch_size=100)
                stats = await downloader.download_lots(
                    lot_type="national",
                    status="active",
                    target=batch_target,
                    start_from=current_position,
                    resume=True,
                    skip_existing=False
                )
                
                total_found += stats.found
                current_position += 5000
                
                await checkpoint.save_checkpoint({
                    "last_id": current_position,
                    "total_found": total_found,
                    "last_run": datetime.now(timezone.utc).isoformat(),
                })
                
                logger.info(f"✅ National+Active: {stats.found} new, {total_found:,} total")
                await asyncio.sleep(120)
                
            except Exception as e:
                logger.error(f"❌ Error in national+active: {e}")
                await asyncio.sleep(300)
                continue
    
    return run_async(scrape())


# ============================================================================
# Utility Functions
# ============================================================================

def check_all_scrapers_status():
    """Check status of all 6 UZEX scrapers."""
    import asyncio
    
    async def check():
        from src.core.checkpoint import get_checkpoint_manager
        
        statuses = {}
        for name in ["auction_completed", "shop_completed", "national_completed",
                     "auction_active", "shop_active", "national_active"]:
            checkpoint = await get_checkpoint_manager("uzex", name)
            saved = await checkpoint.load_checkpoint()
            statuses[name] = saved if saved else {"status": "not_started"}
            await checkpoint.close()
        
        return statuses
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(check())
    finally:
        loop.close()
