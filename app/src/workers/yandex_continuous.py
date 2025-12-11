"""
Continuous Yandex Scraper - Non-stop category discovery and product scraping.

This module provides continuous, never-ending Yandex Market scraping similar to
the Uzum continuous_scan pattern. Runs 24/7 without cron schedules.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from celery import shared_task

logger = logging.getLogger(__name__)


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(bind=True, max_retries=None, name="yandex.continuous_scrape")
def continuous_yandex_scrape(
    self,
    categories_per_cycle: int = 100,
    products_per_run: int = 50000,
    pause_between_cycles_minutes: int = 120  # 2 hours
) -> Dict[str, Any]:
    """
    Continuously scrape Yandex Market in endless loop - RUNS FOREVER.
    
    This task runs FOREVER, cycling through category discovery and product scraping.
    
    Args:
        categories_per_cycle: Max categories to discover per cycle
        products_per_run: Max products to scrape per discovery run  
        pause_between_cycles_minutes: Pause between full cycles
        
    Returns:
        Status dict (only on graceful stop - never happens)
    """
    logger.info("🚀 Starting CONTINUOUS Yandex Market scraping")
    
    async def do_continuous_yandex():
        cycles_completed = 0
        total_products_discovered = 0
        total_products_scraped = 0
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        while True:  # Endless loop
            try:
                logger.info(f"🔄 Yandex Cycle {cycles_completed + 1} starting...")
                
                # Phase 1: Category Discovery 
                logger.info("📋 Phase 1: Discovering categories and products...")
                
                from src.workers.yandex_tasks import discover_yandex_categories
                
                # Trigger discovery (this queues products for scraping)
                discovery_result = discover_yandex_categories.apply(
                    kwargs={
                        'max_products_per_run': products_per_run,
                        'checkpoint_interval': 100,
                    }
                )
                
                # Wait for discovery to complete (blocks until done)
                try:
                    discovery_stats = discovery_result.get(timeout=7200)  # 2 hour timeout
                    products_discovered = discovery_stats.get('products_discovered', 0)
                    total_products_discovered += products_discovered
                    
                    logger.info(
                        f"✅ Discovery complete: {products_discovered} products found, "
                        f"total discovered: {total_products_discovered:,}"
                    )
                    consecutive_errors = 0  # Reset on success
                    
                except Exception as e:
                    logger.error(f"❌ Discovery failed: {e}")
                    consecutive_errors += 1
                
                # Phase 2: Let scraped products process (they're already queued)
                logger.info("⏳ Phase 2: Waiting for product scraping to process...")
                await asyncio.sleep(600)  # 10 minutes for products to scrape
                
                cycles_completed += 1
                
                logger.info(
                    f"🎯 Cycle {cycles_completed} COMPLETE! "
                    f"Total discovered: {total_products_discovered:,}. "
                    f"Pausing {pause_between_cycles_minutes} minutes..."
                )
                
                # Pause between full cycles
                await asyncio.sleep(pause_between_cycles_minutes * 60)
                
            except asyncio.CancelledError:
                logger.info("⏹️ Continuous Yandex scraping cancelled gracefully")
                break
                
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"❌ Error in continuous Yandex scraping (attempt {consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"🔴 Circuit breaker: {max_consecutive_errors} consecutive errors, pausing 10 minutes...")
                    await asyncio.sleep(600)  # 10 min cooldown
                    consecutive_errors = 0
                else:
                    # Exponential backoff
                    wait_time = min(60 * (2 ** consecutive_errors), 600)
                    logger.info(f"⏳ Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                continue  # Don't break, just retry
        
        return {
            "status": "stopped",
            "cycles": cycles_completed,
            "total_discovered": total_products_discovered,
            "total_scraped": total_products_scraped,
        }
    
    try:
        return run_async(do_continuous_yandex())
    except Exception as e:
        logger.error(f"Fatal error in continuous_yandex_scrape: {e}. Task will retry in 60s.")
        raise self.retry(exc=e, countdown=60)
