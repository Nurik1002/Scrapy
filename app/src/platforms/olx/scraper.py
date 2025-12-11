"""
OLX.uz Platform Scraper

C2C Classifieds platform scraper based on research in scrape_researches/olx/
"""

import asyncio
import aiohttp
import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import random

logger = logging.getLogger(__name__)
debug_logger = logging.getLogger(f"{__name__}.debug")


@dataclass
class OLXConfig:
    """OLX scraper configuration"""
    base_url: str = "https://www.olx.uz"
    api_base: str = "https://www.olx.uz/api/v1"
    concurrency: int = 5
    min_delay: float = 2.0
    max_delay: float = 5.0
    max_pages: int = 25  # OLX limits to 25 pages per category
    timeout: int = 30
    retries: int = 3


class OLXClient:
    """HTTP client for OLX.uz API"""
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    ]
    
    def __init__(self, config: OLXConfig = None):
        self.config = config or OLXConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._request_count = 0
        self._last_request_time = 0.0
        
    async def __aenter__(self):
        await self._create_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
    async def _create_session(self):
        if self._session is not None:
            return
            
        connector = aiohttp.TCPConnector(limit=self.config.concurrency, ttl_dns_cache=300)
        
        headers = {
            "Accept": "application/json",
            "Accept-Language": "ru-RU,ru;q=0.9,uz;q=0.8",
            "User-Agent": random.choice(self.USER_AGENTS),
        }
        
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            headers=headers
        )
        self._semaphore = asyncio.Semaphore(self.config.concurrency)
        logger.info(f"OLX client initialized - concurrency: {self.config.concurrency}")
        
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
            
    async def _rate_limit(self):
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self.config.min_delay:
            delay = self.config.min_delay - time_since_last
            delay += random.uniform(0, self.config.max_delay - self.config.min_delay)
            await asyncio.sleep(delay)
            
        self._last_request_time = asyncio.get_event_loop().time()
        self._request_count += 1
        
    async def _fetch_json(self, url: str, params: Dict = None) -> Optional[Dict]:
        if not self._session:
            await self._create_session()
            
        await self._rate_limit()
        
        for attempt in range(self.config.retries):
            try:
                async with self._semaphore:
                    async with self._session.get(url, params=params) as response:
                        if response.status == 200:
                            # OLX returns application/x-json which aiohttp rejects
                            # So read as text and parse manually
                            text = await response.text()
                            data = json.loads(text)
                            debug_logger.debug(f"Got JSON from {url}: {len(str(data))} chars")
                            return data
                        elif response.status == 429:
                            wait_time = (attempt + 1) * 30
                            logger.warning(f"Rate limited on {url}, waiting {wait_time}s")
                            await asyncio.sleep(wait_time)
                        else:
                            logger.debug(f"HTTP {response.status} for {url}")
                            await asyncio.sleep(random.uniform(5, 15))
            except Exception as e:
                logger.debug(f"Error fetching {url}: {e}")
                await asyncio.sleep(random.uniform(5, 15))
                
        return None
        
    async def get_categories(self) -> List[Dict]:
        """Get all OLX categories"""
        # OLX doesn't have a public categories endpoint
        # Use hardcoded popular categories instead
        return [
            {"id": "transport", "name": "Transport"},
            {"id": "elektronika", "name": "Electronics"},
            {"id": "nedvizhimost", "name": "Real Estate"},
            {"id": "dom-i-sad", "name": "Home & Garden"},
            {"id": "lichnye-veschi", "name": "Personal Items"},
        ]
        
    async def get_listings(self, category_id: int = None, region_id: int = None, 
                          page: int = 1, filters: Dict = None) -> Optional[Dict]:
        """Get listings from OLX"""
        url = f"{self.config.api_base}/offers"
        
        params = {"page": page, "limit": 40}
        if category_id:
            params["category_id"] = category_id
        if region_id:
            params["region_id"] = region_id
        if filters:
            params.update(filters)
            
        return await self._fetch_json(url, params)
        
    async def get_listing_details(self, listing_id: int) -> Optional[Dict]:
        """Get detailed listing information including phone"""
        url = f"{self.config.api_base}/offers/{listing_id}"
        return await self._fetch_json(url)
        
    async def get_seller_phone(self, listing_id: int) -> Optional[str]:
        """Get seller phone number (requires authentication or captcha)"""
        url = f"{self.config.api_base}/offers/{listing_id}/phones"
        data = await self._fetch_json(url)
        
        if data and "phones" in data:
            phones = data["phones"]
            return phones[0] if phones else None
        return None


