"""
Base Platform - Abstract interface for marketplace platforms.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ProductData:
    """Parsed product data."""
    id: int
    title: str
    title_ru: Optional[str] = None
    title_uz: Optional[str] = None
    
    category_id: Optional[int] = None
    category_title: Optional[str] = None
    category_path: Optional[List[Dict]] = None
    
    seller_id: Optional[int] = None
    seller_title: Optional[str] = None
    seller_data: Optional[Dict] = None
    
    rating: Optional[float] = None
    review_count: int = 0
    order_count: int = 0
    
    is_available: bool = True
    total_available: int = 0
    
    description: Optional[str] = None
    photos: Optional[List[str]] = None
    attributes: Optional[Dict] = None
    characteristics: Optional[Dict] = None
    
    skus: List[Dict] = None
    
    raw_data: Optional[Dict] = None


class MarketplacePlatform(ABC):
    """
    Abstract base class for marketplace platforms.
    
    Implement this for each marketplace (Uzum, Wildberries, Ozon, etc.)
    """
    
    name: str = "unknown"
    api_base_url: str = ""
    
    @abstractmethod
    async def download_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        """
        Download raw product data from API.
        
        Args:
            product_id: Product ID to download
            
        Returns:
            Raw API response dict, or None if not found
        """
        pass
    
    @abstractmethod
    def parse_product(self, raw_data: Dict[str, Any]) -> Optional[ProductData]:
        """
        Parse raw API response into ProductData.
        
        Args:
            raw_data: Raw API response
            
        Returns:
            Parsed ProductData, or None if invalid
        """
        pass
    
    @abstractmethod
    async def download_range(
        self,
        start_id: int,
        end_id: int,
        concurrency: int = 50
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Download products in ID range.
        
        Args:
            start_id: Start product ID
            end_id: End product ID
            concurrency: Number of concurrent requests
            
        Yields:
            Raw product data dicts
        """
        pass
    
    @abstractmethod
    def get_id_range(self) -> tuple[int, int]:
        """
        Get valid product ID range for this platform.
        
        Returns:
            (min_id, max_id) tuple
        """
        pass
    
    def normalize_title(self, title: str) -> str:
        """Normalize product title for matching across sellers."""
        import re
        # Remove special characters, lowercase, collapse whitespace
        normalized = re.sub(r'[^\w\s]', '', title.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
