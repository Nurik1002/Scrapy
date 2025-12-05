"""
Uzum API Client - Fast async client for Uzum.uz API.
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

import aiohttp
from aiohttp import ClientTimeout, TCPConnector

logger = logging.getLogger(__name__)


class UzumClient:
    """
    Async client for Uzum.uz API.
    
    Features:
    - Connection pooling
    - Automatic retries
    - Rate limiting
    - Concurrent downloads
    """
    
    API_BASE = "https://api.uzum.uz/api/v2"
    PRODUCT_URL = f"{API_BASE}/product/{{product_id}}"
    
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }
    
    def __init__(
        self,
        concurrency: int = 500,  # Scaled for 16-core server (was 150)
        timeout: int = 15,
        retries: int = 3,
        min_sleep: float = 0.01, # Keep-alive sleep
        max_sleep: float = 0.1,  # Random jitter
    ):
        self.concurrency = concurrency
        self.timeout = timeout
        self.retries = retries
        self.min_sleep = min_sleep
        self.max_sleep = max_sleep
        self._session: Optional[aiohttp.ClientSession] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def connect(self):
        """Initialize optimized connection pool for high-throughput."""
        if self._session is None:
            connector = TCPConnector(
                limit=self.concurrency,
                limit_per_host=self.concurrency,
                ttl_dns_cache=300,
                keepalive_timeout=30,
                enable_cleanup_closed=True,
                force_close=False,
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=ClientTimeout(total=self.timeout),
                headers=self.DEFAULT_HEADERS,
            )
            self._semaphore = asyncio.Semaphore(self.concurrency)
    
    async def close(self):
        """Close connection pool."""
        if self._session:
            await self._session.close()
            self._session = None
    
    async def fetch_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Fetch with smart rate limiting."""
        if self._session is None:
            await self.connect()
        
        url = self.PRODUCT_URL.format(product_id=product_id)
        
        # Smart sleep to avoid pattern detection
        import random
        await asyncio.sleep(random.uniform(self.min_sleep, self.max_sleep))
        
        for attempt in range(self.retries):
            try:
                async with self._semaphore:
                    async with self._session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            payload = data.get("payload", {}).get("data", {})
                            if payload and payload.get("title"):
                                return data
                            return None
                        elif response.status == 429: # Rate limit
                            wait = (attempt + 1) * 2
                            logger.warning(f"Rate limited (429). Waiting {wait}s...")
                            await asyncio.sleep(wait)
                            continue
                        elif response.status == 404:
                            return None
                            
                        return None
            except asyncio.TimeoutError:
                if attempt == self.retries - 1:
                    logger.debug(f"Timeout for product {product_id}")
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.debug(f"Error fetching {product_id}: {e}")
                await asyncio.sleep(0.5)
        
        return None
    
    async def fetch_batch(self, product_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Fetch multiple products concurrently.
        
        Args:
            product_ids: List of product IDs
            
        Returns:
            List of raw API responses (only valid ones)
        """
        tasks = [self.fetch_product(pid) for pid in product_ids]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]
    
    async def scan_range(
        self,
        start_id: int,
        end_id: int,
        batch_size: int = 500,
        on_batch: callable = None
    ):
        """
        Scan product ID range and yield valid products.
        
        Args:
            start_id: Starting product ID
            end_id: Ending product ID
            batch_size: Products per batch
            on_batch: Callback function(products, stats) called after each batch
            
        Yields:
            Valid product data dicts
        """
        current_id = start_id
        stats = {
            "processed": 0,
            "found": 0,
            "empty": 0,
            "start_time": datetime.now(timezone.utc),
        }
        
        while current_id < end_id:
            batch_ids = list(range(current_id, min(current_id + batch_size, end_id)))
            products = await self.fetch_batch(batch_ids)
            
            stats["processed"] += len(batch_ids)
            stats["found"] += len(products)
            stats["empty"] += len(batch_ids) - len(products)
            
            for product in products:
                yield product
            
            if on_batch:
                await on_batch(products, stats.copy())
            
            current_id += batch_size
            
            # Minimal delay between batches
            await asyncio.sleep(0.01)  # 10ms (reduced from 50ms)


# Singleton client
_client: Optional[UzumClient] = None


def get_client(concurrency: int = 50) -> UzumClient:
    """Get or create Uzum client."""
    global _client
    if _client is None:
        _client = UzumClient(concurrency=concurrency)
    return _client
