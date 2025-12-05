"""
Checkpoint Manager - Track scraping progress across restarts.
Enables resume capability and deduplication.
"""
import json
import logging
from typing import Dict, Any, Optional, Set
from datetime import datetime, timezone
from pathlib import Path

import redis.asyncio as aioredis

from .config import settings

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Manages checkpoints for resumable scraping.
    
    Features:
    - Progress checkpoints (last processed ID, counts)
    - Deduplication (skip already-scraped items)
    - Both Redis and file-based fallback
    """
    
    CHECKPOINT_PREFIX = "checkpoint:"
    SEEN_PREFIX = "seen:"
    
    def __init__(self, platform: str, job_type: str):
        """
        Initialize checkpoint manager.
        
        Args:
            platform: Platform name (uzum, uzex)
            job_type: Job type (products, auctions, shop)
        """
        self.platform = platform
        self.job_type = job_type
        self.key = f"{platform}:{job_type}"
        self._redis: Optional[aioredis.Redis] = None
        self._local_checkpoint_file = Path(f"storage/checkpoints/{self.key.replace(':', '_')}.json")
    
    async def connect(self) -> bool:
        """Connect to Redis."""
        try:
            self._redis = await aioredis.from_url(
                settings.redis.url,
                encoding="utf-8",
                decode_responses=True
            )
            await self._redis.ping()
            logger.info(f"Checkpoint manager connected for {self.key}")
            return True
        except Exception as e:
            logger.warning(f"Redis unavailable, using file-based checkpoints: {e}")
            self._redis = None
            return False
    
    async def close(self):
        """Close connection."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None
    
    # =========================================================================
    # Checkpoint Operations
    # =========================================================================
    
    async def save_checkpoint(self, data: Dict[str, Any]):
        """
        Save checkpoint data.
        
        Example data:
        {
            "last_id": 1700500,
            "processed": 500,
            "found": 397,
            "started_at": "2024-01-01T12:00:00Z"
        }
        """
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        if self._redis:
            await self._redis.set(
                f"{self.CHECKPOINT_PREFIX}{self.key}",
                json.dumps(data)
            )
        else:
            self._save_to_file(data)
        
        logger.debug(f"Checkpoint saved: {data}")
    
    async def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Load last checkpoint."""
        if self._redis:
            data = await self._redis.get(f"{self.CHECKPOINT_PREFIX}{self.key}")
            if data:
                return json.loads(data)
        else:
            return self._load_from_file()
        return None
    
    async def clear_checkpoint(self):
        """Clear checkpoint (start fresh)."""
        if self._redis:
            await self._redis.delete(f"{self.CHECKPOINT_PREFIX}{self.key}")
        else:
            if self._local_checkpoint_file.exists():
                self._local_checkpoint_file.unlink()
        logger.info(f"Checkpoint cleared for {self.key}")
    
    # =========================================================================
    # Deduplication (Seen IDs)
    # =========================================================================
    
    async def mark_seen(self, ids: list) -> int:
        """
        Mark IDs as seen. Returns number of NEW ids.
        """
        if not ids:
            return 0
        
        if self._redis:
            return await self._redis.sadd(f"{self.SEEN_PREFIX}{self.key}", *[str(i) for i in ids])
        else:
            return len(ids)  # File-based doesn't track seen (yet)
    
    async def filter_unseen(self, ids: list) -> list:
        """
        Filter list to only unseen IDs.
        """
        if not ids or not self._redis:
            return ids
        
        # Check each ID
        unseen = []
        for id_ in ids:
            if not await self._redis.sismember(f"{self.SEEN_PREFIX}{self.key}", str(id_)):
                unseen.append(id_)
        
        return unseen
    
    async def is_seen(self, id_: Any) -> bool:
        """Check if ID was already scraped."""
        if self._redis:
            return await self._redis.sismember(f"{self.SEEN_PREFIX}{self.key}", str(id_))
        return False
    
    async def seen_count(self) -> int:
        """Get count of seen IDs."""
        if self._redis:
            return await self._redis.scard(f"{self.SEEN_PREFIX}{self.key}")
        return 0
    
    async def clear_seen(self):
        """Clear seen set (rescrape everything)."""
        if self._redis:
            await self._redis.delete(f"{self.SEEN_PREFIX}{self.key}")
        logger.info(f"Seen set cleared for {self.key}")
    
    # =========================================================================
    # File-based fallback
    # =========================================================================
    
    def _save_to_file(self, data: Dict):
        """Save checkpoint to file."""
        self._local_checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._local_checkpoint_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load_from_file(self) -> Optional[Dict]:
        """Load checkpoint from file."""
        if self._local_checkpoint_file.exists():
            with open(self._local_checkpoint_file) as f:
                return json.load(f)
        return None


async def get_checkpoint_manager(platform: str, job_type: str) -> CheckpointManager:
    """Create and connect a checkpoint manager."""
    manager = CheckpointManager(platform, job_type)
    await manager.connect()
    return manager
