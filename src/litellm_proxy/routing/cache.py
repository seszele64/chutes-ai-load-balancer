"""
Metrics cache with per-metric TTLs.

This module provides a caching layer for chute metrics with separate
TTL (Time To Live) values for each metric type.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from litellm_proxy.routing.metrics import ChuteMetrics

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Single metric cache entry."""

    value: Any
    fetched_at: float


class MetricsCache:
    """
    Multi-metric cache with separate TTLs per metric type.

    TTL Configuration (per user decision):
    - utilization: 30 seconds (needs to be fresh for load)
    - tps: 300 seconds (5 minutes)
    - ttft: 300 seconds (5 minutes)
    - quality: 300 seconds (5 minutes, derived from total_invocations)
    """

    DEFAULT_TTLS = {
        "utilization": 30,  # 30 seconds
        "tps": 300,  # 5 minutes
        "ttft": 300,  # 5 minutes
        "quality": 300,  # 5 minutes
        "total_invocations": 300,  # 5 minutes
    }

    def __init__(self, ttls: Optional[Dict[str, int]] = None):
        """
        Initialize the metrics cache.

        Args:
            ttls: Optional custom TTLs for metric types
        """
        self.ttls = ttls or self.DEFAULT_TTLS.copy()
        # chute_id -> metric_name -> CacheEntry
        self._cache: Dict[str, Dict[str, CacheEntry]] = {}

    def get(self, chute_id: str, metric: str) -> Optional[Any]:
        """
        Get cached metric value if not expired.

        Args:
            chute_id: The chute ID
            metric: The metric name (e.g., "tps", "ttft", "utilization")

        Returns:
            Cached value or None if not found or expired
        """
        if chute_id not in self._cache:
            logger.debug(f"Cache miss for {chute_id}.{metric}: chute not in cache")
            return None

        metric_cache = self._cache[chute_id]
        if metric not in metric_cache:
            logger.debug(f"Cache miss for {chute_id}.{metric}: metric not cached")
            return None

        entry = metric_cache[metric]
        ttl = self.ttls.get(metric, 30)
        age = time.time() - entry.fetched_at

        if age > ttl:
            # Expired
            logger.debug(
                f"Cache expired for {chute_id}.{metric}: age={age:.1f}s > TTL={ttl}s"
            )
            del metric_cache[metric]
            return None

        logger.debug(f"Cache hit for {chute_id}.{metric}: age={age:.1f}s < TTL={ttl}s")
        return entry.value

    def set(self, chute_id: str, metric: str, value: Any) -> None:
        """
        Cache a metric value.

        Args:
            chute_id: The chute ID
            metric: The metric name
            value: The value to cache
        """
        if chute_id not in self._cache:
            self._cache[chute_id] = {}

        self._cache[chute_id][metric] = CacheEntry(value=value, fetched_at=time.time())
        logger.debug(f"Cached {chute_id}.{metric} = {value}")

    def get_all(self, chute_id: str) -> Optional[ChuteMetrics]:
        """
        Get all cached metrics for a chute.

        Args:
            chute_id: The chute ID

        Returns:
            ChuteMetrics with cached values, or None if no valid metrics
        """
        if chute_id not in self._cache:
            return None

        metric_cache = self._cache[chute_id]

        # Check if any metric is still valid
        has_valid = False
        for metric, entry in list(metric_cache.items()):
            ttl = self.ttls.get(metric, 30)
            if time.time() - entry.fetched_at <= ttl:
                has_valid = True
            else:
                # Remove expired entries
                del metric_cache[metric]

        if not has_valid:
            logger.debug(f"No valid metrics in cache for {chute_id}")
            return None

        return ChuteMetrics(
            chute_id=chute_id,
            model=self.get(chute_id, "model") or "",
            tps=self.get(chute_id, "tps"),
            ttft=self.get(chute_id, "ttft"),
            utilization=self.get(chute_id, "utilization"),
            total_invocations=self.get(chute_id, "total_invocations"),
        )

    def set_all(self, metrics: ChuteMetrics) -> None:
        """
        Cache all metrics for a chute.

        Args:
            metrics: ChuteMetrics object with values to cache
        """
        if metrics.model:
            self.set(metrics.chute_id, "model", metrics.model)
        if metrics.tps is not None:
            self.set(metrics.chute_id, "tps", metrics.tps)
        if metrics.ttft is not None:
            self.set(metrics.chute_id, "ttft", metrics.ttft)
        if metrics.utilization is not None:
            self.set(metrics.chute_id, "utilization", metrics.utilization)
        if metrics.total_invocations is not None:
            self.set(metrics.chute_id, "total_invocations", metrics.total_invocations)
        logger.info(f"Cached all metrics for {metrics.chute_id}")

    def is_warm(self) -> bool:
        """
        Check if cache has any data.

        Returns:
            True if cache has at least one cached metric
        """
        return len(self._cache) > 0

    def is_warm_for(self, chute_id: str) -> bool:
        """
        Check if cache has valid data for a specific chute.

        Args:
            chute_id: The chute ID to check

        Returns:
            True if cache has valid data for the chute
        """
        if chute_id not in self._cache:
            return False

        metric_cache = self._cache[chute_id]
        for metric, entry in metric_cache.items():
            ttl = self.ttls.get(metric, 30)
            if time.time() - entry.fetched_at <= ttl:
                return True

        return False

    def get_age(self, chute_id: str, metric: str) -> Optional[float]:
        """
        Get the age of a cached metric in seconds.

        Args:
            chute_id: The chute ID
            metric: The metric name

        Returns:
            Age in seconds, or None if not cached
        """
        if chute_id not in self._cache:
            return None

        metric_cache = self._cache[chute_id]
        if metric not in metric_cache:
            return None

        entry = metric_cache[metric]
        return time.time() - entry.fetched_at

    def clear(self, chute_id: Optional[str] = None) -> None:
        """
        Clear cached data.

        Args:
            chute_id: Optional specific chute to clear, or all if None
        """
        if chute_id is None:
            self._cache.clear()
            logger.info("Cleared entire metrics cache")
        elif chute_id in self._cache:
            del self._cache[chute_id]
            logger.info(f"Cleared metrics cache for {chute_id}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_entries = sum(len(metrics) for metrics in self._cache.values())
        return {
            "total_chutes": len(self._cache),
            "total_entries": total_entries,
            "ttls": self.ttls,
        }
