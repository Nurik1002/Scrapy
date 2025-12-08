"""
Celery Tasks for Uzum.uz Scraper.

Scheduled jobs for:
- Category crawling
- Product downloading
- Data processing
- Daily analytics
"""
import os
import asyncio
from datetime import datetime, timedelta
from celery import Celery
from celery.schedules import crontab

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config

# Initialize Celery
app = Celery(
    'uzum_scraper',
    broker=config.redis.url,
    backend=config.redis.url
)

# Celery configuration
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Tashkent',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    worker_prefetch_multiplier=1,  # One task at a time for scraping
    task_acks_late=True,  # Acknowledge after completion
)


# ============================================
# HELPER: Run async functions in Celery
# ============================================

def run_async(coro):
    """Run an async coroutine in Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================
# CRAWLING TASKS
# ============================================

@app.task(bind=True, name='crawl_category')
def crawl_category(self, category_slug: str, max_scrolls: int = 20):
    """
    Crawl a category page and push product IDs to queue.
    
    Args:
        category_slug: e.g., "elektronika-10020"
        max_scrolls: Max scroll attempts for lazy loading
    """
    from crawlers.category_crawler import CategoryCrawler
    
    async def _crawl():
        crawler = CategoryCrawler()
        await crawler.setup()
        
        try:
            product_ids = await crawler.crawl_category(category_slug, max_scrolls)
            await crawler.push_to_queue(product_ids)
            await crawler.save_ids_to_file(f"crawl_{category_slug}_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
            return {
                "category": category_slug,
                "products_found": len(product_ids),
                "status": "success"
            }
        finally:
            await crawler.cleanup()
    
    self.update_state(state='RUNNING', meta={'category': category_slug})
    return run_async(_crawl())


@app.task(bind=True, name='crawl_multiple_categories')
def crawl_multiple_categories(self, category_slugs: list):
    """Crawl multiple categories in sequence."""
    from crawlers.category_crawler import CategoryCrawler
    
    async def _crawl_all():
        crawler = CategoryCrawler()
        await crawler.setup()
        
        try:
            results = await crawler.crawl_multiple_categories(category_slugs)
            await crawler.save_ids_to_file()
            return {
                "categories": results,
                "total_products": sum(results.values()),
                "status": "success"
            }
        finally:
            await crawler.cleanup()
    
    self.update_state(state='RUNNING', meta={'categories': category_slugs})
    return run_async(_crawl_all())


# ============================================
# DOWNLOADING TASKS
# ============================================

@app.task(bind=True, name='download_from_queue')
def download_from_queue(self, limit: int = 100):
    """
    Download products from Redis queue.
    
    Args:
        limit: Maximum products to download in this batch
    """
    from downloaders.product_downloader import ProductDownloader
    
    async def _download():
        downloader = ProductDownloader()
        await downloader.setup()
        
        try:
            await downloader.process_queue(limit=limit)
            return {
                "downloaded": downloader.downloaded,
                "failed": downloader.failed,
                "status": "success"
            }
        finally:
            await downloader.cleanup()
    
    self.update_state(state='RUNNING', meta={'limit': limit})
    return run_async(_download())


@app.task(bind=True, name='download_products')
def download_products(self, product_ids: list):
    """Download specific product IDs."""
    from downloaders.product_downloader import ProductDownloader
    
    async def _download():
        downloader = ProductDownloader()
        await downloader.setup()
        
        try:
            results = await downloader.download_list(product_ids)
            success = sum(1 for r in results if r.success)
            return {
                "requested": len(product_ids),
                "downloaded": success,
                "failed": len(product_ids) - success,
                "status": "success"
            }
        finally:
            await downloader.cleanup()
    
    self.update_state(state='RUNNING', meta={'count': len(product_ids)})
    return run_async(_download())


# ============================================
# PROCESSING TASKS
# ============================================

@app.task(bind=True, name='process_raw_files')
def process_raw_files(self, date_str: str = None):
    """
    Process raw JSON files and save to database.
    
    Args:
        date_str: Date folder to process (YYYY-MM-DD), defaults to today
    """
    from processors.product_processor import ProductProcessor
    
    processor = ProductProcessor()
    processor.connect()
    
    try:
        self.update_state(state='RUNNING', meta={'date': date_str or 'today'})
        processor.process_directory(date_str)
        return {
            "processed": processor.processed,
            "failed": processor.failed,
            "alerts_created": processor.alerts_created,
            "status": "success"
        }
    finally:
        processor.close()


@app.task(name='reprocess_all')
def reprocess_all():
    """Re-process all raw files (useful after parser changes)."""
    from processors.product_processor import ProductProcessor
    from config import RAW_STORAGE_DIR
    
    processor = ProductProcessor()
    processor.connect()
    
    try:
        products_dir = RAW_STORAGE_DIR / 'products'
        if products_dir.exists():
            for date_dir in sorted(products_dir.iterdir()):
                if date_dir.is_dir():
                    processor.process_directory(date_dir.name)
        
        return {
            "processed": processor.processed,
            "failed": processor.failed,
            "status": "success"
        }
    finally:
        processor.close()


# ============================================
# ANALYTICS TASKS
# ============================================

@app.task(name='update_seller_daily_stats')
def update_seller_daily_stats():
    """Update daily seller statistics snapshot."""
    import psycopg2
    
    conn = psycopg2.connect(config.database.url)
    try:
        with conn.cursor() as cur:
            # This query is in analytics.sql
            cur.execute("""
                INSERT INTO seller_daily_stats (
                    seller_id, stat_date, 
                    total_products, available_products,
                    total_orders, new_orders,
                    avg_rating, total_reviews, new_reviews,
                    avg_price, min_price, max_price, total_stock
                )
                SELECT 
                    s.id,
                    CURRENT_DATE,
                    COUNT(DISTINCT p.id),
                    COUNT(DISTINCT CASE WHEN p.is_available THEN p.id END),
                    s.total_orders,
                    s.total_orders - COALESCE(prev.total_orders, 0),
                    s.rating,
                    s.reviews_count,
                    s.reviews_count - COALESCE(prev.total_reviews, 0),
                    ROUND(AVG(sk.sell_price)::numeric, 0),
                    MIN(sk.sell_price),
                    MAX(sk.sell_price),
                    SUM(sk.available_amount)
                FROM sellers s
                LEFT JOIN products p ON s.id = p.seller_id
                LEFT JOIN skus sk ON p.id = sk.product_id AND sk.is_available
                LEFT JOIN seller_daily_stats prev ON s.id = prev.seller_id 
                    AND prev.stat_date = CURRENT_DATE - 1
                GROUP BY s.id, prev.total_orders, prev.total_reviews
                ON CONFLICT (seller_id, stat_date) DO UPDATE SET
                    total_products = EXCLUDED.total_products,
                    available_products = EXCLUDED.available_products,
                    total_orders = EXCLUDED.total_orders,
                    new_orders = EXCLUDED.new_orders,
                    avg_rating = EXCLUDED.avg_rating,
                    total_reviews = EXCLUDED.total_reviews,
                    new_reviews = EXCLUDED.new_reviews,
                    avg_price = EXCLUDED.avg_price,
                    min_price = EXCLUDED.min_price,
                    max_price = EXCLUDED.max_price,
                    total_stock = EXCLUDED.total_stock
            """)
            conn.commit()
            return {"status": "success", "date": datetime.now().strftime('%Y-%m-%d')}
    finally:
        conn.close()


@app.task(name='cleanup_old_data')
def cleanup_old_data(days: int = 90):
    """Clean up old price history data (keep last N days)."""
    import psycopg2
    
    conn = psycopg2.connect(config.database.url)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM price_history 
                WHERE scraped_at < NOW() - INTERVAL '%s days'
            """, (days,))
            deleted = cur.rowcount
            conn.commit()
            return {"deleted_records": deleted, "days_kept": days}
    finally:
        conn.close()


