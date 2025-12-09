"""
Checkpoint Manager - Track scraping progress across restarts.
Enables resume capability and deduplication.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Set

import redis.asyncio as aioredis

from .config import settings

logger = logging.getLogger(__name__)

# Create debug logger for detailed troubleshooting
debug_logger = logging.getLogger(f"{__name__}.debug")


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
        self._local_checkpoint_file = Path(
            f"storage/checkpoints/{self.key.replace(':', '_')}.json"
        )

    async def connect(self) -> bool:
        """Connect to Redis."""
        debug_logger.debug(
            f"Attempting Redis connection for checkpoint manager: {self.key}"
        )
        debug_logger.debug(f"Redis URL: {settings.redis.url}")
        try:
            self._redis = await aioredis.from_url(
                settings.redis.url, encoding="utf-8", decode_responses=True
            )
            debug_logger.debug("Redis client created, attempting ping")
            await self._redis.ping()
            logger.info(f"Checkpoint manager connected for {self.key}")
            debug_logger.debug(f"Redis connection successful for {self.key}")
            return True
        except Exception as e:
            logger.warning(f"Redis unavailable, using file-based checkpoints: {e}")
            debug_logger.debug(
                f"Redis connection failed for {self.key}: {type(e).__name__}: {str(e)}"
            )
            debug_logger.debug(
                f"Will use file-based checkpoints: {self._local_checkpoint_file}"
            )
            self._redis = None
            return False

    async def close(self):
        """Close connection."""
        debug_logger.debug(f"Closing checkpoint manager for {self.key}")
        if self._redis:
            debug_logger.debug("Closing Redis connection")
            await self._redis.aclose()
            self._redis = None
            debug_logger.debug("Redis connection closed")
        else:
            debug_logger.debug("No Redis connection to close")

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
        debug_logger.debug(f"Saving checkpoint for {self.key}: {data}")
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        debug_logger.debug(f"Added timestamp to checkpoint data: {data['updated_at']}")

        if self._redis:
            debug_logger.debug(
                f"Saving checkpoint to Redis with key: {self.CHECKPOINT_PREFIX}{self.key}"
            )
            json_data = json.dumps(data)
            debug_logger.debug(f"Serialized checkpoint data: {len(json_data)} chars")
            await self._redis.set(f"{self.CHECKPOINT_PREFIX}{self.key}", json_data)
            debug_logger.debug("Checkpoint saved to Redis successfully")
        else:
            debug_logger.debug("Redis not available, saving checkpoint to file")
            self._save_to_file(data)
            debug_logger.debug("Checkpoint saved to file successfully")

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
        debug_logger.debug(f"Clearing checkpoint for {self.key}")

        if self._redis:
            debug_logger.debug(
                f"Deleting checkpoint from Redis with key: {self.CHECKPOINT_PREFIX}{self.key}"
            )
            result = await self._redis.delete(f"{self.CHECKPOINT_PREFIX}{self.key}")
            debug_logger.debug(f"Redis delete result: {result} keys deleted")
        else:
            debug_logger.debug(
                f"Checking for local checkpoint file: {self._local_checkpoint_file}"
            )
            if self._local_checkpoint_file.exists():
                debug_logger.debug(
                    f"Deleting local checkpoint file: {self._local_checkpoint_file}"
                )
                self._local_checkpoint_file.unlink()
                debug_logger.debug("Local checkpoint file deleted")
            else:
                debug_logger.debug("No local checkpoint file to delete")

        logger.info(f"Checkpoint cleared for {self.key}")
        debug_logger.debug(f"Checkpoint clearing completed for {self.key}")

    # =========================================================================
    # Deduplication (Seen IDs)
    # =========================================================================

    async def mark_seen(self, ids: list) -> int:
        """
        Mark IDs as seen. Returns number of NEW ids.
        """
        debug_logger.debug(f"Marking {len(ids)} IDs as seen for {self.key}")
        if not ids:
            debug_logger.debug("No IDs provided, returning 0")
            return 0

        debug_logger.debug(
            f"IDs to mark as seen: {ids[:10]}{'...' if len(ids) > 10 else ''}"
        )

        if self._redis:
            debug_logger.debug(f"Adding IDs to Redis set: {self.SEEN_PREFIX}{self.key}")
            str_ids = [str(i) for i in ids]
            debug_logger.debug(f"Converted {len(str_ids)} IDs to strings")
            new_count = await self._redis.sadd(
                f"{self.SEEN_PREFIX}{self.key}", *str_ids
            )
            debug_logger.debug(f"Redis SADD result: {new_count} new IDs added")
            return new_count
        else:
            debug_logger.debug(
                "Redis not available, file-based doesn't track seen IDs yet"
            )
            return len(ids)  # File-based doesn't track seen (yet)

    async def filter_unseen(self, ids: list) -> list:
        """
        Filter list to only unseen IDs.
        Uses Redis pipeline for atomic bulk checking.
        """
        if not ids or not self._redis:
            return ids

        # Use pipeline for atomic bulk check (much faster, reduces race condition)
        seen_key = f"{self.SEEN_PREFIX}{self.key}"
        pipe = self._redis.pipeline()

        for id_ in ids:
            pipe.sismember(seen_key, str(id_))

        # Execute all checks atomically
        results = await pipe.execute()

        # Filter to unseen only
        unseen = [ids[i] for i, is_seen in enumerate(results) if not is_seen]

        return unseen

    async def is_seen(self, id_: Any) -> bool:
        """Check if ID was already scraped."""
        debug_logger.debug(f"Checking if ID {id_} is seen for {self.key}")
        if self._redis:
            debug_logger.debug(f"Checking Redis set: {self.SEEN_PREFIX}{self.key}")
            result = await self._redis.sismember(
                f"{self.SEEN_PREFIX}{self.key}", str(id_)
            )
            debug_logger.debug(f"ID {id_} seen status: {result}")
            return result
        debug_logger.debug("Redis not available, returning False (unseen)")
        return False

    async def seen_count(self) -> int:
        """Get count of seen IDs."""
        debug_logger.debug(f"Getting seen count for {self.key}")
        if self._redis:
            debug_logger.debug(f"Counting Redis set: {self.SEEN_PREFIX}{self.key}")
            count = await self._redis.scard(f"{self.SEEN_PREFIX}{self.key}")
            debug_logger.debug(f"Seen count: {count}")
            return count
        debug_logger.debug("Redis not available, returning 0")
        return 0

    async def clear_seen(self):
        """Clear seen set (rescrape everything)."""
        debug_logger.debug(f"Clearing seen set for {self.key}")
        if self._redis:
            debug_logger.debug(f"Deleting Redis set: {self.SEEN_PREFIX}{self.key}")
            result = await self._redis.delete(f"{self.SEEN_PREFIX}{self.key}")
            debug_logger.debug(f"Redis delete result: {result} keys deleted")
        else:
            debug_logger.debug("Redis not available, no seen set to clear")
        logger.info(f"Seen set cleared for {self.key}")
        debug_logger.debug(f"Seen set clearing completed for {self.key}")

    # =========================================================================
    # File-based fallback
    # =========================================================================

    def _save_to_file(self, data: Dict):
        """
        Save checkpoint to file with file locking to prevent corruption.
        """
        debug_logger.debug(f"Saving checkpoint to file: {self._local_checkpoint_file}")
        import fcntl

        debug_logger.debug(
            f"Creating parent directories for {self._local_checkpoint_file.parent}"
        )
        self._local_checkpoint_file.parent.mkdir(parents=True, exist_ok=True)

        debug_logger.debug("Opening file with exclusive lock")
        # Use exclusive lock to prevent concurrent writes
        with open(self._local_checkpoint_file, "w") as f:
            debug_logger.debug("Acquiring exclusive file lock")
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                debug_logger.debug(
                    f"Writing checkpoint data to file: {len(str(data))} chars"
                )
                json.dump(data, f, indent=2)
                debug_logger.debug("Checkpoint data written to file successfully")
            finally:
                debug_logger.debug("Releasing file lock")
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _load_from_file(self) -> Optional[Dict]:
        """
        Load checkpoint from file with shared lock.
        """
        import fcntl

        if not self._local_checkpoint_file.exists():
            return None

        # Use shared lock for reading
        with open(self._local_checkpoint_file) as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


async def get_checkpoint_manager(platform: str, job_type: str) -> CheckpointManager:
    """Create and connect a checkpoint manager."""
    manager = CheckpointManager(platform, job_type)
    await manager.connect()
    return manager
