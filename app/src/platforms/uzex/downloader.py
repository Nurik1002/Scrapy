"""
UZEX Downloader - Download lots and items from UZEX APIs.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Callable
from datetime import datetime, timezone
from dataclasses import dataclass, field

from .client import UzexClient, get_client
from .parser import UzexParser, parser, LotData

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from src.core.config import RAW_STORAGE_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class DownloadStats:
    """Download statistics."""
    processed: int = 0
    found: int = 0
    errors: int = 0
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def rate(self) -> float:
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        return self.processed / elapsed if elapsed > 0 else 0


class UzexDownloader:
    """
    Download lots and items from UZEX APIs.
    
    Supports:
    - Auctions (completed/active)
    - E-shop (completed/active)
    - National shop (completed/active)
    - Product catalog
    - Categories
    """
    
    LOT_TYPES = {
        "auction": {"completed": "get_completed_auctions", "active": "get_active_auctions"},
        "shop": {"completed": "get_completed_shop", "active": "get_active_shop"},
        "national": {"completed": "get_completed_shop", "active": "get_active_shop"},
    }
    
    def __init__(self, batch_size: int = 100, save_raw: bool = True, db_batch_size: int = 100):
        self.batch_size = batch_size
        self.save_raw = save_raw
        self.db_batch_size = db_batch_size
        self.client = UzexClient()
        self.stats = DownloadStats()
        self._save_dir: Optional[Path] = None

        # Buffers for batch DB inserts (using dicts for deduplication)
        self._lots_buffer: Dict[int, Dict] = {}
        self._items_buffer: List[Dict] = []
        self.db_inserts = 0
    
    async def download_lots(
        self,
        lot_type: str = "auction",
        status: str = "completed",
        target: int = None,
        start_from: int = 1,
        resume: bool = True,
        skip_existing: bool = True,
        on_lot: Callable[[LotData], None] = None,
    ) -> DownloadStats:
        """
        Download lots of a specific type.
        
        Args:
            lot_type: Type of lots (auction, shop, national)
            status: Status (completed, active)
            target: Stop after N lots
            start_from: Start index
            resume: Continue from last checkpoint
            skip_existing: Skip already-downloaded lots
            on_lot: Callback for each lot
        """
        from src.core.checkpoint import get_checkpoint_manager
        
        logger.info(f"Downloading {status} {lot_type} lots...")
        
        # Initialize checkpoint manager
        checkpoint = await get_checkpoint_manager("uzex", f"{lot_type}_{status}")
        
        # Resume from checkpoint if available
        if resume:
            saved = await checkpoint.load_checkpoint()
            if saved:
                start_from = saved.get("last_index", 1)
                # DON'T load found/processed counts - they're cumulative totals
                # We want to count NEW lots in THIS run, not total from all time
                logger.info(f"📍 Resuming from index {start_from}")
        
        # Setup save directory
        if self.save_raw:
            self._save_dir = RAW_STORAGE_DIR / "uzex" / lot_type / datetime.now().strftime("%Y-%m-%d")
            self._save_dir.mkdir(parents=True, exist_ok=True)
        
        await self.client.connect()
        
        try:
            from_idx = start_from
            total_count = None
            
            while True:
                # Check target
                if target and self.stats.found >= target:
                    logger.info(f"🎯 Target {target} reached!")
                    break
                
                # Fetch batch
                to_idx = from_idx + self.batch_size - 1
                
                if lot_type == "auction":
                    if status == "completed":
                        data = await self.client.get_completed_auctions(from_idx, to_idx)
                    else:
                        data = await self.client.get_active_auctions(from_idx, to_idx)
                else:
                    national = (lot_type == "national")
                    if status == "completed":
                        data = await self.client.get_completed_shop(from_idx, to_idx, national)
                    else:
                        data = await self.client.get_active_shop(from_idx, to_idx, national)
                
                if not data:
                    logger.info("No more data.")
                    break
                
                # Get total count from first result
                if total_count is None and data:
                    total_count = data[0].get("total_count", 0)
                    logger.info(f"Total available: {total_count:,}")
                
                # Process lots
                for item in data:
                    lot_id = item.get("lot_id")
                    
                    # Skip if already seen
                    if skip_existing and await checkpoint.is_seen(lot_id):
                        continue
                    
                    lot = parser.parse_lot(item, lot_type, status)
                    if lot:
                        self.stats.found += 1
                        
                        # Fetch lot items for auctions
                        if lot_type == "auction" and status == "completed":
                            items = await self.client.get_auction_products(lot.id)
                            if items:
                                lot.items = parser.parse_lot_items(items)
                        
                        # Mark as seen
                        await checkpoint.mark_seen([lot_id])
                        
                        # Save raw
                        if self.save_raw:
                            await self._save_raw(lot)

                        # Process for DB insertion
                        self._process_lot(lot)

                        # Callback
                        if on_lot:
                            on_lot(lot)

                self.stats.processed += len(data)

                # Flush to DB if buffer gets big
                if len(self._lots_buffer) >= self.db_batch_size:
                    await self._flush_to_db()
                
                # Save checkpoint every batch
                await checkpoint.save_checkpoint({
                    "last_index": from_idx + self.batch_size,
                    "found": self.stats.found,
                    "processed": self.stats.processed,
                    "total_available": total_count,
                })
                
                # Log progress
                logger.info(
                    f"Progress: {self.stats.found:,} lots | "
                    f"Rate: {self.stats.rate:.1f}/sec"
                )
                
                # Move to next batch
                from_idx += self.batch_size
                
                # Small delay
                await asyncio.sleep(0.1)
                
                # Stop if we've processed all
                if total_count and from_idx > total_count:
                    break
        
        finally:
            # Flush remaining lots to DB
            await self._flush_to_db()
            await self.client.close()
            await checkpoint.close()

        logger.info(f"✅ Done! Found {self.stats.found:,} lots, inserted {self.db_inserts:,} to DB")
        return self.stats
    
    async def download_categories(self) -> List[Dict]:
        """Download all categories."""
        await self.client.connect()
        try:
            categories = await self.client.get_categories()
            if categories:
                logger.info(f"Downloaded {len(categories)} categories")
                if self.save_raw:
                    save_dir = RAW_STORAGE_DIR / "uzex"
                    save_dir.mkdir(parents=True, exist_ok=True)
                    with open(save_dir / "categories.json", 'w', encoding='utf-8') as f:
                        json.dump(categories, f, ensure_ascii=False, indent=2)
            return categories or []
        finally:
            await self.client.close()
    
    async def download_products(self, max_pages: int = 100) -> List[Dict]:
        """Download product catalog."""
        await self.client.connect()
        all_products = []
        try:
            for page in range(1, max_pages + 1):
                products = await self.client.get_products(page)
                if not products:
                    break
                all_products.extend(products)
                logger.info(f"Page {page}: {len(all_products)} products total")
                await asyncio.sleep(0.1)
            
            if self.save_raw and all_products:
                save_dir = RAW_STORAGE_DIR / "uzex"
                save_dir.mkdir(parents=True, exist_ok=True)
                with open(save_dir / "products.json", 'w', encoding='utf-8') as f:
                    json.dump(all_products, f, ensure_ascii=False, indent=2)
            
            return all_products
        finally:
            await self.client.close()
    
    async def _save_raw(self, lot: LotData):
        """Save lot to JSON file."""
        try:
            if self._save_dir:
                filepath = self._save_dir / f"{lot.id}.json"
                data = {
                    "lot": lot.raw_data,
                    "items": [
                        {
                            "order_num": i.order_num,
                            "product_name": i.product_name,
                            "description": i.description,
                            "quantity": i.quantity,
                            "price": i.price,
                            "cost": i.cost,
                            "country_name": i.country_name,
                            "properties": i.properties,
                        }
                        for i in lot.items
                    ]
                }
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.stats.errors += 1
            logger.error(f"Save error: {e}")

    def _process_lot(self, lot: LotData):
        """Convert LotData to dict and add to buffers."""
        try:
            # Add lot to buffer (deduplicated by ID)
            self._lots_buffer[lot.id] = {
                "id": lot.id,
                "display_no": lot.display_no,
                "lot_type": lot.lot_type,
                "status": lot.status,
                "is_budget": lot.is_budget,
                "type_name": lot.type_name,
                "start_cost": lot.start_cost,
                "deal_cost": lot.deal_cost,
                "currency_name": lot.currency_name,
                "customer_name": lot.customer_name,
                "customer_inn": lot.customer_inn,
                "provider_name": lot.provider_name,
                "provider_inn": lot.provider_inn,
                "deal_id": lot.deal_id,
                "deal_date": lot.deal_date,
                "category_name": lot.category_name,
                "pcp_count": lot.pcp_count,
                "lot_start_date": lot.lot_start_date,
                "lot_end_date": lot.lot_end_date,
                "kazna_status": lot.kazna_status,
                "raw_data": lot.raw_data,
            }

            # Add items to buffer
            if lot.items:
                for item in lot.items:
                    self._items_buffer.append({
                        "lot_id": lot.id,
                        "order_num": item.order_num,
                        "product_name": item.product_name,
                        "description": item.description,
                        "quantity": item.quantity,
                        "amount": item.amount,
                        "measure_name": item.measure_name,
                        "price": item.price,
                        "cost": item.cost,
                        "country_name": item.country_name,
                        "properties": item.properties,
                    })
        except Exception as e:
            self.stats.errors += 1
            logger.error(f"Error processing lot {lot.id}: {e}")

    async def _flush_to_db(self):
        """Flush buffers to database."""
        if not self._lots_buffer:
            return

        try:
            from src.core.database import get_session
            from src.core.bulk_ops import (
                bulk_upsert_uzex_lots,
                bulk_insert_uzex_items,
            )

            async with get_session() as session:
                # Convert dicts to lists
                lots_list = list(self._lots_buffer.values())
                items_list = self._items_buffer

                # Insert lots first (parent table)
                if lots_list:
                    count = await bulk_upsert_uzex_lots(session, lots_list)
                    self.db_inserts += count
                    logger.info(f"Bulk upserting {len(lots_list)} UZEX lots")

                # Insert items (child table)
                if items_list:
                    await bulk_insert_uzex_items(session, items_list)
                    logger.info(f"Bulk inserting {len(items_list)} UZEX lot items")

                await session.commit()
                
                # ✅ Only clear buffers AFTER successful commit
                self._lots_buffer.clear()
                self._items_buffer.clear()

        except Exception as e:
            # ✅ CRITICAL: Rollback transaction on error
            await session.rollback()
            logger.error(f"❌ DB flush error: {e}")
            logger.error(f"⚠️  Buffers NOT cleared - will retry on next flush")
            self.stats.errors += 1
            raise  # Re-raise to trigger retry logic


async def main():
    """CLI entry point."""
    import argparse
    
    ap = argparse.ArgumentParser(description='UZEX Downloader')
    ap.add_argument('--type', '-t', default='auction', 
                    choices=['auction', 'shop', 'national', 'categories', 'products'])
    ap.add_argument('--status', '-s', default='completed', choices=['completed', 'active'])
    ap.add_argument('--target', '-n', type=int, default=100)
    ap.add_argument('--no-resume', action='store_true', help='Start fresh, ignore checkpoint')
    ap.add_argument('--no-skip', action='store_true', help='Re-download already seen lots')
    
    args = ap.parse_args()
    
    downloader = UzexDownloader()
    
    if args.type == 'categories':
        await downloader.download_categories()
    elif args.type == 'products':
        await downloader.download_products()
    else:
        await downloader.download_lots(
            lot_type=args.type,
            status=args.status,
            target=args.target,
            resume=not args.no_resume,
            skip_existing=not args.no_skip,
        )


if __name__ == "__main__":
    asyncio.run(main())
