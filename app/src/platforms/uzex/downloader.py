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
    
    def __init__(self, batch_size: int = 100, save_raw: bool = True):
        self.batch_size = batch_size
        self.save_raw = save_raw
        self.client = UzexClient()
        self.stats = DownloadStats()
        self._save_dir: Optional[Path] = None
    
    async def download_lots(
        self,
        lot_type: str = "auction",
        status: str = "completed",
        target: int = None,
        start_from: int = 1,
        on_lot: Callable[[LotData], None] = None,
    ) -> DownloadStats:
        """
        Download lots of a specific type.
        
        Args:
            lot_type: Type of lots (auction, shop, national)
            status: Status (completed, active)
            target: Stop after N lots
            start_from: Start index
            on_lot: Callback for each lot
        """
        logger.info(f"Downloading {status} {lot_type} lots...")
        
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
                    lot = parser.parse_lot(item, lot_type, status)
                    if lot:
                        self.stats.found += 1
                        
                        # Fetch lot items for auctions
                        if lot_type == "auction" and status == "completed":
                            items = await self.client.get_auction_products(lot.id)
                            if items:
                                lot.items = parser.parse_lot_items(items)
                        
                        # Save raw
                        if self.save_raw:
                            await self._save_raw(lot)
                        
                        # Callback
                        if on_lot:
                            on_lot(lot)
                
                self.stats.processed += len(data)
                
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
            await self.client.close()
        
        logger.info(f"✅ Done! Found {self.stats.found:,} lots")
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


async def main():
    """CLI entry point."""
    import argparse
    
    ap = argparse.ArgumentParser(description='UZEX Downloader')
    ap.add_argument('--type', '-t', default='auction', 
                    choices=['auction', 'shop', 'national', 'categories', 'products'])
    ap.add_argument('--status', '-s', default='completed', choices=['completed', 'active'])
    ap.add_argument('--target', '-n', type=int, default=100)
    
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
        )


if __name__ == "__main__":
    asyncio.run(main())
