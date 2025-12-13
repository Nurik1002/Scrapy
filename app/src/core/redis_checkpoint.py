"""
Redis-based checkpoint manager for safe multi-worker resume capability.
Replaces file-based checkpoints which are prone to corruption with 4 workers.
"""
import json
import redis.asyncio as aioredis
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class RedisCheckpointManager:
    """
    Atomic checkpoint storage using Redis.
    Safe for multiple workers writing simultaneously.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None
    
    async def connect(self):
        """Establish Redis connection"""
        if not self._redis:
            self._redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info(f"✅ Connected to Redis: {self.redis_url}")
    
    async def close(self):
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
            logger.info("🔌 Redis connection closed")
    
    def _make_key(self, platform: str, task: str, worker_id: Optional[str] = None) -> str:
        """Generate Redis key for checkpoint"""
        if worker_id:
            return f"checkpoint:{platform}:{task}:{worker_id}"
        return f"checkpoint:{platform}:{task}"
    
    async def save(
        self, 
        platform: str, 
        task: str, 
        data: Dict[Any, Any],
        worker_id: Optional[str] = None,
        ttl: Optional[int] = None
    ):
        """
        Atomically save checkpoint to Redis.
        
        Args:
            platform: Platform name (uzum, uzex, olx)
            task: Task name (continuous, daily, etc.)
            data: Checkpoint data to save
            worker_id: Optional worker ID for multi-worker setups
            ttl: Optional TTL in seconds (default: never expire)
        """
        await self.connect()
        
        key = self._make_key(platform, task, worker_id)
        
        # Add timestamp
        checkpoint_data = {
            **data,
            "_timestamp": datetime.now().isoformat(),
            "_worker_id": worker_id
        }
        
        # Atomic write
        await self._redis.set(key, json.dumps(checkpoint_data))
        
        # Set TTL if specified
        if ttl:
            await self._redis.expire(key, ttl)
        
        logger.info(f"💾 Saved checkpoint: {key}")
    
    async def load(
        self, 
        platform: str, 
        task: str,
        worker_id: Optional[str] = None
    ) -> Optional[Dict[Any, Any]]:
        """
        Load checkpoint from Redis.
        
        Returns:
            Checkpoint data dict, or None if not found
        """
        await self.connect()
        
        key = self._make_key(platform, task, worker_id)
        
        data = await self._redis.get(key)
        
        if data:
            checkpoint = json.loads(data)
            logger.info(f"📂 Loaded checkpoint: {key}")
            return checkpoint
        else:
            logger.info(f"ℹ️  No checkpoint found: {key}")
            return None
    
    async def delete(
        self, 
        platform: str, 
        task: str,
        worker_id: Optional[str] = None
    ):
        """Delete checkpoint"""
        await self.connect()
        
        key = self._make_key(platform, task, worker_id)
        await self._redis.delete(key)
        
        logger.info(f"🗑️  Deleted checkpoint: {key}")
    
    async def list_checkpoints(self, pattern: str = "checkpoint:*") -> list:
        """List all checkpoint keys matching pattern"""
        await self.connect()
        
        keys = []
        async for key in self._redis.scan_iter(match=pattern):
            keys.append(key)
        
        return keys


# Convenience functions for backward compatibility
async def save_checkpoint(platform: str, task: str, data: Dict[Any, Any]):
    """Save checkpoint (simple interface)"""
    mgr = RedisCheckpointManager()
    try:
        await mgr.save(platform, task, data)
    finally:
        await mgr.close()


async def load_checkpoint(platform: str, task: str) -> Optional[Dict[Any, Any]]:
    """Load checkpoint (simple interface)"""
    mgr = RedisCheckpointManager()
    try:
        return await mgr.load(platform, task)
    finally:
        await mgr.close()
