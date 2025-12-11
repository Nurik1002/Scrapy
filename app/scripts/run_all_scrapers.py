#!/usr/bin/env python3
"""
Master Scraper Runner - Run all scrapers with debug logging

This script runs all platform scrapers (Uzum, Yandex, UZEX, OLX) with:
- Full debug logging to files
- Real-time console output
- Error handling and recovery
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Create logs directory
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Configure logging
def setup_logging(name: str):
    """Setup logging for a scraper"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = LOGS_DIR / f"{name}_debug_{timestamp}.log"
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # File handler (DEBUG level)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    ))
    
    # Console handler (INFO level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s'
    ))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return log_file


async def run_uzum_scraper(target: int = 1000):
    """Run Uzum scraper"""
    from src.platforms.uzum.downloader import UzumDownloader
    
    logging.info("=" * 60)
    logging.info("UZUM SCRAPER - Starting")
    logging.info("=" * 60)
    
    try:
        downloader = UzumDownloader()
        await downloader.download_range(target=target)
        logging.info(f"Uzum scraper completed: {downloader.stats}")
        return True
    except Exception as e:
        logging.exception(f"Uzum scraper failed: {e}")
        return False


async def run_yandex_scraper(max_categories: int = 5):
    """Run Yandex scraper"""
    from src.platforms.yandex.platform import YandexPlatform
    
    logging.info("=" * 60)
    logging.info("YANDEX SCRAPER - Starting")
    logging.info("=" * 60)
    
    try:
        platform = YandexPlatform()
        async with platform:
            # Health check first
            logging.info("Running Yandex health check...")
            health = await platform.client.health_check()
            
            if not health:
                logging.warning("Yandex health check failed, but continuing...")
            
            # Try to fetch some products
            logging.info(f"Testing product fetch...")
            product = await platform.download_product(100000000001)
            
            if product:
                logging.info(f"Got product data: {len(str(product))} chars")
            else:
                logging.warning("No product data received")
                
        logging.info("Yandex scraper completed")
        return True
    except Exception as e:
        logging.exception(f"Yandex scraper failed: {e}")
        return False


async def run_uzex_scraper(target: int = 50):
    """Run UZEX scraper"""
    from src.platforms.uzex.downloader import UzexDownloader
    
    logging.info("=" * 60)
    logging.info("UZEX SCRAPER - Starting")
    logging.info("=" * 60)
    
    try:
        downloader = UzexDownloader()
        await downloader.download_lots(lot_type="auction", target=target)
        logging.info(f"UZEX scraper completed: {downloader.stats}")
        return True
    except Exception as e:
        logging.exception(f"UZEX scraper failed: {e}")
        return False


async def run_olx_scraper(max_categories: int = 3):
    """Run OLX scraper"""
    from src.platforms.olx.scraper import OLXScraper
    
    logging.info("=" * 60)
    logging.info("OLX SCRAPER - Starting")
    logging.info("=" * 60)
    
    try:
        async with OLXScraper() as scraper:
            listings = await scraper.run_full_scrape(max_categories=max_categories)
            logging.info(f"OLX scraper completed: {len(listings)} listings")
            return True
    except Exception as e:
        logging.exception(f"OLX scraper failed: {e}")
        return False


async def run_all_scrapers():
    """Run all scrapers sequentially with logging"""
    
    log_file = setup_logging("master")
    logging.info(f"Master log file: {log_file}")
    
    logging.info("=" * 80)
    logging.info("MASTER SCRAPER RUNNER")
    logging.info(f"Started at: {datetime.now().isoformat()}")
    logging.info("=" * 80)
    
    results = {}
    
    # Run each scraper
    scrapers = [
        ("uzum", run_uzum_scraper, {"target": 100}),
        ("yandex", run_yandex_scraper, {"max_categories": 3}),
        ("uzex", run_uzex_scraper, {"target": 20}),
        ("olx", run_olx_scraper, {"max_categories": 2}),
    ]
    
    for name, func, kwargs in scrapers:
        logging.info(f"\n{'='*60}")
        logging.info(f"Starting {name.upper()} scraper...")
        logging.info(f"{'='*60}")
        
        try:
            success = await func(**kwargs)
            results[name] = "✅ SUCCESS" if success else "⚠️ PARTIAL"
        except Exception as e:
            logging.exception(f"{name} scraper crashed: {e}")
            results[name] = f"❌ FAILED: {str(e)[:50]}"
    
    # Summary
    logging.info("\n" + "=" * 80)
    logging.info("SCRAPER RUN SUMMARY")
    logging.info("=" * 80)
    
    for name, status in results.items():
        logging.info(f"  {name.upper()}: {status}")
    
    logging.info(f"\nCompleted at: {datetime.now().isoformat()}")
    logging.info(f"Full log saved to: {log_file}")
    
    return results


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run all scrapers with debug logging')
    parser.add_argument('--uzum-only', action='store_true', help='Run only Uzum')
    parser.add_argument('--yandex-only', action='store_true', help='Run only Yandex')
    parser.add_argument('--uzex-only', action='store_true', help='Run only UZEX')
    parser.add_argument('--olx-only', action='store_true', help='Run only OLX')
    
    args = parser.parse_args()
    
    log_file = setup_logging("master")
    
    if args.uzum_only:
        asyncio.run(run_uzum_scraper())
    elif args.yandex_only:
        asyncio.run(run_yandex_scraper())
    elif args.uzex_only:
        asyncio.run(run_uzex_scraper())
    elif args.olx_only:
        asyncio.run(run_olx_scraper())
    else:
        asyncio.run(run_all_scrapers())


if __name__ == "__main__":
    main()
