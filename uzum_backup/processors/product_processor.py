"""
Product Processor - Parses raw JSON and saves to PostgreSQL.

This module runs OFFLINE - no network access needed!
Can re-process saved JSON files if parsing logic changes.
"""
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
from decimal import Decimal
from dataclasses import dataclass

import psycopg2
from psycopg2.extras import Json, execute_values

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config, RAW_STORAGE_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ValidationAlert:
    """Validation issue detected in data."""
    alert_type: str
    severity: str  # info, warning, critical
    message: str
    details: Optional[Dict[str, Any]] = None


class DataValidator:
    """Validates scraped data for anomalies."""
    
    def __init__(self):
        self.config = config.validation
        
    def validate_price(
        self,
        new_price: float,
        old_price: Optional[float] = None,
        product_id: Optional[int] = None
    ) -> List[ValidationAlert]:
        """Validate price for anomalies."""
        alerts = []
        
        # Check if price is zero
        if new_price == 0:
            alerts.append(ValidationAlert(
                alert_type="zero_price",
                severity="critical",
                message="Price is 0 - likely parse error",
                details={"product_id": product_id, "price": new_price}
            ))
            return alerts
        
        # Check price bounds
        if new_price < self.config.min_valid_price:
            alerts.append(ValidationAlert(
                alert_type="price_too_low",
                severity="warning",
                message=f"Price {new_price} is below minimum threshold",
                details={"product_id": product_id, "min_threshold": self.config.min_valid_price}
            ))
        
        if new_price > self.config.max_valid_price:
            alerts.append(ValidationAlert(
                alert_type="price_too_high",
                severity="warning",
                message=f"Price {new_price} exceeds maximum threshold",
                details={"product_id": product_id, "max_threshold": self.config.max_valid_price}
            ))
        
        # Check price change (if we have old price)
        if old_price and old_price > 0:
            change_percent = ((new_price - old_price) / old_price) * 100
            
            if change_percent < -self.config.max_price_drop_percent:
                alerts.append(ValidationAlert(
                    alert_type="price_drop_suspicious",
                    severity="warning",
                    message=f"Price dropped {abs(change_percent):.1f}% - verify manually",
                    details={
                        "product_id": product_id,
                        "old_price": old_price,
                        "new_price": new_price,
                        "change_percent": change_percent
                    }
                ))
            
            if change_percent > self.config.max_price_increase_percent:
                alerts.append(ValidationAlert(
                    alert_type="price_increase_suspicious",
                    severity="warning",
                    message=f"Price increased {change_percent:.1f}% - verify manually",
                    details={
                        "product_id": product_id,
                        "old_price": old_price,
                        "new_price": new_price,
                        "change_percent": change_percent
                    }
                ))
        
        return alerts


