"""
Redis caching service for loan calculations.
Frequent same-parameter queries (e.g. standard loan products)
are cached to avoid redundant computation.
Cache key is derived from request parameters — same inputs = same output.
"""

import json
import hashlib
import logging
from typing import Optional, Any
from functools import wraps

import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)

# Global Redis client — initialized on startup
redis_client: Optional[aioredis.Redis] = None


async def init_redis() -> None:
    """Initialize Redis connection on app startup."""
    global redis_client
    try:
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=3,
        )
        await redis_client.ping()
        logger.info("✅ Redis connected successfully")
    except Exception as e:
        logger.warning(f"⚠️  Redis not available — running without cache: {e}")
        redis_client = None


async def close_redis() -> None:
    """Close Redis connection on app shutdown."""
    global redis_client
    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")


async def is_connected() -> bool:
    """Check if Redis is available."""
    if not redis_client:
        return False
    try:
        await redis_client.ping()
        return True
    except Exception:
        return False


def make_cache_key(prefix: str, params: dict) -> str:
    """
    Generate a deterministic cache key from request parameters.
    Uses SHA256 hash of sorted JSON to ensure consistency.
    """
    param_str = json.dumps(params, sort_keys=True)
    hash_str = hashlib.sha256(param_str.encode()).hexdigest()[:16]
    return f"mifos:loan:{prefix}:{hash_str}"


async def get_cached(key: str) -> Optional[Any]:
    """Retrieve value from cache. Returns None if miss or Redis unavailable."""
    if not redis_client:
        return None
    try:
        value = await redis_client.get(key)
        if value:
            logger.debug(f"Cache HIT: {key}")
            return json.loads(value)
        logger.debug(f"Cache MISS: {key}")
        return None
    except Exception as e:
        logger.warning(f"Cache GET error: {e}")
        return None


async def set_cached(key: str, value: Any, ttl: int = None) -> None:
    """Store value in cache with TTL. Silently fails if Redis unavailable."""
    if not redis_client:
        return
    try:
        ttl = ttl or settings.CACHE_TTL_SECONDS
        await redis_client.setex(key, ttl, json.dumps(value))
        logger.debug(f"Cache SET: {key} (TTL={ttl}s)")
    except Exception as e:
        logger.warning(f"Cache SET error: {e}")


async def invalidate_pattern(pattern: str) -> int:
    """Invalidate all cache keys matching a pattern. Returns count deleted."""
    if not redis_client:
        return 0
    try:
        keys = await redis_client.keys(pattern)
        if keys:
            count = await redis_client.delete(*keys)
            logger.info(f"Cache invalidated {count} keys matching: {pattern}")
            return count
        return 0
    except Exception as e:
        logger.warning(f"Cache invalidation error: {e}")
        return 0
