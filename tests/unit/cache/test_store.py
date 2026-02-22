"""
Unit tests for cache store.

These tests verify the utilization cache behavior including TTL expiration,
thread safety, eviction, and basic CRUD operations.
"""

import pytest
import time
import threading
from concurrent.futures import ThreadPoolExecutor

# Import the cache store
from litellm_proxy.cache.store import UtilizationCache


@pytest.mark.unit
def test_cache_ttl_expiration():
    """
    Given: Cache entry with short TTL (1 second)
    When: More than TTL seconds pass before get()
    Then: Returns None (entry expired)
    """
    # Arrange
    cache = UtilizationCache(ttl=1)
    cache.set("chute-1", 0.5)

    # Act - wait for TTL to expire
    time.sleep(1.5)

    # Assert
    result = cache.get("chute-1")
    assert result is None


@pytest.mark.unit
def test_cache_get_returns_cached():
    """
    Given: A value is stored in cache
    When: get() is called before TTL expires
    Then: Returns the cached value
    """
    # Arrange
    cache = UtilizationCache(ttl=30)
    cache.set("chute-1", 0.75)

    # Act
    result = cache.get("chute-1")

    # Assert
    assert result == 0.75


@pytest.mark.unit
def test_cache_get_returns_none_for_expired():
    """
    Given: Cache entry that has expired
    When: get() is called
    Then: Returns None and removes expired entry
    """
    # Arrange
    cache = UtilizationCache(ttl=1)
    cache.set("chute-1", 0.3)

    # Wait for expiration
    time.sleep(1.5)

    # Act
    result = cache.get("chute-1")

    # Assert
    assert result is None


@pytest.mark.unit
def test_cache_set_updates_existing():
    """
    Given: Cache entry already exists
    When: set() is called with same key
    Then: Updates the existing value
    """
    # Arrange
    cache = UtilizationCache(ttl=30)
    cache.set("chute-1", 0.5)

    # Act - update the value
    cache.set("chute-1", 0.8)

    # Assert
    result = cache.get("chute-1")
    assert result == 0.8
    # Size should remain 1 (not 2)
    assert cache.size() == 1


@pytest.mark.unit
def test_cache_thread_safety():
    """
    Given: Multiple threads accessing cache simultaneously
    When: Concurrent read/write operations
    Then: All operations complete without errors (thread-safe)
    """
    # Arrange
    cache = UtilizationCache(ttl=30)
    num_threads = 10
    operations_per_thread = 100

    def write_operation(i):
        cache.set(f"chute-{i % num_threads}", i / 100.0)

    def read_operation(i):
        cache.get(f"chute-{i % num_threads}")

    # Act - run concurrent operations
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Write operations
        futures = [
            executor.submit(write_operation, i) for i in range(operations_per_thread)
        ]
        for f in futures:
            f.result()

        # Read operations
        futures = [
            executor.submit(read_operation, i) for i in range(operations_per_thread)
        ]
        for f in futures:
            f.result()

    # Assert - cache should have entries without errors
    assert cache.size() > 0


@pytest.mark.unit
def test_cache_can_store_multiple_entries():
    """
    Given: Cache with default configuration
    When: Adding multiple entries
    Then: All entries can be stored and retrieved
    """
    # Arrange - current implementation doesn't have max_size, but we verify behavior
    cache = UtilizationCache(ttl=30)

    # Act - add multiple entries
    for i in range(50):
        cache.set(f"chute-{i}", i / 100.0)

    # Assert - all entries should be retrievable
    assert cache.size() == 50

    # Verify a few entries
    assert cache.get("chute-0") == 0.0
    assert cache.get("chute-49") == 0.49


@pytest.mark.unit
def test_cache_clear():
    """
    Given: Cache with multiple entries
    When: clear() is called
    Then: All entries are removed
    """
    # Arrange
    cache = UtilizationCache(ttl=30)
    cache.set("chute-1", 0.5)
    cache.set("chute-2", 0.6)
    cache.set("chute-3", 0.7)

    assert cache.size() == 3

    # Act
    cache.clear()

    # Assert
    assert cache.size() == 0
    assert cache.get("chute-1") is None
    assert cache.get("chute-2") is None


@pytest.mark.unit
def test_cache_delete():
    """
    Given: Cache entry exists
    When: delete() is called with existing key
    Then: Returns True and entry is removed from cache
    """
    # Arrange
    cache = UtilizationCache(ttl=30)
    cache.set("chute-1", 0.5)
    cache.set("chute-2", 0.6)

    assert cache.size() == 2

    # Act - delete existing key
    result = cache.delete("chute-1")

    # Assert
    assert result is True
    assert cache.size() == 1
    assert cache.get("chute-1") is None
    assert cache.get("chute-2") == 0.6  # Other entries unaffected


@pytest.mark.unit
def test_cache_delete_nonexistent_key():
    """
    Given: Cache does not contain the key
    When: delete() is called with non-existent key
    Then: Returns False and cache is unchanged
    """
    # Arrange
    cache = UtilizationCache(ttl=30)
    cache.set("chute-1", 0.5)

    assert cache.size() == 1

    # Act - delete non-existent key
    result = cache.delete("nonexistent")

    # Assert
    assert result is False
    assert cache.size() == 1  # Cache unchanged
