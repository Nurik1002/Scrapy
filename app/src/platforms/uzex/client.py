"""
UZEX API Client - Async client for government procurement APIs.
Uses browser session for authentication.
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

import aiohttp
from aiohttp import ClientTimeout, TCPConnector

from .session import get_session, UzexSession

logger = logging.getLogger(__name__)


class UzexClient:
    """
    Async client for UZEX Government Procurement APIs.
    
    3 API subdomains:
    - xarid-api-auction.uzex.uz - Auctions
    - xarid-api-shop.uzex.uz - E-shop & National shop
    - xarid-api-trade.uzex.uz - Products/Categories
    
    Uses Playwright-captured browser session for authentication.
    """
    
    AUCTION_API = "https://xarid-api-auction.uzex.uz"
    SHOP_API = "https://xarid-api-shop.uzex.uz"
    TRADE_API = "https://xarid-api-trade.uzex.uz"
    
    def __init__(self, timeout: int = 60, retries: int = 3, use_session: bool = True):
        self.timeout = timeout
        self.retries = retries
        self.use_session = use_session
        self._session: Optional[aiohttp.ClientSession] = None
        self._uzex_session: Optional[UzexSession] = None
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers with session cookies if available."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        if self._uzex_session and self._uzex_session.cookie_header:
            headers["Cookie"] = self._uzex_session.cookie_header
        return headers
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def connect(self):
        """Initialize connection with session capture."""
        if self._session is None:
            # Capture browser session first
            if self.use_session:
                self._uzex_session = get_session()
                await self._uzex_session.ensure_valid()
                logger.info(f"Session ready with {len(self._uzex_session.cookies)} cookies")
            
            connector = TCPConnector(limit=20, ttl_dns_cache=300)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=ClientTimeout(total=self.timeout),
            )
    
    async def close(self):
        """Close connection."""
        if self._session:
            await self._session.close()
            self._session = None
    
    # =========================================================================
    # AUCTION API
    # =========================================================================
    
    async def get_completed_auctions(
        self,
        from_idx: int = 1,
        to_idx: int = 100,
        **filters
    ) -> List[Dict]:
        """
        Get completed auction deals.
        
        Args:
            from_idx: Start index (1-based)
            to_idx: End index
            filters: Optional filters (lot_id, customer_name, start_date, end_date)
        """
        payload = {
            "region_ids": [],
            "district_ids": [],
            "from": from_idx,
            "to": to_idx,
            "lot_id": filters.get("lot_id"),
            "inn": filters.get("inn"),
            "customer_name": filters.get("customer_name"),
            "start_date": filters.get("start_date"),
            "end_date": filters.get("end_date"),
        }
        return await self._post(f"{self.AUCTION_API}/Common/GetCompletedDeals", payload)
    
    async def get_active_auctions(self, from_idx: int = 1, to_idx: int = 100) -> List[Dict]:
        """Get active (not completed) auctions."""
        payload = {
            "region_ids": [],
            "district_ids": [],
            "from": from_idx,
            "to": to_idx,
        }
        return await self._post(f"{self.AUCTION_API}/Common/GetNotCompletedDeals", payload)
    
    async def get_auction_products(self, lot_id: int) -> List[Dict]:
        """Get products/items for a specific auction lot."""
        url = f"{self.AUCTION_API}/Common/GetCompletedDealProducts/{lot_id}"
        return await self._get(url)
    
    # =========================================================================
    # SHOP API
    # =========================================================================
    
    async def get_completed_shop(
        self,
        from_idx: int = 1,
        to_idx: int = 100,
        national: bool = False
    ) -> List[Dict]:
        """
        Get completed shop deals.
        
        Args:
            national: If True, get national shop; if False, get e-shop
        """
        payload = {
            "region_ids": [],
            "display_on_shop": 0 if national else 1,
            "display_on_national": 1 if national else 0,
            "from": from_idx,
            "to": to_idx,
        }
        return await self._post(f"{self.SHOP_API}/Common/GetCompletedDeals", payload)
    
    async def get_active_shop(
        self,
        from_idx: int = 1,
        to_idx: int = 100,
        national: bool = False
    ) -> List[Dict]:
        """Get active shop deals."""
        payload = {
            "region_ids": [],
            "display_on_shop": 0 if national else 1,
            "display_on_national": 1 if national else 0,
            "from": from_idx,
            "to": to_idx,
        }
        return await self._post(f"{self.SHOP_API}/Common/GetNotCompletedDeals", payload)
    
    # =========================================================================
    # TRADE API (Products/Categories)
    # =========================================================================
    
    async def get_categories(self) -> List[Dict]:
        """Get all product categories."""
        return await self._get(f"{self.TRADE_API}/Lib/GetCategories")
    
    async def get_products(self, page: int = 1, count: int = 100) -> List[Dict]:
        """Get product catalog."""
        payload = {"page": page, "count": count}
        return await self._post(f"{self.TRADE_API}/Lib/GetProductsForInfo", payload)
    
    # =========================================================================
    # HTTP Methods
    # =========================================================================
    
    async def _get(self, url: str) -> Optional[List[Dict]]:
        """Make GET request with session headers."""
        headers = self._get_headers()
        for attempt in range(self.retries):
            try:
                async with self._session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    logger.warning(f"GET {url} returned {response.status}")
                    return None
            except Exception as e:
                if attempt == self.retries - 1:
                    logger.error(f"GET {url} failed: {e}")
                await asyncio.sleep(1 * (attempt + 1))
        return None
    
    async def _post(self, url: str, payload: Dict) -> Optional[List[Dict]]:
        """Make POST request with session headers."""
        headers = self._get_headers()
        for attempt in range(self.retries):
            try:
                async with self._session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    logger.warning(f"POST {url} returned {response.status}")
                    return None
            except Exception as e:
                if attempt == self.retries - 1:
                    logger.error(f"POST {url} failed: {e}")
                await asyncio.sleep(1 * (attempt + 1))
        return None


# Singleton
_client: Optional[UzexClient] = None


def get_client() -> UzexClient:
    """Get or create UZEX client."""
    global _client
    if _client is None:
        _client = UzexClient()
    return _client
