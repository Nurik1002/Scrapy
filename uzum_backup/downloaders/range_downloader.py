"""
Fast ID Range Downloader - Download ALL products by iterating IDs.

Instead of crawling category pages with Playwright, we simply iterate
through product IDs (1 to 3,000,000) and fetch via API.

MUCH faster:
- No browser needed
- No Cloudflare issues  
- Parallel async requests
- Can resume from any point
"""
import asyncio
import aiohttp
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config, RAW_STORAGE_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


class RangeDownloader:
    """
    Downloads products by iterating through ID ranges.
    
    Much faster than crawling - no Playwright needed!
    """
    
    API_URL = "https://api.uzum.uz/api/v2/product/{}"
    
    def __init__(
        self,
        start_id: int = 1,
        end_id: int = 3000000,
        concurrency: int = 10,
        save_dir: Path = None
    ):
        self.start_id = start_id
        self.end_id = end_id
        self.concurrency = concurrency
        self.save_dir = save_dir or RAW_STORAGE_DIR / "products" / datetime.now().strftime("%Y-%m-%d")
        
        # Stats
        self.found = 0
        self.empty = 0
        self.errors = 0
        self.checked = 0
        
        # Progress tracking
        self.last_id = start_id
        self.progress_file = RAW_STORAGE_DIR / "range_progress.json"
        
    async def fetch_product(
        self, 
        session: aiohttp.ClientSession, 
        product_id: int
    ) -> Optional[Dict]:
        """Fetch a single product by ID."""
        try:
            async with session.get(
                self.API_URL.format(product_id),
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    payload = data.get('payload', {}).get('data', {})
                    if payload and payload.get('title'):
                        return {
                            'product_id': product_id,
                            'data': data,
                            'fetched_at': datetime.now(timezone.utc).isoformat()
                        }
                return None
        except Exception as e:
            self.errors += 1
            return None
    
    async def save_product(self, product: Dict):
        """Save product to file."""
        self.save_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.save_dir / f"{product['product_id']}.json"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(product['data'], f, ensure_ascii=False, indent=2)
    
    async def process_batch(
        self, 
        session: aiohttp.ClientSession, 
        ids: List[int]
    ) -> int:
        """Process a batch of IDs concurrently."""
        tasks = [self.fetch_product(session, pid) for pid in ids]
        results = await asyncio.gather(*tasks)
        
        found_count = 0
        for product in results:
            self.checked += 1
            if product:
                self.found += 1
                found_count += 1
                await self.save_product(product)
            else:
                self.empty += 1
        
        return found_count
    
    def save_progress(self):
        """Save progress for resume capability."""
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.progress_file, 'w') as f:
            json.dump({
                'last_id': self.last_id,
                'found': self.found,
                'empty': self.empty,
                'errors': self.errors,
                'checked': self.checked,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }, f, indent=2)
    
    def load_progress(self) -> int:
        """Load progress and return last ID."""
        if self.progress_file.exists():
            with open(self.progress_file) as f:
                data = json.load(f)
                self.found = data.get('found', 0)
                self.empty = data.get('empty', 0)
                self.errors = data.get('errors', 0)
                self.checked = data.get('checked', 0)
                return data.get('last_id', self.start_id)
        return self.start_id
    
    async def run(
        self, 
        target: int = None,
        resume: bool = True
    ):
        """
        Run the downloader.
        
        Args:
            target: Stop after finding this many products (None = run until end_id)
            resume: Resume from last position
        """
        if resume:
            self.start_id = self.load_progress()
            logger.info(f"Resuming from ID {self.start_id} (found={self.found})")
        
        batch_size = self.concurrency * 10  # 100 IDs per batch
        
        connector = aiohttp.TCPConnector(limit=self.concurrency)
        async with aiohttp.ClientSession(connector=connector) as session:
            
            current_id = self.start_id
            start_time = datetime.now()
            
            while current_id < self.end_id:
                # Create batch
                batch_ids = list(range(current_id, min(current_id + batch_size, self.end_id)))
                
                # Process batch
                found = await self.process_batch(session, batch_ids)
                current_id += batch_size
                self.last_id = current_id
                
                # Progress report every 1000 IDs
                if self.checked % 1000 == 0:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    rate = self.checked / elapsed if elapsed > 0 else 0
                    logger.info(
                        f"ID {current_id:,} | Found: {self.found:,} | "
                        f"Empty: {self.empty:,} | Rate: {rate:.0f}/sec"
                    )
                    self.save_progress()
                
                # Check target
                if target and self.found >= target:
                    logger.info(f"🎯 Target {target} reached!")
                    break
                
                # Small delay to be nice
                await asyncio.sleep(0.1)
        
        self.save_progress()
        logger.info(f"\n✅ Done! Found {self.found:,} products from {self.checked:,} IDs")
        return self.found


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Download products by ID range')
    parser.add_argument('--start', '-s', type=int, default=1, help='Start ID')
    parser.add_argument('--end', '-e', type=int, default=3000000, help='End ID')
    parser.add_argument('--target', '-t', type=int, default=None, help='Target product count')
    parser.add_argument('--concurrency', '-c', type=int, default=20, help='Concurrent requests')
    parser.add_argument('--no-resume', action='store_true', help='Start fresh')
    
    args = parser.parse_args()
    
    downloader = RangeDownloader(
        start_id=args.start,
        end_id=args.end,
        concurrency=args.concurrency
    )
    
    try:
        await downloader.run(
            target=args.target,
            resume=not args.no_resume
        )
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted! Saving progress...")
        downloader.save_progress()
        print(f"💾 Resume from ID {downloader.last_id}")


if __name__ == "__main__":
    asyncio.run(main())
