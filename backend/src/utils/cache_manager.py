"""
Multi-level caching system for performance optimization.

Caches:
- Account info (TTL: 5s)
- Pool state (TTL: 1s)
- Price data (TTL: 0.5s)
- Token metadata (TTL: 60s)
- Holder lists (TTL: 30s)
"""

import asyncio
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class CacheManager:
    """
    Multi-level cache manager with TTL and LRU eviction.
    
    Features:
    - Type-specific TTLs
    - LRU eviction
    - Size limits
    - Thread-safe operations
    """

    def __init__(self, max_size: int = 1000):
        """Initialize cache manager.

        Args:
            max_size: Maximum entries per cache type
        """
        self.max_size = max_size
        self.lock = asyncio.Lock()
        
        # Caches with (value, timestamp) tuples
        self.account_cache: OrderedDict[str, tuple[Any, datetime]] = OrderedDict()
        self.pool_cache: OrderedDict[str, tuple[Any, datetime]] = OrderedDict()
        self.price_cache: OrderedDict[str, tuple[float, datetime]] = OrderedDict()
        self.metadata_cache: OrderedDict[str, tuple[Any, datetime]] = OrderedDict()
        self.holder_cache: OrderedDict[str, tuple[Any, datetime]] = OrderedDict()
        
        # TTLs for each cache type
        self.ttls = {
            'account': timedelta(seconds=5),
            'pool': timedelta(seconds=1),
            'price': timedelta(seconds=0.5),
            'metadata': timedelta(seconds=60),
            'holder': timedelta(seconds=30),
        }
        
        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
        }

    async def get(self, cache_type: str, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            cache_type: Type of cache ('account', 'pool', 'price', 'metadata', 'holder')
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        async with self.lock:
            cache = getattr(self, f'{cache_type}_cache', None)
            if cache is None:
                logger.warning(f"Unknown cache type: {cache_type}")
                self.stats['misses'] += 1
                return None

            if key in cache:
                value, timestamp = cache[key]
                ttl = self.ttls.get(cache_type, timedelta(seconds=5))
                
                # Check if expired
                if datetime.now() - timestamp < ttl:
                    # Move to end (LRU - most recently used)
                    cache.move_to_end(key)
                    self.stats['hits'] += 1
                    logger.debug(f"Cache HIT: {cache_type}:{key}")
                    return value
                else:
                    # Expired, remove
                    del cache[key]
                    logger.debug(f"Cache EXPIRED: {cache_type}:{key}")
            
            self.stats['misses'] += 1
            logger.debug(f"Cache MISS: {cache_type}:{key}")
            return None

    async def set(self, cache_type: str, key: str, value: Any) -> None:
        """Set value in cache.

        Args:
            cache_type: Type of cache
            key: Cache key
            value: Value to cache
        """
        async with self.lock:
            cache = getattr(self, f'{cache_type}_cache', None)
            if cache is None:
                logger.warning(f"Unknown cache type: {cache_type}")
                return

            # Remove if exists (will be re-added at end)
            if key in cache:
                del cache[key]
            
            # Add new entry
            cache[key] = (value, datetime.now())
            
            # LRU eviction if over limit
            if len(cache) > self.max_size:
                cache.popitem(last=False)  # Remove oldest
                self.stats['evictions'] += 1
                logger.debug(f"Cache EVICTION: {cache_type} (size: {len(cache)})")

    async def clear(self, cache_type: Optional[str] = None) -> None:
        """Clear cache(s).

        Args:
            cache_type: Specific cache type to clear, or None to clear all
        """
        async with self.lock:
            if cache_type:
                cache = getattr(self, f'{cache_type}_cache', None)
                if cache:
                    cache.clear()
                    logger.info(f"Cleared {cache_type} cache")
            else:
                self.account_cache.clear()
                self.pool_cache.clear()
                self.price_cache.clear()
                self.metadata_cache.clear()
                self.holder_cache.clear()
                logger.info("Cleared all caches")

    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Statistics dictionary
        """
        async with self.lock:
            total_requests = self.stats['hits'] + self.stats['misses']
            hit_rate = (
                (self.stats['hits'] / total_requests * 100)
                if total_requests > 0
                else 0.0
            )
            
            return {
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'evictions': self.stats['evictions'],
                'hit_rate': hit_rate,
                'sizes': {
                    'account': len(self.account_cache),
                    'pool': len(self.pool_cache),
                    'price': len(self.price_cache),
                    'metadata': len(self.metadata_cache),
                    'holder': len(self.holder_cache),
                },
            }

    async def cleanup_expired(self) -> int:
        """Clean up expired entries from all caches.

        Returns:
            Number of entries removed
        """
        async with self.lock:
            removed = 0
            now = datetime.now()
            
            for cache_type, cache in [
                ('account', self.account_cache),
                ('pool', self.pool_cache),
                ('price', self.price_cache),
                ('metadata', self.metadata_cache),
                ('holder', self.holder_cache),
            ]:
                ttl = self.ttls.get(cache_type, timedelta(seconds=5))
                expired_keys = [
                    key for key, (_, timestamp) in cache.items()
                    if now - timestamp >= ttl
                ]
                for key in expired_keys:
                    del cache[key]
                    removed += 1
            
            if removed > 0:
                logger.debug(f"Cleaned up {removed} expired cache entries")
            
            return removed

