"""
Product Downloader - Fetches raw JSON from Uzum.uz API.

Uses proxy rotation and human-like delays.
Saves raw JSON to storage/raw/ for later processing.
"""
import asyncio
import json
import random
import time
import logging
from typing import Optional, List
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

import aiohttp
import redis.asyncio as redis

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config, RAW_STORAGE_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    """Result of downloading a product."""
    product_id: int
    success: bool
    http_status: Optional[int] = None
    file_path: Optional[str] = None
    error: Optional[str] = None
    response_time_ms: Optional[int] = None


class SmartDelayManager:
    """Manages human-like delays between requests."""
    
    def __init__(
        self,
        min_delay: float = 2.0,
        max_delay: float = 5.0,
        reading_pause_chance: float = 0.1,
        reading_pause_range: tuple = (10.0, 30.0)
    ):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.reading_pause_chance = reading_pause_chance
        self.reading_pause_range = reading_pause_range
        self.request_times: List[float] = []
        
    async def wait(self):
        """Wait with human-like variability."""
        delay = random.uniform(self.min_delay, self.max_delay)
        
        # 10% chance of "reading" pause
        if random.random() < self.reading_pause_chance:
            delay += random.uniform(*self.reading_pause_range)
            logger.debug(f"Adding reading pause, total delay: {delay:.1f}s")
        
        # Rate limiting: if too many recent requests, slow down
        now = time.time()
        recent_requests = [t for t in self.request_times if now - t < 60]
        if len(recent_requests) > config.scraper.requests_per_minute:
            extra_delay = 60 - (now - recent_requests[0])
            if extra_delay > 0:
                delay += extra_delay
                logger.warning(f"Rate limiting: adding {extra_delay:.1f}s delay")
        
        await asyncio.sleep(delay)
        self.request_times.append(time.time())
        
        # Cleanup old timestamps
        self.request_times = [t for t in self.request_times if now - t < 120]


class ProxyManager:
    """Manages proxy rotation for requests."""
    
    def __init__(self):
        self.config = config.proxy
        self.request_count = 0
        self.failed_requests = 0
        
    def get_proxy(self, session_id: Optional[str] = None) -> Optional[str]:
        """Get proxy URL with rotation."""
        if not self.config.enabled:
            return None
        
        # Generate random session ID for rotation
        if session_id is None:
            session_id = str(random.randint(100000, 999999))
        
        return self.config.get_url(session_id)
    
    def report_success(self):
        self.request_count += 1
        
    def report_failure(self):
        self.request_count += 1
        self.failed_requests += 1


