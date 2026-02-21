"""
Utilization Cache for storing and retrieving utilization data.

This module provides a thread-safe cache for storing utilization data
with TTL support.
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional, Dict

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached utilization value with timestamp."""

    utilization: float
    timestamp: float


class UtilizationCache:
    """
    Thread-safe cache for storing utilization data.

    This cache stores utilization values with timestamps and provides
    methods for checking if entries are expired and retrieving/setting
    values.
    """

    def __init__(self, ttl: int = 30):
        """
        Initialize the utilization cache.

        Args:
            ttl: Time-to-live for cache entries in seconds (default: 30)
        """
        self.ttl = ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()

        logger.debug(f"UtilizationCache initialized with ttl={ttl}s")

    def get(self, chute_id: str) -> Optional[float]:
        """
        Get cached utilization value if still valid.

        Args:
            chute_id: The Chutes deployment ID

        Returns:
            Cached utilization value or None if expired/not cached
        """
        with self._lock:
            if chute_id not in self._cache:
                return None

            entry = self._cache[chute_id]

            if self._is_expired(entry):
                logger.debug(f"Cache expired for {chute_id}")
                del self._cache[chute_id]
                return None

            age = time.time() - entry.timestamp
            logger.debug(
                f"Cache hit for {chute_id}, age={age:.1f}s, util={entry.utilization}"
            )
            return entry.utilization

    def set(self, chute_id: str, utilization: float) -> None:
        """
        Store utilization value in cache.

        Args:
            chute_id: The Chutes deployment ID
            utilization: The utilization value (0.0 to 1.0)
        """
        with self._lock:
            self._cache[chute_id] = CacheEntry(
                utilization=utilization, timestamp=time.time()
            )
            logger.debug(f"Cached utilization for {chute_id}: {utilization}")

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            logger.debug("Cache cleared")

    def _is_expired(self, entry: CacheEntry) -> bool:
        """
        Check if a cache entry is expired.

        Args:
            entry: The cache entry to check

        Returns:
            True if the entry is expired, False otherwise
        """
        age = time.time() - entry.timestamp
        return age > self.ttl

    def is_expired(self, chute_id: str) -> bool:
        """
        Check if a specific cache entry is expired.

        Args:
            chute_id: The Chutes deployment ID

        Returns:
            True if the entry is expired or not found, False otherwise
        """
        with self._lock:
            if chute_id not in self._cache:
                return True

            entry = self._cache[chute_id]
            return self._is_expired(entry)

    def size(self) -> int:
        """
        Get the number of cached entries.

        Returns:
            Number of entries in the cache
        """
        with self._lock:
            return len(self._cache)

    def keys(self) -> list:
        """
        Get all cached chute IDs.

        Returns:
            List of cached chute IDs
        """
        with self._lock:
            return list(self._cache.keys())

    def delete(self, key: str) -> bool:
        """
        Delete an item from the cache.

        Args:
            key: The cache key to delete

        Returns:
            True if item was deleted, False if key didn't exist
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Deleted cache entry for {key}")
                return True
            return False
