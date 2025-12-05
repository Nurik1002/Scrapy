"""
Uzum Parser - Parse raw API responses into structured data.
"""
import re
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from ..base import ProductData

logger = logging.getLogger(__name__)


class UzumParser:
    """
    Parser for Uzum.uz API responses.
    
    Extracts and normalizes:
    - Product info
    - Seller info
    - Category hierarchy
    - SKUs with pricing
    """
    
    @staticmethod
    def parse_product(raw_data: Dict[str, Any]) -> Optional[ProductData]:
        """
        Parse raw API response into ProductData.
        
        Args:
            raw_data: Raw API response from /api/v2/product/{id}
            
        Returns:
            ProductData or None if invalid
        """
        try:
            payload = raw_data.get("payload", {})
            data = payload.get("data", {})
            
            if not data or not data.get("title"):
                return None
            
            # Parse category hierarchy
            category_path = []
            cat = data.get("category", {})
            category_id = cat.get("id") if cat else None
            category_title = cat.get("title") if cat else None
            
            while cat:
                category_path.insert(0, {
                    "id": cat.get("id"),
                    "title": cat.get("title"),
                })
                cat = cat.get("parent")
            
            # Parse seller
            seller = data.get("seller", {})
            seller_data = None
            if seller:
                seller_data = {
                    "id": seller.get("id"),
                    "title": seller.get("title"),
                    "link": seller.get("link"),
                    "rating": seller.get("rating"),
                    "reviews": seller.get("reviews", 0),
                    "orders": seller.get("orders", 0),
                    "is_official": seller.get("official", False),
                    "description": seller.get("description"),
                    "registration_date": seller.get("registrationDate"),
                    "account_id": seller.get("sellerAccountId"),
                }
            
            # Parse SKUs
            skus = []
            for sku in data.get("skuList", []):
                full_price = sku.get("fullPrice")
                purchase_price = sku.get("purchasePrice")
                
                # Calculate discount
                discount = 0
                if full_price and purchase_price and full_price > purchase_price:
                    discount = round((full_price - purchase_price) / full_price * 100, 2)
                
                skus.append({
                    "id": sku.get("id"),
                    "full_price": full_price,
                    "purchase_price": purchase_price,
                    "discount_percent": discount,
                    "available_amount": sku.get("availableAmount", 0),
                    "barcode": sku.get("barcode"),
                    "characteristics": sku.get("characteristics"),
                })
            
            # Parse photos
            photos = []
            for photo in data.get("photos", []):
                if isinstance(photo, dict) and photo.get("photoKey"):
                    photos.append(photo["photoKey"])
                elif isinstance(photo, str):
                    photos.append(photo)
            
            # Parse localized titles
            loc_title = data.get("localizableTitle", {})
            title_ru = loc_title.get("ru") if isinstance(loc_title, dict) else None
            title_uz = loc_title.get("uz") if isinstance(loc_title, dict) else None
            
            # Calculate total availability
            total_available = sum(sku.get("available_amount", 0) for sku in skus)
            
            return ProductData(
                id=data["id"],
                title=data["title"],
                title_ru=title_ru,
                title_uz=title_uz,
                
                category_id=category_id,
                category_title=category_title,
                category_path=category_path,
                
                seller_id=seller.get("id") if seller else None,
                seller_title=seller.get("title") if seller else None,
                seller_data=seller_data,
                
                rating=data.get("rating"),
                review_count=data.get("reviewsAmount", 0),
                order_count=data.get("ordersAmount", 0),
                
                is_available=total_available > 0,
                total_available=total_available,
                
                description=data.get("description"),
                photos=photos if photos else None,
                attributes=data.get("attributes"),
                characteristics=data.get("characteristics"),
                
                skus=skus,
                raw_data=raw_data,
            )
            
        except Exception as e:
            logger.error(f"Error parsing product: {e}")
            return None
    
    @staticmethod
    def normalize_title(title: str) -> str:
        """Normalize title for cross-seller matching."""
        if not title:
            return ""
        # Remove special chars, lowercase, collapse whitespace
        normalized = re.sub(r'[^\w\s]', '', title.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized[:500]  # Limit length


# Singleton
parser = UzumParser()
