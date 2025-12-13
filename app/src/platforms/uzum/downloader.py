"""
Uzum Downloader - High-performance ID range downloader with direct DB insert.

Optimized for speed:
- 150 concurrent connections (3x default)
- Direct PostgreSQL inserts (no JSON files)
- Batch inserts for performance
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Callable, List
from datetime import datetime, timezone
from dataclasses import dataclass, field

from .client import UzumClient
from .parser import UzumParser, parser

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from src.core.config import settings, RAW_STORAGE_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class DownloadStats:
    """Download statistics."""
    processed: int = 0
    found: int = 0
    empty: int = 0
    errors: int = 0
    db_inserts: int = 0
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_id: int = 0
    
    @property
    def rate(self) -> float:
        """Products processed per second."""
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        return self.processed / elapsed if elapsed > 0 else 0
    
    @property
    def success_rate(self) -> float:
        """Percentage of valid products found."""
        return (self.found / self.processed * 100) if self.processed > 0 else 0


class UzumDownloader:
    """
    High-performance downloader with direct PostgreSQL insert.
    
    Features:
    - 150 parallel async downloads (3x faster)
    - Direct database inserts (no JSON files)
    - Batch inserts for performance
    - Full product data with image URLs
    """
    
    def __init__(
        self,
        concurrency: int = 150,
        batch_size: int = 500,
        db_batch_size: int = 100,
        progress_file: Path = None
    ):
        self.concurrency = concurrency
        self.batch_size = batch_size
        self.db_batch_size = db_batch_size
        self.progress_file = progress_file or RAW_STORAGE_DIR / "download_progress.json"
        
        self.client = UzumClient(concurrency=concurrency)
        self.stats = DownloadStats()
        
        # Buffers for batch DB inserts (using dicts for deduplication)
        self._products_buffer: Dict[int, Dict] = {}
        self._sellers_buffer: Dict[int, Dict] = {}
        self._skus_buffer: Dict[int, Dict] = {}
        self._categories_buffer: Dict[int, Dict] = {}  # NEW: Categories buffer
    
    async def download_range(
        self,
        start_id: int = 1,
        end_id: int = 3000000,
        target: int = None,
        on_product: Callable = None,
        on_batch: Callable = None,
        resume: bool = True
    ) -> DownloadStats:
        """
        Download products in ID range and insert directly to PostgreSQL.
        """
        # Resume from progress
        if resume:
            progress = self._load_progress()
            if progress:
                start_id = progress.get("last_id", start_id)
                self.stats.found = progress.get("found", 0)
                logger.info(f"Resuming from ID {start_id} (found={self.stats.found})")
        
        await self.client.connect()
        
        try:
            current_id = start_id
            
            while current_id < end_id:
                # Check target
                if target and self.stats.found >= target:
                    logger.info(f"🎯 Target {target} reached!")
                    break
                
                # Create batch
                batch_ids = list(range(current_id, min(current_id + self.batch_size, end_id)))
                
                # Download batch
                products = await self.client.fetch_batch(batch_ids)
                
                # Update stats
                self.stats.processed += len(batch_ids)
                self.stats.found += len(products)
                self.stats.empty += len(batch_ids) - len(products)
                self.stats.last_id = current_id + self.batch_size
                
                # Process products - parse and buffer for DB insert
                for raw_data in products:
                    await self._process_product(raw_data)
                
                # Flush to DB if buffer gets big
                if len(self._products_buffer) >= self.db_batch_size:
                    await self._flush_to_db()
                
                # Progress log every 1000 IDs
                if self.stats.processed % 1000 == 0:
                    self._log_progress()
                    self._save_progress()
                
                current_id += self.batch_size
                
                # Small delay
                await asyncio.sleep(0.02)
        
        finally:
            # Flush remaining
            await self._flush_to_db()
            await self.client.close()
            self._save_progress()
        
        logger.info(f"\n✅ Done! Found {self.stats.found:,} products, inserted {self.stats.db_inserts:,} to DB")
        return self.stats
    
    async def _process_product(self, raw_data: Dict):
        """Parse product and add to buffers."""
        try:
            parsed = parser.parse_product(raw_data)
            if not parsed:
                return
            
            # Extract all photo URLs
            photos = []
            raw_photos = raw_data.get("payload", {}).get("data", {}).get("photos", [])
            for photo in raw_photos:
                photo_data = photo.get("photo", {})
                # Get highest resolution
                for size in ["800", "720", "540", "480", "240"]:
                    if size in photo_data:
                        high = photo_data[size].get("high")
                        if high:
                            photos.append(high)
                            break
            
            # Product data (deduplicated by ID)
            self._products_buffer[parsed.id] = {
                "id": parsed.id,
                "platform": "uzum",
                "title": parsed.title,
                "title_normalized": parser.normalize_title(parsed.title) if parsed.title else None,
                "title_ru": parsed.title_ru,
                "title_uz": parsed.title_uz,
                "category_id": parsed.category_id,
                "seller_id": parsed.seller_id,
                "rating": parsed.rating,
                "review_count": parsed.review_count,
                "order_count": parsed.order_count,
                "is_available": parsed.is_available,
                "total_available": parsed.total_available,
                "description": parsed.description,
                "photos": {"urls": photos} if photos else None,
                "video_url": parsed.video_url,
                "attributes": parsed.attributes,
                "characteristics": parsed.characteristics,
                "tags": parsed.tags,
                "is_eco": parsed.is_eco,
                "is_adult": parsed.is_adult,
                "is_perishable": parsed.is_perishable,
                "has_warranty": parsed.has_warranty,
                "warranty_info": parsed.warranty_info,
                "raw_data": raw_data.get("payload", {}).get("data", {}),
            }
            
            # Seller data (deduplicated by ID)
            if parsed.seller_data and parsed.seller_id:
                # Convert registration_date if needed
                reg_date = parsed.seller_data.get("registration_date")
                if reg_date and isinstance(reg_date, (int, float)):
                    # Convert Unix timestamp (milliseconds) to datetime
                    # Use naive datetime (without timezone) for PostgreSQL TIMESTAMP WITHOUT TIME ZONE
                    from datetime import datetime
                    reg_date = datetime.utcfromtimestamp(reg_date / 1000)

                self._sellers_buffer[parsed.seller_id] = {
                    "id": parsed.seller_id,
                    "platform": "uzum",
                    "title": parsed.seller_title,
                    "link": parsed.seller_data.get("link"),
                    "description": parsed.seller_data.get("description"),
                    "rating": parsed.seller_data.get("rating"),
                    "review_count": parsed.seller_data.get("reviews", 0),
                    "order_count": parsed.seller_data.get("orders", 0),
                    "total_products": parsed.seller_data.get("totalProducts", 0),
                    "is_official": parsed.seller_data.get("is_official", False),
                    "registration_date": reg_date,
                    "account_id": parsed.seller_data.get("account_id"),
                }
            
            # SKU data (deduplicated by ID)
            for sku_data in (parsed.skus or []):
                self._skus_buffer[sku_data['id']] = {
                    "id": sku_data['id'],
                    "product_id": parsed.id,
                    "full_price": sku_data.get('full_price'),
                    "purchase_price": sku_data.get('purchase_price'),
                    "discount_percent": sku_data.get('discount_percent'),
                    "available_amount": sku_data.get('available_amount', 0),
                    "barcode": sku_data.get('barcode'),
                    "characteristics": sku_data.get('characteristics'),
                }
            
            # NEW: Buffer categories (for FK constraint fix)
            if parsed.category_path:
                for cat in parsed.category_path:
                    self._categories_buffer[cat['id']] = {
                        "id": cat['id'],
                        "title": cat.get('title'),
                    }
        except Exception as e:
            self.stats.errors += 1
            logger.error(f"Error processing product: {e}")
    
    async def _flush_to_db(self):
        """Flush buffers to database."""
        if not self._products_buffer:
            return
        
        try:
            from src.core.database import get_session
            from src.core.bulk_ops import (
                bulk_upsert_products,
                bulk_upsert_sellers,
                bulk_upsert_skus,
                bulk_upsert_categories,  # NEW: Import categories function
            )
            
            async with get_session() as session:
                # Convert dicts to lists
                categories_list = list(self._categories_buffer.values())  # NEW
                sellers_list = list(self._sellers_buffer.values())
                products_list = list(self._products_buffer.values())
                skus_list = list(self._skus_buffer.values())
                
                # Use smaller chunk size to avoid param limit (32767)
                # 100 items * ~20 cols = 2000 params (safe)
                CHUNK_SIZE = 100
                
                # CRITICAL: Insert in correct dependency order to avoid FK violations
                # 1. Categories FIRST (no dependencies)
                # Use skip_on_contention=True to avoid deadlocks during continuous scraping
                # Categories are relatively static (only 4,349 total), so OK to skip on lock contention
                for i in range(0, len(categories_list), CHUNK_SIZE):
                    chunk = categories_list[i:i + CHUNK_SIZE]
                    if chunk:
                        await bulk_upsert_categories(session, chunk, "uzum", skip_on_contention=True)
                
                # 2. Sellers (no dependencies)
                for i in range(0, len(sellers_list), CHUNK_SIZE):
                    chunk = sellers_list[i:i + CHUNK_SIZE]
                    if chunk:
                        await bulk_upsert_sellers(session, chunk, "uzum")
                
                # 3. Products (depends on categories, sellers)
                for i in range(0, len(products_list), CHUNK_SIZE):
                    chunk = products_list[i:i + CHUNK_SIZE]
                    if chunk:
                        count = await bulk_upsert_products(session, chunk, "uzum")
                        self.stats.db_inserts += count
                
                # 4. SKUs (depends on products)
                for i in range(0, len(skus_list), CHUNK_SIZE):
                    chunk = skus_list[i:i + CHUNK_SIZE]
                    if chunk:
                        await bulk_upsert_skus(session, chunk)
                
                await session.commit()
                
                # ✅ Only clear buffers AFTER successful commit
                self._categories_buffer.clear()
                self._products_buffer.clear()
                self._sellers_buffer.clear()
                self._skus_buffer.clear()
            
        except Exception as e:
            # ✅ CRITICAL: Rollback transaction on error
            await session.rollback()
            
            # Calculate total items in buffers
            buffer_count = (
                len(self._categories_buffer) +
                len(self._products_buffer) +
                len(self._sellers_buffer) +
                len(self._skus_buffer)
            )
            
            logger.error(f"❌ DB flush error: {e}")
            logger.error(f"⚠️  Buffers NOT cleared - will retry {buffer_count} items on next flush")
            self.stats.errors += 1
            raise  # Re-raise to trigger retry logic
    
    def _log_progress(self):
        """Log current progress."""
        logger.info(
            f"ID {self.stats.last_id:,} | "
            f"Found: {self.stats.found:,} | "
            f"DB: {self.stats.db_inserts:,} | "
            f"Rate: {self.stats.rate:.0f}/sec | "
            f"Success: {self.stats.success_rate:.1f}%"
        )
    
    def _save_progress(self):
        """Save progress for resume."""
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.progress_file, 'w') as f:
            json.dump({
                "last_id": self.stats.last_id,
                "found": self.stats.found,
                "processed": self.stats.processed,
                "db_inserts": self.stats.db_inserts,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2)
    
    def _load_progress(self) -> Optional[Dict]:
        """Load progress from file."""
        if self.progress_file.exists():
            try:
                with open(self.progress_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return None


async def main():
    """CLI entry point."""
    import argparse
    
    arg_parser = argparse.ArgumentParser(description='Uzum ID Range Downloader')
    arg_parser.add_argument('--start', '-s', type=int, default=1, help='Start ID')
    arg_parser.add_argument('--end', '-e', type=int, default=3000000, help='End ID')
    arg_parser.add_argument('--target', '-t', type=int, default=None, help='Target count')
    arg_parser.add_argument('--concurrency', '-c', type=int, default=50, help='Concurrent requests')
    arg_parser.add_argument('--no-resume', action='store_true', help='Start fresh')
    
    args = arg_parser.parse_args()
    
    downloader = UzumDownloader(concurrency=args.concurrency)
    
    try:
        stats = await downloader.download_range(
            start_id=args.start,
            end_id=args.end,
            target=args.target,
            resume=not args.no_resume
        )
        
        print(f"\n{'='*50}")
        print(f"📊 Final Stats")
        print(f"{'='*50}")
        print(f"   Processed: {stats.processed:,}")
        print(f"   Found: {stats.found:,}")
        print(f"   DB Inserts: {stats.db_inserts:,}")
        print(f"   Success Rate: {stats.success_rate:.1f}%")
        print(f"   Rate: {stats.rate:.0f}/sec")
        
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted! Progress saved.")


if __name__ == "__main__":
    asyncio.run(main())