@app.task(name='resolve_old_alerts')
def resolve_old_alerts(days: int = 7):
    """Auto-resolve alerts older than N days."""
    import psycopg2
    
    conn = psycopg2.connect(config.database.url)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE data_alerts 
                SET is_resolved = true, 
                    resolved_at = CURRENT_TIMESTAMP,
                    resolved_by = 'auto_cleanup'
                WHERE is_resolved = false
                  AND created_at < NOW() - INTERVAL '%s days'
            """, (days,))
            resolved = cur.rowcount
            conn.commit()
            return {"resolved_alerts": resolved}
    finally:
        conn.close()


# ============================================
# PIPELINE CHAINS
# ============================================

@app.task(name='full_scrape_pipeline')
def full_scrape_pipeline(category_slug: str):
    """
    Run full scraping pipeline for a category:
    1. Crawl category → collect IDs
    2. Download products → save raw JSON
    3. Process files → save to DB
    """
    from celery import chain
    
    # Chain tasks in sequence
    pipeline = chain(
        crawl_category.s(category_slug),
        download_from_queue.s(),  # Will use result from previous
        process_raw_files.s()
    )
    
    return pipeline.delay()


# ============================================
# CELERY BEAT SCHEDULE
# ============================================

app.conf.beat_schedule = {
    # Crawl Electronics every 2 hours
    'crawl-electronics-every-2h': {
        'task': 'crawl_category',
        'schedule': crontab(minute=0, hour='*/2'),
        'args': ('elektronika-10020',),
    },
    
    # Download from queue every 30 minutes
    'download-queue-every-30min': {
        'task': 'download_from_queue',
        'schedule': crontab(minute='*/30'),
        'args': (50,),  # 50 products per batch
    },
    
    # Process raw files every hour
    'process-files-hourly': {
        'task': 'process_raw_files',
        'schedule': crontab(minute=15),  # At :15 past every hour
    },
    
    # Update seller stats daily at 3 AM
    'update-seller-stats-daily': {
        'task': 'update_seller_daily_stats',
        'schedule': crontab(minute=0, hour=3),
    },
    
    # Cleanup old data weekly on Sunday at 4 AM
    'cleanup-old-data-weekly': {
        'task': 'cleanup_old_data',
        'schedule': crontab(minute=0, hour=4, day_of_week=0),
        'args': (90,),  # Keep 90 days
    },
    
    # Auto-resolve old alerts daily
    'resolve-old-alerts-daily': {
        'task': 'resolve_old_alerts',
        'schedule': crontab(minute=30, hour=3),
        'args': (7,),  # Resolve after 7 days
    },
}


if __name__ == '__main__':
    # For testing: run a task directly
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', choices=['crawl', 'download', 'process', 'pipeline'])
    parser.add_argument('--category', default='elektronika-10020')
    args = parser.parse_args()
    
    if args.test == 'crawl':
        result = crawl_category(args.category)
        print(f"Crawl result: {result}")
    elif args.test == 'download':
        result = download_from_queue(10)
        print(f"Download result: {result}")
    elif args.test == 'process':
        result = process_raw_files()
        print(f"Process result: {result}")
    elif args.test == 'pipeline':
        result = full_scrape_pipeline(args.category)
        print(f"Pipeline started: {result}")
