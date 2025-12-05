"""
Redis Client - Async Redis connection for queues and caching.
"""
import json
from typing import Any, Optional, List
from datetime import datetime, timezone

import redis.asyncio as aioredis

from .config import settings


class RedisClient:
    """Async Redis client for queues and caching."""
    
    def __init__(self):
        self._client: Optional[aioredis.Redis] = None
    
    async def connect(self) -> aioredis.Redis:
        """Connect to Redis."""
        if self._client is None:
            self._client = await aioredis.from_url(
                settings.redis.url,
                encoding="utf-8",
                decode_responses=True
            )
        return self._client
    
    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    @property
    def client(self) -> aioredis.Redis:
        """Get Redis client (must be connected first)."""
        if self._client is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client
    
    # Queue operations
    async def push_to_queue(self, queue_name: str, items: List[Any]):
        """Push items to a queue."""
        if not items:
            return
        pipeline = self.client.pipeline()
        for item in items:
            data = json.dumps(item) if not isinstance(item, str) else item
            pipeline.rpush(queue_name, data)
        await pipeline.execute()
    
    async def pop_from_queue(self, queue_name: str, count: int = 1) -> List[Any]:
        """Pop items from queue."""
        items = []
        for _ in range(count):
            item = await self.client.lpop(queue_name)
            if item is None:
                break
            try:
                items.append(json.loads(item))
            except json.JSONDecodeError:
                items.append(item)
        return items
    
    async def queue_length(self, queue_name: str) -> int:
        """Get queue length."""
        return await self.client.llen(queue_name)
    
    # Progress tracking
    async def set_progress(self, key: str, data: dict):
        """Save progress data."""
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        await self.client.set(f"progress:{key}", json.dumps(data))
    
    async def get_progress(self, key: str) -> Optional[dict]:
        """Get progress data."""
        data = await self.client.get(f"progress:{key}")
        if data:
            return json.loads(data)
        return None
    
    # Caching
    async def cache_set(self, key: str, value: Any, ttl: int = 3600):
        """Set cache value with TTL."""
        await self.client.setex(f"cache:{key}", ttl, json.dumps(value))
    
    async def cache_get(self, key: str) -> Optional[Any]:
        """Get cached value."""
        data = await self.client.get(f"cache:{key}")
        if data:
            return json.loads(data)
        return None
    
    # Sets for deduplication
    async def add_to_set(self, set_name: str, items: List[Any]) -> int:
        """Add items to a set. Returns number of new items added."""
        if not items:
            return 0
        return await self.client.sadd(set_name, *[str(i) for i in items])
    
    async def is_in_set(self, set_name: str, item: Any) -> bool:
        """Check if item is in set."""
        return await self.client.sismember(set_name, str(item))
    
    async def set_size(self, set_name: str) -> int:
        """Get set size."""
        return await self.client.scard(set_name)


# Global Redis client instance
redis_client = RedisClient()
