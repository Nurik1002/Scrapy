"""
OLX Scraper Celery Tasks - Automated continuous scraping
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


@shared_task(bind=True, name="olx.scrape_all", time_limit=7200)
def scrape_olx_all(self, max_pages_per_category: int = 10) -> Dict[str, Any]:
    """
    Scrape all OLX categories and save to database.
    
    Args:
        max_pages_per_category: Max pages to scrape per category (10 pages = ~400 listings)
    
    Returns:
        Scraping statistics
    """
    logger.info("🚀 Starting OLX full scrape...")
    
    async def do_scrape():
        from src.platforms.olx.scraper import OLXScraper
        
        stats = {
            "start_time": datetime.now(timezone.utc).isoformat(),
            "categories_scraped": 0,
            "listings_found": 0,
            "products_saved": 0,
            "errors": 0,
        }
        
        try:
            async with OLXScraper() as scraper:
                # Get categories
                categories = await scraper.client.get_categories()
                logger.info(f"📋 Found {len(categories)} categories to scrape")
                
                for i, cat in enumerate(categories, 1):
                    cat_slug = cat.get("id")
                    cat_name = cat.get("name")
                    
                    try:
                        logger.info(f"📦 [{i}/{len(categories)}] Scraping {cat_name}...")
                        
                        # Scrape category
                        listings = await scraper.scrape_category(cat_slug, max_pages=max_pages_per_category)
                        stats["listings_found"] += len(listings)
                        
                        # Save to database
                        if listings:
                            await scraper._save_to_db(listings)
                            stats["products_saved"] += len(listings)
                            logger.info(f"✅ {cat_name}: {len(listings)} products saved")
                        else:
                            logger.info(f"⚠️ {cat_name}: No listings found")
                        
                        stats["categories_scraped"] += 1
                        
                    except Exception as e:
                        logger.error(f"❌ Error scraping {cat_name}: {e}")
                        stats["errors"] += 1
                
                stats["end_time"] = datetime.now(timezone.utc).isoformat()
                logger.info(f"🎉 OLX scrape complete: {stats}")
                
        except Exception as e:
            logger.error(f"❌ Fatal error in OLX scrape: {e}")
            stats["errors"] += 1
            raise
        
        return stats
    
    try:
        return run_async(do_scrape())
    except Exception as e:
        logger.error(f"OLX scrape failed: {e}")
        raise self.retry(exc=e, countdown=300)  # Retry after 5 minutes


@shared_task(bind=True, name="olx.continuous_scrape", max_retries=None)
def continuous_olx_scrape(self, pages_per_cycle: int = 5, pause_minutes: int = 30) -> Dict[str, Any]:
    """
    Continuously scrape OLX in an infinite loop.
    
    Args:
        pages_per_cycle: Pages per category each cycle
        pause_minutes: Minutes to wait between full cycles
    
    Returns:
        Never returns - runs forever
    """
    logger.info("🔄 Starting OLX continuous scraper...")
    
    async def do_continuous():
        from src.platforms.olx.scraper import OLXScraper
        
        cycle_count = 0
        total_products = 0
        
        while True:  # Infinite loop
            try:
                cycle_count += 1
                logger.info(f"🔄 CYCLE {cycle_count} - Starting...")
                
                async with OLXScraper() as scraper:
                    categories = await scraper.client.get_categories()
                    
                    for cat in categories:
                        cat_slug = cat.get("id")
                        cat_name = cat.get("name")
                        
                        try:
                            listings = await scraper.scrape_category(cat_slug, max_pages=pages_per_cycle)
                            
                            if listings:
                                await scraper._save_to_db(listings)
                                total_products += len(listings)
                                logger.info(f"✅ Cycle {cycle_count} - {cat_name}: {len(listings)} products")
                        
                        except Exception as e:
                            logger.error(f"Error in {cat_name}: {e}")
                            continue
                
                logger.info(f"🎉 Cycle {cycle_count} complete. Total products: {total_products:,}")
                logger.info(f"⏳ Waiting {pause_minutes} minutes before next cycle...")
                
                # Wait before next cycle
                await asyncio.sleep(pause_minutes * 60)
                
            except asyncio.CancelledError:
                logger.info("⏹️ Continuous scraper stopped gracefully")
                break
                
            except Exception as e:
                logger.error(f"❌ Error in cycle {cycle_count}: {e}")
                logger.info("⏳ Waiting 5 minutes before retry...")
                await asyncio.sleep(300)
                continue
        
        return {"cycles": cycle_count, "total_products": total_products}
    
    try:
        return run_async(do_continuous())
    except Exception as e:
        logger.error(f"Fatal error in continuous scraper: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task(name="olx.scrape_category")
def scrape_single_category(category_slug: str, max_pages: int = 10) -> Dict[str, Any]:
    """
    Scrape a single OLX category.
    
    Args:
        category_slug: Category slug (e.g., 'transport')
        max_pages: Number of pages to scrape
    
    Returns:
        Scraping statistics
    """
    logger.info(f"📦 Scraping OLX category: {category_slug}")
    
    async def do_scrape():
        from src.platforms.olx.scraper import OLXScraper
        
        async with OLXScraper() as scraper:
            listings = await scraper.scrape_category(category_slug, max_pages=max_pages)
            
            if listings:
                await scraper._save_to_db(listings)
                logger.info(f"✅ {category_slug}: {len(listings)} products saved")
                return {"category": category_slug, "products": len(listings)}
            else:
                logger.info(f"⚠️ {category_slug}: No listings found")
                return {"category": category_slug, "products": 0}
    
    return run_async(do_scrape())
