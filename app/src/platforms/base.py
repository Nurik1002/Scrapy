"""
Base Platform - Abstract interface for marketplace platforms.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

logger = logging.getLogger(__name__)

# Create debug logger for detailed troubleshooting
debug_logger = logging.getLogger(f"{__name__}.debug")


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
    video_url: Optional[str] = None
    attributes: Optional[Dict] = None
    characteristics: Optional[Dict] = None
    tags: Optional[List[str]] = None

    # Product flags
    is_eco: bool = False
    is_adult: bool = False
    is_perishable: bool = False
    has_warranty: bool = False
    warranty_info: Optional[str] = None

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
        debug_logger.debug(
            f"[{self.name}] download_product called with product_id: {product_id}"
        )
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
        debug_logger.debug(
            f"[{self.name}] parse_product called with raw_data size: {len(str(raw_data)) if raw_data else 0} chars"
        )
        pass

    @abstractmethod
    async def download_range(
        self, start_id: int, end_id: int, concurrency: int = 50
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
        debug_logger.debug(
            f"[{self.name}] download_range called: start_id={start_id}, end_id={end_id}, concurrency={concurrency}"
        )
        debug_logger.debug(
            f"[{self.name}] Expected to process {end_id - start_id + 1} products"
        )
        pass

    @abstractmethod
    def get_id_range(self) -> tuple[int, int]:
        """
        Get valid product ID range for this platform.

        Returns:
            (min_id, max_id) tuple
        """
        debug_logger.debug(f"[{self.name}] get_id_range called")
        pass

    def normalize_title(self, title: str) -> str:
        """Normalize product title for matching across sellers."""
        debug_logger.debug(
            f"[{self.name}] Normalizing title: '{title}' (length: {len(title)})"
        )
        import re

        # Remove special characters, lowercase, collapse whitespace
        normalized = re.sub(r"[^\w\s]", "", title.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        debug_logger.debug(
            f"[{self.name}] Normalized title: '{normalized}' (length: {len(normalized)})"
        )
        return normalized
