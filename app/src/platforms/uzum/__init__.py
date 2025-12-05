"""
Uzum Platform - Implementation for Uzum.uz marketplace.
"""
from typing import Dict, Any, Optional, List, AsyncGenerator

from ..base import MarketplacePlatform, ProductData
from .client import UzumClient, get_client
from .parser import UzumParser, parser
from .downloader import UzumDownloader


class UzumPlatform(MarketplacePlatform):
    """
    Uzum.uz marketplace implementation.
    """
    
    name = "uzum"
    api_base_url = "https://api.uzum.uz/api/v2"
    
    ID_RANGE_START = 1
    ID_RANGE_END = 3000000
    
    def __init__(self, concurrency: int = 50):
        self.client = UzumClient(concurrency=concurrency)
        self.parser = parser
    
    async def download_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Download raw product data from API."""
        return await self.client.fetch_product(product_id)
    
    def parse_product(self, raw_data: Dict[str, Any]) -> Optional[ProductData]:
        """Parse raw API response into ProductData."""
        return self.parser.parse_product(raw_data)
    
    async def download_range(
        self,
        start_id: int,
        end_id: int,
        concurrency: int = 50
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Download products in ID range."""
        async for product in self.client.scan_range(start_id, end_id):
            yield product
    
    def get_id_range(self) -> tuple[int, int]:
        """Get valid product ID range."""
        return (self.ID_RANGE_START, self.ID_RANGE_END)


# Export all
__all__ = [
    "UzumPlatform",
    "UzumClient",
    "UzumParser",
    "UzumDownloader",
    "get_client",
    "parser",
]