class ProductProcessor:
    """
    Processes raw JSON files and saves clean data to PostgreSQL.
    
    Strategy:
    1. Read raw JSON from storage/raw/
    2. Extract and normalize data
    3. Validate data quality
    4. Upsert to PostgreSQL
    5. Record price history
    """
    
    def __init__(self):
        self.conn = None
        self.validator = DataValidator()
        
        # Stats
        self.processed = 0
        self.failed = 0
        self.alerts_created = 0
        
    def connect(self):
        """Connect to PostgreSQL."""
        self.conn = psycopg2.connect(config.database.url)
        logger.info("Connected to PostgreSQL")
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def extract_category_path(self, category_data: dict) -> List[dict]:
        """Extract full category hierarchy from nested structure."""
        path = []
        current = category_data
        
        while current:
            path.append({
                "id": current.get("id"),
                "title": current.get("title")
            })
            current = current.get("parent")
        
        return list(reversed(path))  # Root first
    
    def extract_images(self, photos: List[dict]) -> List[str]:
        """Extract high-quality image URLs from photos array."""
        images = []
        for photo in photos:
            photo_data = photo.get("photo", {})
            # Prefer 800px or 720px high quality
            for size in ["800", "720", "540"]:
                if size in photo_data:
                    url = photo_data[size].get("high")
                    if url:
                        images.append(url)
                        break
        return images
    
    def parse_product(self, raw_data: dict) -> Optional[dict]:
        """Parse raw JSON into clean product data."""
        try:
            # Navigate to actual data
            payload = raw_data.get("data", {})
            if "payload" in payload:
                product_data = payload.get("payload", {}).get("data", {})
            elif "payload" in raw_data:
                product_data = raw_data.get("payload", {}).get("data", {})
            else:
                product_data = payload
            
            if not product_data:
                logger.error("No product data found in payload")
                return None
            
            # Extract seller
            seller_data = product_data.get("seller", {})
            seller = {
                "id": seller_data.get("id"),
                "name": seller_data.get("title"),
                "link": seller_data.get("link"),
                "rating": seller_data.get("rating"),
                "reviews_count": seller_data.get("reviews"),
                "total_orders": seller_data.get("orders"),
                "is_official": seller_data.get("official", False),
                "registration_date": seller_data.get("registrationDate")
            }
            
            # Extract category
            category_data = product_data.get("category", {})
            category_path = self.extract_category_path(category_data)
            
            # Extract images
            photos = product_data.get("photos", [])
            images = self.extract_images(photos)
            
            # Extract SKUs
            skus = []
            for sku_data in product_data.get("skuList", []):
                # Build SKU name from characteristics
                chars = sku_data.get("characteristics", [])
                char_values = [c.get("value", "") for c in chars]
                sku_name = ", ".join(char_values) if char_values else None
                
                # Get stock info
                stock_info = sku_data.get("stock", {})
                
                sku = {
                    "id": sku_data.get("id"),
                    "name": sku_name,
                    "characteristics": chars,
                    "barcode": str(sku_data.get("barcode")) if sku_data.get("barcode") else None,
                    "full_price": sku_data.get("fullPrice"),
                    "sell_price": sku_data.get("purchasePrice"),
                    "available_amount": sku_data.get("availableAmount", 0),
                    "stock_type": stock_info.get("type"),
                    "delivery_days": stock_info.get("deliveryDays"),
                    "vat_rate": sku_data.get("vat", {}).get("vatRate", 0)
                }
                
                # Calculate discount
                if sku["full_price"] and sku["sell_price"] and sku["full_price"] > 0:
                    discount = ((sku["full_price"] - sku["sell_price"]) / sku["full_price"]) * 100
                    sku["discount_percent"] = round(discount, 1)
                else:
                    sku["discount_percent"] = 0
                
                skus.append(sku)
            
            # Build product
            product = {
                "id": product_data.get("id"),
                "title": product_data.get("title"),
                "title_ru": product_data.get("localizableTitle", {}).get("ru"),
                "title_uz": product_data.get("localizableTitle", {}).get("uz"),
                "description": product_data.get("description"),
                "category_id": category_data.get("id"),
                "category_path": category_path,
                "url": f"https://uzum.uz/ru/product/{product_data.get('id')}",
                "total_orders": product_data.get("ordersAmount", 0),
                "rating": product_data.get("rating"),
                "reviews_count": product_data.get("reviewsAmount", 0),
                "is_available": product_data.get("totalAvailableAmount", 0) > 0,
                "is_eco": product_data.get("isEco", False),
                "adult_category": product_data.get("adultCategory", False),
                "has_charity": product_data.get("charityCommission", 0) > 0,
                "images": images,
                "photos_count": len(photos),
                "specs": product_data.get("attributes", []),
                "tags": product_data.get("tags", []),
                "seller": seller,
                "skus": skus
            }
            
            return product
            
        except Exception as e:
            logger.error(f"Error parsing product: {e}")
            return None
    
    def upsert_category(self, category: dict, parent_id: Optional[int] = None, level: int = 0):
        """Upsert a category to database."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO categories (id, title, parent_id, level)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    parent_id = EXCLUDED.parent_id,
                    level = EXCLUDED.level,
                    updated_at = CURRENT_TIMESTAMP
            """, (category["id"], category["title"], parent_id, level))
    
    def upsert_seller(self, seller: dict):
        """Upsert seller to database."""
        with self.conn.cursor() as cur:
            # Convert registration date
            reg_date = None
            if seller.get("registration_date"):
                reg_date = datetime.fromtimestamp(seller["registration_date"] / 1000)
            
            cur.execute("""
                INSERT INTO sellers (id, name, link, rating, reviews_count, total_orders, is_official, registration_date, last_seen_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    link = EXCLUDED.link,
                    rating = EXCLUDED.rating,
                    reviews_count = EXCLUDED.reviews_count,
                    total_orders = EXCLUDED.total_orders,
                    is_official = EXCLUDED.is_official,
                    last_seen_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                seller["id"], seller["name"], seller["link"],
                seller["rating"], seller["reviews_count"], seller["total_orders"],
                seller["is_official"], reg_date
            ))
    
    def upsert_product(self, product: dict):
        """Upsert product to database."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO products (
                    id, title, title_ru, title_uz, description,
                    category_id, category_path, seller_id, url,
                    total_orders, rating, reviews_count,
                    is_available, is_eco, adult_category, has_charity,
                    images, photos_count, specs, tags, last_seen_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    total_orders = EXCLUDED.total_orders,
                    rating = EXCLUDED.rating,
                    reviews_count = EXCLUDED.reviews_count,
                    is_available = EXCLUDED.is_available,
                    images = EXCLUDED.images,
                    last_seen_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                product["id"], product["title"], product["title_ru"], product["title_uz"],
                product["description"], product["category_id"], Json(product["category_path"]),
                product["seller"]["id"], product["url"], product["total_orders"],
                product["rating"], product["reviews_count"], product["is_available"],
                product["is_eco"], product["adult_category"], product["has_charity"],
                Json(product["images"]), product["photos_count"],
                Json(product["specs"]), Json(product["tags"])
            ))
    
    def upsert_skus(self, product_id: int, seller_id: int, skus: List[dict]):
        """Upsert SKUs and record price history."""
        with self.conn.cursor() as cur:
            for sku in skus:
                # Get current price for comparison
                cur.execute("SELECT sell_price FROM skus WHERE id = %s", (sku["id"],))
                result = cur.fetchone()
                old_price = result[0] if result else None
                
                # Upsert SKU
                cur.execute("""
                    INSERT INTO skus (
                        id, product_id, name, characteristics, barcode,
                        full_price, sell_price, discount_percent,
                        available_amount, is_available, stock_type, delivery_days, vat_rate
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        full_price = EXCLUDED.full_price,
                        sell_price = EXCLUDED.sell_price,
                        discount_percent = EXCLUDED.discount_percent,
                        available_amount = EXCLUDED.available_amount,
                        is_available = EXCLUDED.is_available,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    sku["id"], product_id, sku["name"], Json(sku["characteristics"]),
                    sku["barcode"], sku["full_price"], sku["sell_price"],
                    sku["discount_percent"], sku["available_amount"],
                    sku["available_amount"] > 0, sku["stock_type"],
                    sku["delivery_days"], sku["vat_rate"]
                ))
                
                # Record price history
                new_price = sku["sell_price"]
                
                # Validate price change
                alerts = self.validator.validate_price(
                    new_price=new_price,
                    old_price=float(old_price) if old_price else None,
                    product_id=product_id
                )
                
                is_validated = len([a for a in alerts if a.severity in ("warning", "critical")]) == 0
                validation_flags = {"alerts": [a.__dict__ for a in alerts]} if alerts else None
                
                cur.execute("""
                    INSERT INTO price_history (
                        sku_id, product_id, seller_id,
                        price, old_price, discount_percent,
                        is_available, available_amount,
                        is_validated, validation_flags
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    sku["id"], product_id, seller_id,
                    new_price, sku["full_price"], sku["discount_percent"],
                    sku["available_amount"] > 0, sku["available_amount"],
                    is_validated, Json(validation_flags)
                ))
                
                # Create alerts in database
                for alert in alerts:
                    self.create_alert(alert, product_id, sku["id"], seller_id)
    
    def create_alert(
        self, 
        alert: ValidationAlert, 
        product_id: int, 
        sku_id: int, 
        seller_id: int
    ):
        """Create a data quality alert."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO data_alerts (
                    alert_type, severity, product_id, sku_id, seller_id, message, details
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                alert.alert_type, alert.severity,
                product_id, sku_id, seller_id,
                alert.message, Json(alert.details)
            ))
        self.alerts_created += 1
    
    def process_file(self, file_path: Path) -> bool:
        """Process a single raw JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            
            product = self.parse_product(raw_data)
            if not product:
                logger.warning(f"Could not parse {file_path}")
                self.failed += 1
                return False
            
            # Process categories
            for i, cat in enumerate(product["category_path"]):
                parent_id = product["category_path"][i-1]["id"] if i > 0 else None
                self.upsert_category(cat, parent_id, i)
            
            # Process seller
            self.upsert_seller(product["seller"])
            
            # Process product
            self.upsert_product(product)
            
            # Process SKUs and price history
            self.upsert_skus(product["id"], product["seller"]["id"], product["skus"])
            
            self.conn.commit()
            self.processed += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            self.conn.rollback()
            self.failed += 1
            return False
    
    def process_directory(self, date_str: Optional[str] = None):
        """Process all files in a date directory."""
        if date_str:
            dir_path = RAW_STORAGE_DIR / 'products' / date_str
        else:
            # Process today's files
            dir_path = RAW_STORAGE_DIR / 'products' / datetime.utcnow().strftime('%Y-%m-%d')
        
        if not dir_path.exists():
            logger.warning(f"Directory not found: {dir_path}")
            return
        
        json_files = list(dir_path.glob("*.json"))
        logger.info(f"Found {len(json_files)} files to process in {dir_path}")
        
        for i, file_path in enumerate(json_files):
            self.process_file(file_path)
            
            if (i + 1) % 100 == 0:
                logger.info(f"Progress: {i + 1}/{len(json_files)}")
        
        logger.info(f"Finished! Processed: {self.processed}, Failed: {self.failed}, Alerts: {self.alerts_created}")


def main():
    """Process raw JSON files."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Process raw JSON files')
    parser.add_argument('--date', '-d', help='Date to process (YYYY-MM-DD)')
    parser.add_argument('--file', '-f', help='Single file to process')
    
    args = parser.parse_args()
    
    processor = ProductProcessor()
    processor.connect()
    
    try:
        if args.file:
            processor.process_file(Path(args.file))
        else:
            processor.process_directory(args.date)
    finally:
        processor.close()


if __name__ == "__main__":
    main()
