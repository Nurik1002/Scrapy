"""
Category Crawler - Collects ALL Product IDs from Uzum.uz categories.

Features:
- HEADLESS browser (invisible)
- Pagination support (currentPage=1,2,3...)
- Subcategory discovery
- Auto-save after each category (no data loss!)
- Progress tracking

Fixed issues:
- Hidden browser (headless=True)
- Save progress after each category
- Better error handling
"""
import asyncio
import re
import json
import logging
from typing import List, Set, Optional, Dict
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field

from playwright.async_api import async_playwright, Page, Browser
import redis.asyncio as redis

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config, RAW_STORAGE_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class CrawlStats:
    """Track crawling statistics."""
    categories_crawled: int = 0
    pages_crawled: int = 0
    products_found: int = 0
    errors: int = 0
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CategoryCrawler:
    """
    Crawls Uzum.uz category pages with FULL pagination and subcategory support.
    
    Fixed Issues:
    - headless=True (browser hidden)
    - Auto-save after each category
    - Better error recovery
    """
    
    PRODUCT_URL_PATTERN = re.compile(r'-([\d]+)(?:\?|$)')
    MAX_PAGES_PER_CATEGORY = 50  # Safety limit
    
    def __init__(self, headless: bool = True):
        self.browser: Optional[Browser] = None
        self.playwright = None
        self.redis_client: Optional[redis.Redis] = None
        self.collected_ids: Set[int] = set()
        self.crawled_categories: Set[str] = set()
        self.stats = CrawlStats()
        self.headless = headless
        self.save_path = RAW_STORAGE_DIR / "product_ids.json"
        
    async def setup(self):
        """Initialize browser and Redis connection."""
        self.playwright = await async_playwright().start()
        
        # HEADLESS mode - browser is invisible!
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
        
        try:
            self.redis_client = await redis.from_url(config.redis.url)
        except Exception as e:
            logger.warning(f"Redis not available: {e}")
            self.redis_client = None
            
        logger.info(f"CategoryCrawler initialized (headless={self.headless})")
        
        # Load existing IDs if file exists
        if self.save_path.exists():
            try:
                with open(self.save_path) as f:
                    data = json.load(f)
                    self.collected_ids = set(data.get('product_ids', []))
                    logger.info(f"Loaded {len(self.collected_ids)} existing product IDs")
            except Exception:
                pass
        
    async def create_page(self) -> Page:
        """Create a new page with anti-detection settings."""
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=config.scraper.user_agents[0],
            locale='ru-RU',
            timezone_id='Asia/Tashkent',
        )
        
        page = await context.new_page()
        
        # Anti-detection script
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['ru-RU', 'ru', 'en-US', 'en'] });
        """)
        
        return page
    
    def extract_product_id(self, url: str) -> Optional[int]:
        """Extract product ID from URL."""
        match = self.PRODUCT_URL_PATTERN.search(url)
        if match:
            return int(match.group(1))
        return None
    
    async def extract_products_from_page(self, page: Page) -> List[int]:
        """Extract all product IDs from current page."""
        try:
            await page.wait_for_selector('a[href*="/product/"]', timeout=10000)
        except Exception:
            return []
        
        links = await page.evaluate("""
            Array.from(document.querySelectorAll('a[href*="/product/"]'))
                .map(a => a.href)
        """)
        
        product_ids = []
        for link in set(links):
            pid = self.extract_product_id(link)
            if pid and pid not in self.collected_ids:
                product_ids.append(pid)
                self.collected_ids.add(pid)
        
        return product_ids
    
    async def get_total_pages(self, page: Page) -> int:
        """Get total number of pages from pagination."""
        try:
            pagination = await page.evaluate("""
                (() => {
                    const links = document.querySelectorAll('a[href*="currentPage="]');
                    let maxPage = 1;
                    links.forEach(link => {
                        const match = link.href.match(/currentPage=(\\d+)/);
                        if (match) {
                            const pageNum = parseInt(match[1]);
                            if (pageNum > maxPage) maxPage = pageNum;
                        }
                    });
                    return maxPage;
                })()
            """)
            return min(pagination, self.MAX_PAGES_PER_CATEGORY)
        except Exception:
            return 1
    
    async def get_subcategories(self, page: Page, current_slug: str) -> List[Dict]:
        """Extract subcategories from sidebar."""
        try:
            subcats = await page.evaluate("""
                (currentSlug) => {
                    const links = document.querySelectorAll('a[href*="/category/"]');
                    const result = [];
                    const seen = new Set();
                    
                    links.forEach(link => {
                        const href = link.href;
                        const match = href.match(/\\/category\\/([^?/]+)/);
                        if (match) {
                            const slug = match[1];
                            if (slug !== currentSlug && !seen.has(slug) && !slug.includes('--')) {
                                seen.add(slug);
                                result.push({
                                    slug: slug,
                                    title: link.textContent.trim().substring(0, 50)
                                });
                            }
                        }
                    });
                    return result;
                }
            """, current_slug)
            return subcats[:15]  # Limit subcategories
        except Exception as e:
            logger.warning(f"Error getting subcategories: {e}")
            return []
    
    async def crawl_category_page(self, category_slug: str, page_num: int, page: Page) -> List[int]:
        """Crawl a single page of a category."""
        product_ids = []
        
        try:
            url = f"{config.uzum_api.web_base_url}/ru/category/{category_slug}"
            if page_num > 1:
                url += f"?currentPage={page_num}"
            
            await page.goto(url, wait_until='load', timeout=60000)
            await asyncio.sleep(2)  # Wait for JS
            
            product_ids = await self.extract_products_from_page(page)
            self.stats.pages_crawled += 1
            self.stats.products_found += len(product_ids)
            
        except Exception as e:
            logger.error(f"Error on page {page_num}: {e}")
            self.stats.errors += 1
        
        return product_ids
    
    async def crawl_category_all_pages(
        self, 
        category_slug: str,
        max_pages: int = None,
        crawl_subcategories: bool = False
    ) -> List[int]:
        """Crawl ALL pages of a category."""
        if category_slug in self.crawled_categories:
            return []
        
        self.crawled_categories.add(category_slug)
        self.stats.categories_crawled += 1
        
        all_product_ids = []
        page = await self.create_page()
        
        try:
            # First page
            logger.info(f"📂 Category: {category_slug}")
            products = await self.crawl_category_page(category_slug, 1, page)
            all_product_ids.extend(products)
            
            if not products:
                logger.warning(f"No products found in {category_slug}")
                await page.close()
                return []
            
            # Get total pages
            total_pages = await self.get_total_pages(page)
            if max_pages:
                total_pages = min(total_pages, max_pages)
            
            logger.info(f"   Pages: {total_pages}, Found: {len(products)} products")
            
            # Crawl remaining pages
            for page_num in range(2, total_pages + 1):
                await asyncio.sleep(1)  # Polite delay
                products = await self.crawl_category_page(category_slug, page_num, page)
                all_product_ids.extend(products)
                logger.info(f"   Page {page_num}: +{len(products)} products")
                
                if not products:
                    break
            
            # Get subcategories
            subcategories = []
            if crawl_subcategories:
                subcategories = await self.get_subcategories(page, category_slug)
            
        finally:
            await page.close()
        
        # ✅ AUTO-SAVE after each category!
        await self.save_progress()
        
        # Push to Redis
        if all_product_ids and self.redis_client:
            await self.push_to_queue(all_product_ids)
        
        # Crawl subcategories
        if crawl_subcategories:
            for subcat in subcategories:
                await asyncio.sleep(1.5)
                sub_products = await self.crawl_category_all_pages(
                    subcat['slug'], 
                    max_pages=max_pages,
                    crawl_subcategories=False
                )
                all_product_ids.extend(sub_products)
        
        return all_product_ids
    
    async def crawl_until_target(
        self, 
        target: int = 1000,
        root_categories: List[str] = None
    ) -> Dict:
        """Crawl until we reach target number of products."""
        if root_categories is None:
            root_categories = [
                'elektronika-10020',
                'bytovaya-tekhnika-10004', 
                'odezhda-10014',
                'obuv-10013',
                'krasota-i-ukhod-10012',
                'zdorove-10009',
                'detskie-tovary-10007',
                'dom-i-sad-10340',
                'sport-i-otdykh-10015',
                'avtotovary-10002',
                'produkty-pitaniya-1821',
                'bytovaya-khimiya-10005',
            ]
        
        for category in root_categories:
            if len(self.collected_ids) >= target:
                logger.info(f"🎯 Target reached: {len(self.collected_ids)} products!")
                break
            
            await self.crawl_category_all_pages(category, crawl_subcategories=True)
            
            logger.info(f"📊 Progress: {len(self.collected_ids)}/{target} products")
        
        return self.get_stats()
    
    def get_stats(self) -> Dict:
        """Get current statistics."""
        return {
            "total_products": len(self.collected_ids),
            "categories_crawled": self.stats.categories_crawled,
            "pages_crawled": self.stats.pages_crawled,
            "errors": self.stats.errors,
            "duration_seconds": (datetime.now(timezone.utc) - self.stats.start_time).total_seconds()
        }
    
    async def push_to_queue(self, product_ids: List[int], queue_name: str = "product_ids"):
        """Push product IDs to Redis queue."""
        if not product_ids or not self.redis_client:
            return
            
        try:
            pipeline = self.redis_client.pipeline()
            for pid in product_ids:
                pipeline.rpush(queue_name, json.dumps({
                    "product_id": pid,
                    "queued_at": datetime.now(timezone.utc).isoformat()
                }))
            await pipeline.execute()
        except Exception as e:
            logger.warning(f"Redis push failed: {e}")
    
    async def save_progress(self):
        """Save collected IDs to file (auto-save)."""
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.save_path, 'w') as f:
            json.dump({
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "total_count": len(self.collected_ids),
                "stats": self.get_stats(),
                "product_ids": sorted(list(self.collected_ids))
            }, f, indent=2)
        
        logger.info(f"💾 Saved {len(self.collected_ids)} IDs to {self.save_path}")
    
    async def cleanup(self):
        """Close browser and Redis connections."""
        # Save before exit
        await self.save_progress()
        
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        if self.redis_client:
            await self.redis_client.aclose()


async def main():
    """CLI for CategoryCrawler."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Crawl Uzum.uz categories')
    parser.add_argument('--category', '-c', default=None,
                       help='Single category to crawl')
    parser.add_argument('--target', '-t', type=int, default=1000,
                       help='Target number of products')
    parser.add_argument('--max-pages', '-p', type=int, default=10,
                       help='Max pages per category')
    parser.add_argument('--subcategories', '-s', action='store_true',
                       help='Also crawl subcategories')
    parser.add_argument('--visible', '-v', action='store_true',
                       help='Show browser (for debugging)')
    
    args = parser.parse_args()
    
    crawler = CategoryCrawler(headless=not args.visible)
    await crawler.setup()
    
    try:
        if args.category:
            # Single category
            products = await crawler.crawl_category_all_pages(
                args.category,
                max_pages=args.max_pages,
                crawl_subcategories=args.subcategories
            )
            print(f"\n✅ Found {len(products)} products from {args.category}")
        else:
            # Crawl until target
            stats = await crawler.crawl_until_target(target=args.target)
            print(f"\n{'='*50}")
            print(f"✅ CRAWL COMPLETE")
            print(f"{'='*50}")
            for k, v in stats.items():
                print(f"   {k}: {v}")
            
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted! Saving progress...")
    finally:
        await crawler.cleanup()
        print(f"💾 Saved to: {crawler.save_path}")


if __name__ == "__main__":
    asyncio.run(main())