class ProductDownloader:
    """
    Downloads product data from Uzum.uz API.
    
    Strategy:
    1. Pop product IDs from Redis queue
    2. Fetch JSON from API with proxy rotation
    3. Save raw JSON to storage/raw/
    4. Track download results
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.delay_manager = SmartDelayManager(
            min_delay=config.scraper.min_delay,
            max_delay=config.scraper.max_delay,
            reading_pause_chance=config.scraper.reading_pause_chance
        )
        self.proxy_manager = ProxyManager()
        
        # Stats
        self.downloaded = 0
        self.failed = 0
        
    async def setup(self):
        """Initialize connections."""
        self.redis_client = await redis.from_url(config.redis.url)
        
        # Create session with headers
        headers = {
            'Accept': 'application/json',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            'User-Agent': random.choice(config.scraper.user_agents),
            'Referer': 'https://uzum.uz/',
            'Origin': 'https://uzum.uz',
        }
        
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        
        logger.info("ProductDownloader initialized")
    
    def get_storage_path(self, product_id: int) -> Path:
        """Get storage path for a product JSON file."""
        date_str = datetime.utcnow().strftime('%Y-%m-%d')
        path = RAW_STORAGE_DIR / 'products' / date_str
        path.mkdir(parents=True, exist_ok=True)
        return path / f"{product_id}.json"
    
    async def download_product(self, product_id: int) -> DownloadResult:
        """Download a single product from API."""
        url = config.uzum_api.get_product_url(product_id)
        start_time = time.time()
        
        try:
            # Get proxy for this request
            proxy = self.proxy_manager.get_proxy()
            
            async with self.session.get(url, proxy=proxy) as response:
                elapsed_ms = int((time.time() - start_time) * 1000)
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Save raw JSON
                    file_path = self.get_storage_path(product_id)
                    
                    # Add metadata
                    raw_data = {
                        "product_id": product_id,
                        "scraped_at": datetime.utcnow().isoformat(),
                        "http_status": response.status,
                        "response_time_ms": elapsed_ms,
                        "data": data
                    }
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(raw_data, f, ensure_ascii=False, indent=2)
                    
                    self.proxy_manager.report_success()
                    self.downloaded += 1
                    
                    logger.info(f"Downloaded product {product_id} ({elapsed_ms}ms)")
                    
                    return DownloadResult(
                        product_id=product_id,
                        success=True,
                        http_status=response.status,
                        file_path=str(file_path),
                        response_time_ms=elapsed_ms
                    )
                    
                elif response.status == 404:
                    logger.warning(f"Product {product_id} not found (404)")
                    return DownloadResult(
                        product_id=product_id,
                        success=False,
                        http_status=response.status,
                        error="Product not found"
                    )
                    
                else:
                    error = f"HTTP {response.status}"
                    logger.warning(f"Failed to download {product_id}: {error}")
                    self.proxy_manager.report_failure()
                    self.failed += 1
                    
                    return DownloadResult(
                        product_id=product_id,
                        success=False,
                        http_status=response.status,
                        error=error
                    )
                    
        except asyncio.TimeoutError:
            self.failed += 1
            return DownloadResult(
                product_id=product_id,
                success=False,
                error="Timeout"
            )
            
        except Exception as e:
            self.failed += 1
            logger.error(f"Error downloading {product_id}: {e}")
            return DownloadResult(
                product_id=product_id,
                success=False,
                error=str(e)
            )
    
    async def download_with_retry(
        self, 
        product_id: int, 
        max_retries: int = 3
    ) -> DownloadResult:
        """Download with exponential backoff retry."""
        for attempt in range(max_retries):
            result = await self.download_product(product_id)
            
            if result.success:
                return result
            
            # Don't retry 404s
            if result.http_status == 404:
                return result
            
            # Exponential backoff
            if attempt < max_retries - 1:
                delay = config.scraper.retry_base_delay * (2 ** attempt)
                jitter = random.uniform(0, delay * 0.3)
                logger.info(f"Retry {attempt + 1}/{max_retries} for {product_id} in {delay + jitter:.1f}s")
                await asyncio.sleep(delay + jitter)
        
        return result
    
    async def pop_from_queue(self, queue_name: str = "product_ids") -> Optional[int]:
        """Pop a product ID from Redis queue."""
        data = await self.redis_client.lpop(queue_name)
        if data:
            item = json.loads(data)
            return item.get('product_id')
        return None
    
    async def get_queue_length(self, queue_name: str = "product_ids") -> int:
        """Get current queue length."""
        return await self.redis_client.llen(queue_name)
    
    async def process_queue(
        self, 
        queue_name: str = "product_ids",
        limit: Optional[int] = None
    ):
        """Process all items in queue."""
        processed = 0
        
        while True:
            # Check limit
            if limit and processed >= limit:
                logger.info(f"Reached limit of {limit} products")
                break
            
            # Pop from queue
            product_id = await self.pop_from_queue(queue_name)
            if product_id is None:
                logger.info("Queue empty, stopping")
                break
            
            # Download with retry
            result = await self.download_with_retry(product_id)
            processed += 1
            
            # Human-like delay
            await self.delay_manager.wait()
            
            # Progress log
            if processed % 10 == 0:
                queue_len = await self.get_queue_length(queue_name)
                logger.info(f"Progress: {processed} done, {queue_len} remaining")
        
        logger.info(f"Finished! Downloaded: {self.downloaded}, Failed: {self.failed}")
    
    async def download_list(self, product_ids: List[int]) -> List[DownloadResult]:
        """Download a specific list of product IDs."""
        results = []
        
        for i, product_id in enumerate(product_ids):
            result = await self.download_with_retry(product_id)
            results.append(result)
            
            # Human-like delay (except for last item)
            if i < len(product_ids) - 1:
                await self.delay_manager.wait()
            
            # Progress log
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{len(product_ids)}")
        
        return results
    
    async def cleanup(self):
        """Close connections."""
        if self.session:
            await self.session.close()
        if self.redis_client:
            await self.redis_client.close()


async def main():
    """Example usage of ProductDownloader."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Download products from Uzum.uz API')
    parser.add_argument('--queue', action='store_true',
                       help='Process from Redis queue')
    parser.add_argument('--ids', nargs='+', type=int,
                       help='Specific product IDs to download')
    parser.add_argument('--limit', '-l', type=int, default=None,
                       help='Limit number of downloads')
    
    args = parser.parse_args()
    
    downloader = ProductDownloader()
    await downloader.setup()
    
    try:
        if args.queue:
            await downloader.process_queue(limit=args.limit)
            
        elif args.ids:
            results = await downloader.download_list(args.ids)
            for r in results:
                status = "✓" if r.success else "✗"
                print(f"{status} {r.product_id}: {r.file_path or r.error}")
                
        else:
            # Demo: download a single product
            result = await downloader.download_product(1772350)
            print(f"Result: {result}")
            
    finally:
        await downloader.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