class OLXScraper:
    """OLX.uz scraper with database integration"""
    
    def __init__(self, client: OLXClient = None):
        self.client = client or OLXClient()
        self.stats = {
            "categories_scraped": 0,
            "listings_scraped": 0,
            "sellers_found": 0,
            "errors": 0,
            "start_time": None
        }
        
    async def __aenter__(self):
        await self.client.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.__aexit__(exc_type, exc_val, exc_tb)
        
    async def scrape_category(self, category_slug: str, max_pages: int = 25) -> List[Dict]:
        """Scrape all listings from a category"""
        listings = []
        
        for page in range(1, max_pages + 1):
            # Use category in URL path instead of parameter
            url = f"{self.client.config.api_base}/offers/"
            data = await self.client._fetch_json(url, params={"page": page, "limit": 40, "category_slug": category_slug})
            
            if not data or "data" not in data:
                break
                
            page_listings = data["data"]
            if not page_listings:
                break
                
            listings.extend(page_listings)
            logger.info(f"Category {category_slug} page {page}: {len(page_listings)} listings")
            
            # Check if there are more pages
            if len(page_listings) < 40:
                break
                
        self.stats["listings_scraped"] += len(listings)
        return listings
        
    async def run_full_scrape(self, max_categories: int = None, save_to_db: bool = True):
        """Run full OLX scrape"""
        self.stats["start_time"] = datetime.now(timezone.utc).isoformat()
        logger.info("Starting OLX full scrape...")
        
        # Get categories
        categories = await self.client.get_categories()
        logger.info(f"Found {len(categories)} categories")
        
        if max_categories:
            categories = categories[:max_categories]
            
        all_listings = []
        
        for cat in categories:
            try:
                cat_slug = cat.get("id")
                cat_name = cat.get("name", "Unknown")
                logger.info(f"Scraping category: {cat_name} (slug: {cat_slug})")
                
                listings = await self.scrape_category(cat_slug)
                all_listings.extend(listings)
                
                self.stats["categories_scraped"] += 1
                
                # Save to DB in batches
                if save_to_db and len(all_listings) >= 100:
                    await self._save_to_db(all_listings)
                    all_listings = []  # Clear after saving
                
            except Exception as e:
                logger.error(f"Error scraping category {cat.get('id')}: {e}")
                self.stats["errors"] += 1
        
        # Save any remaining listings
        if save_to_db and all_listings:
            await self._save_to_db(all_listings)
                
        logger.info(f"OLX scrape complete: {self.stats}")
        return all_listings
        
    async def _parse_listing(self, raw_listing: Dict) -> Dict:
        """Parse API listing to database format"""
        return {
            "external_id": str(raw_listing.get("id", "")),
            "source": "olx.uz",
            "category_path": raw_listing.get("category", {}).get("slug", "unknown"),
            "title": raw_listing.get("title", "Unknown Title"),
            "description": raw_listing.get("description", ""),
            "price": float(raw_listing.get("params", [{}])[0].get("value", {}).get("value", 0)) if raw_listing.get("params") else None,
            "currency": "UZS",
            "location": raw_listing.get("location", {}).get("name", ""),
            "url": raw_listing.get("url", ""),
            "images": raw_listing.get("photos", []),
            "attributes": {param.get("key"): param.get("value") for param in raw_listing.get("params", [])},
            "status": "active" if raw_listing.get("status") == "active" else "inactive",
        }
    
    async def _parse_seller(self, raw_listing: Dict) -> Optional[Dict]:
        """Parse seller data from listing"""
        user_data = raw_listing.get("user")
        if not user_data or not user_data.get("id"):
            return None  # No seller data available
            
        return {
            "external_id": str(user_data.get("id", "")),
            "source": "olx.uz",
            "name": user_data.get("name", "Unknown Seller"),
            "seller_type": user_data.get("type", "private"),
            "total_ads": user_data.get("seller_type", {}).get("count", 0),
            "registered_since": user_data.get("created", ""),
        }
    
    async def _save_to_db(self, listings: List[Dict]):
        """Save listings to database with sellers"""
        if not listings:
            return
        
        from ...core.database import get_session
        from .bulk_ops import bulk_upsert_olx_sellers, bulk_upsert_olx_products, get_seller_by_external_id
        
        sellers_to_insert = []
        products_to_insert = []
        
        async with get_session() as session:
            # First pass: collect unique sellers
            seller_map = {}
            for listing in listings:
                try:
                    seller_data = await self._parse_seller(listing)
                    if seller_data:  # Only process if seller data exists
                        seller_ext_id = seller_data["external_id"]
                        if seller_ext_id not in seller_map:
                            seller_map[seller_ext_id] = seller_data
                except Exception as e:
                    logger.debug(f"Error parsing seller: {e}")
            
            # Insert sellers
            if seller_map:
                sellers_to_insert = list(seller_map.values())
                await bulk_upsert_olx_sellers(session, sellers_to_insert)
                await session.commit()
            
            # Second pass: get seller IDs and prepare products
            for listing in listings:
                try:
                    product_data = await self._parse_listing(listing)
                    
                    # Get seller ID
                    user_data = listing.get("user", {})
                    seller_ext_id = str(user_data.get("id", ""))
                    if seller_ext_id:
                        seller_id = await get_seller_by_external_id(session, seller_ext_id)
                        product_data["seller_id"] = seller_id
                    
                    products_to_insert.append(product_data)
                except Exception as e:
                    logger.error(f"Error parsing product: {e}")
            
            # Insert products
            if products_to_insert:
                await bulk_upsert_olx_products(session, products_to_insert)
                await session.commit()
        
        logger.info(f"Saved {len(sellers_to_insert)} sellers and {len(products_to_insert)} products to DB")


async def run_olx_debug(max_categories: int = 3, save_to_db: bool = True):
    """Run OLX scraper in debug mode"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler(f"logs/olx_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
            logging.StreamHandler()
        ]
    )
    
    logger.info("=" * 60)
    logger.info("OLX SCRAPER DEBUG MODE")
    logger.info("=" * 60)
    
    async with OLXScraper() as scraper:
        listings = await scraper.run_full_scrape(max_categories=max_categories, save_to_db=False)
        
        logger.info(f"\nResults:")
        logger.info(f"  Categories: {scraper.stats['categories_scraped']}")
        logger.info(f"  Listings: {len(listings)}")
        logger.info(f"  Errors: {scraper.stats['errors']}")
        
        # Show sample listings
        for listing in listings[:3]:
            logger.info(f"\nSample listing: {listing.get('title', 'No title')[:50]}...")
            
    return listings


if __name__ == "__main__":
    asyncio.run(run_olx_debug(max_categories=2))
