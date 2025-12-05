"""
Uzum Downloader - High-performance ID range downloader.

Optimized for speed:
- 150 concurrent connections (3x default)
- Async file I/O
- Minimal delays
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Callable
from datetime import datetime, timezone
from dataclasses import dataclass, field

import aiofiles

from .client import UzumClient
from .parser import UzumParser, parser
from ..base import ProductData

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
    High-performance downloader using ID range iteration.
    
    Features:
    - 150 parallel async downloads (3x faster)
    - Async file I/O with aiofiles
    - Progress tracking & resume
    - Real-time stats
    """
    
    def __init__(
        self,
        concurrency: int = 150,  # Increased from 50
        batch_size: int = 500,
        save_raw: bool = True,
        progress_file: Path = None
    ):
        self.concurrency = concurrency
        self.batch_size = batch_size
        self.save_raw = save_raw
        self.progress_file = progress_file or RAW_STORAGE_DIR / "download_progress.json"
        
        self.client = UzumClient(concurrency=concurrency)
        self.stats = DownloadStats()
        self._save_dir: Optional[Path] = None
    
    async def download_range(
        self,
        start_id: int = 1,
        end_id: int = 3000000,
        target: int = None,
        on_product: Callable[[ProductData], None] = None,
        on_batch: Callable[[DownloadStats], None] = None,
        resume: bool = True
    ) -> DownloadStats:
        """
        Download products in ID range.
        
        Args:
            start_id: Starting product ID
            end_id: Ending product ID
            target: Stop after finding N products (optional)
            on_product: Callback for each valid product
            on_batch: Callback after each batch
            resume: Resume from last position
            
        Returns:
            Final statistics
        """
        # Resume from progress
        if resume:
            progress = self._load_progress()
            if progress:
                start_id = progress.get("last_id", start_id)
                self.stats.found = progress.get("found", 0)
                logger.info(f"Resuming from ID {start_id} (found={self.stats.found})")
        
        # Setup save directory
        if self.save_raw:
            self._save_dir = RAW_STORAGE_DIR / "products" / datetime.now().strftime("%Y-%m-%d")
            self._save_dir.mkdir(parents=True, exist_ok=True)
        
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
                
                # Process products
                for raw_data in products:
                    # Save raw
                    if self.save_raw:
                        await self._save_raw(raw_data)
                    
                    # Parse and callback
                    if on_product:
                        parsed = parser.parse_product(raw_data)
                        if parsed:
                            on_product(parsed)
                
                # Batch callback
                if on_batch:
                    on_batch(self.stats)
                
                # Progress log every 1000 IDs
                if self.stats.processed % 1000 == 0:
                    self._log_progress()
                    self._save_progress()
                
                current_id += self.batch_size
                
                # Small delay
                await asyncio.sleep(0.02)
        
        finally:
            await self.client.close()
            self._save_progress()
        
        logger.info(f"\n✅ Done! Found {self.stats.found:,} products from {self.stats.processed:,} IDs")
        return self.stats
    
    async def _save_raw(self, raw_data: Dict):
        """Save raw JSON to file using async I/O."""
        try:
            product_id = raw_data.get("payload", {}).get("data", {}).get("id")
            if product_id and self._save_dir:
                filepath = self._save_dir / f"{product_id}.json"
                async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(raw_data, ensure_ascii=False))
        except Exception as e:
            self.stats.errors += 1
    
    def _log_progress(self):
        """Log current progress."""
        logger.info(
            f"ID {self.stats.last_id:,} | "
            f"Found: {self.stats.found:,} | "
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
    
    parser = argparse.ArgumentParser(description='Uzum ID Range Downloader')
    parser.add_argument('--start', '-s', type=int, default=1, help='Start ID')
    parser.add_argument('--end', '-e', type=int, default=3000000, help='End ID')
    parser.add_argument('--target', '-t', type=int, default=None, help='Target count')
    parser.add_argument('--concurrency', '-c', type=int, default=50, help='Concurrent requests')
    parser.add_argument('--no-resume', action='store_true', help='Start fresh')
    
    args = parser.parse_args()
    
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
        print(f"   Success Rate: {stats.success_rate:.1f}%")
        print(f"   Rate: {stats.rate:.0f}/sec")
        
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted! Progress saved.")


if __name__ == "__main__":
    asyncio.run(main())
