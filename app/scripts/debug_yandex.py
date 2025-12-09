#!/usr/bin/env python3
"""
Yandex Scraper with Debug Mode
Enhanced logging and real-time progress tracking
"""

import asyncio
import sys
import os
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.platforms.yandex.platform import YandexPlatform
from src.core.database import get_async_session

# Configure debug logging
def setup_debug_logging():
    """Setup comprehensive debug logging"""
    
    # Create logs directory
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # Create timestamp-based log file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f'yandex_debug_{timestamp}.log'
    
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            # File handler with DEBUG level
            logging.FileHandler(log_file, encoding='utf-8'),
            # Console handler with INFO level
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific loggers
    loggers = {
        'src.platforms.yandex': logging.DEBUG,
        'src.core.database': logging.INFO,
        'sqlalchemy.engine': logging.WARNING,  # Too verbose at DEBUG
        'asyncio': logging.WARNING,
    }
    
    for logger_name, level in loggers.items():
        logging.getLogger(logger_name).setLevel(level)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Debug logging initialized.Log file: {log_file}")
    
    return logger, log_file

async def test_yandex_scraper(category_limit=5, products_per_category=10):
    """Test Yandex scraper with debug output"""
    
    logger, log_file = setup_debug_logging()
    
    logger.info("="*80)
    logger.info("YANDEX SCRAPER DEBUG TEST")
    logger.info("="*80)
    logger.info(f"Category limit: {category_limit}")
    logger.info(f"Products per category: {products_per_category}")
    logger.info(f"Log file: {log_file}")
    
    try:
        # Initialize platform
        logger.info("Initializing Yandex platform...")
        platform = YandexPlatform()
        
        # Get database session
        logger.info("Connecting to database...")
        async for session in get_async_session():
            # Test category discovery
            logger.info("Testing category walker...")
            categories = await platform.discover_categories(max_categories=category_limit)
            logger.info(f"Found {len(categories)} categories")
            
            for idx, category in enumerate(categories, 1):
                logger.info(f"Category {idx}/{len(categories)}: {category.get('name', 'Unknown')}")
            
            # Test product scraping
            if categories:
                logger.info(f"\nTesting product scraping from first category...")
                first_cat = categories[0]
                logger.info(f"Target category: {first_cat.get('name')}")
                
                products = await platform.scrape_category(
                    category_url=first_cat.get('url'),
                    max_products=products_per_category
                )
                
                logger.info(f"Scraped {len(products)} products")
                
                for idx, product in enumerate(products[:3], 1):
                    logger.info(f"Product {idx}: {product.get('title', 'Unknown')[:50]}...")
            
            # Database health check
            logger.info("\nChecking database health...")
            result = await session.execute("SELECT COUNT(*) FROM products WHERE platform='yandex'")
            yandex_count = result.scalar()
            logger.info(f"Yandex products in DB: {yandex_count}")
            
        logger.info("\n" + "="*80)
        logger.info("TEST COMPLETED SUCCESSFULLY")
        logger.info("="*80)
        logger.info(f"Full debug log saved to: {log_file}")
        
        return True
        
    except Exception as e:
        logger.error("="*80)
        logger.error("TEST FAILED")
        logger.error("="*80)
        logger.exception(f"Error: {e}")
        logger.error(f"Check full log: {log_file}")
        return False

async def continuous_yandex_debug():
    """Run Yandex scraper in continuous debug mode"""
    
    logger, log_file = setup_debug_logging()
    
    logger.info("Starting continuous Yandex scraping (DEBUG MODE)")
    logger.info(f"Log file: {log_file}")
    logger.info("Press Ctrl+C to stop\n")
    
    platform = YandexPlatform()
    
    try:
        async for session in get_async_session():
            cycle = 1
            while True:
                logger.info(f"\n{'='*60}")
                logger.info(f"SCRAPING CYCLE #{cycle}")
                logger.info(f"{'='*60}")
                
                # Discover categories
                logger.info("Phase 1: Category Discovery")
                categories = await platform.discover_categories(max_categories=50)
                logger.info(f"Found {len(categories)} categories")
                
                # Scrape products from each category
                logger.info("Phase 2: Product Scraping")
                total_products = 0
                
                for idx, category in enumerate(categories, 1):
                    logger.info(f"\nScraping category {idx}/{len(categories)}: {category.get('name')}")
                    
                    products = await platform.scrape_category(
                        category_url=category.get('url'),
                        max_products=100
                    )
                    
                    logger.info(f"  → Scraped {len(products)} products")
                    total_products += len(products)
                
                logger.info(f"\nCycle #{cycle} complete: {total_products} total products")
                logger.info("Waiting 60 seconds before next cycle...")
                
                await asyncio.sleep(60)
                cycle += 1
                
    except KeyboardInterrupt:
        logger.info("\nScraping stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Yandex Scraper Debug Tool')
    parser.add_argument('--test', action='store_true', help='Run test mode (limited scraping)')
    parser.add_argument('--continuous', action='store_true', help='Run continuous scraping')
    parser.add_argument('--categories', type=int, default=5, help='Number of categories (test mode)')
    parser.add_argument('--products', type=int, default=10, help='Products per category (test mode)')
    
    args = parser.parse_args()
    
    if args.continuous:
        asyncio.run(continuous_yandex_debug())
    else:
        # Default: test mode
        success = asyncio.run(test_yandex_scraper(
            category_limit=args.categories,
            products_per_category=args.products
        ))
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
