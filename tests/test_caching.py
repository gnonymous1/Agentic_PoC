import pytest
import time
from unittest.mock import patch
from core.caching import L1Cache

def test_l1_cache_init():
    """Test default initialization."""
    cache = L1Cache(max_size=100)
    assert cache.max_size == 100
    assert cache.cache == {}
    assert cache.access_order == []

def test_l1_cache_set_get():
    """Test basic set and get operations."""
    cache = L1Cache(max_size=2)
    cache.set("a", 1)
    assert cache.get("a") == 1
    cache.set("b", 2)
    assert cache.get("b") == 2

def test_l1_cache_lru_eviction():
    """Test LRU eviction when cache is full."""
    cache = L1Cache(max_size=2)
    cache.set("a", 1)
    cache.set("b", 2)

    # Access a to make it most recently used
    assert cache.get("a") == 1
    # access_order should be ['b', 'a']

    # Add c, should evict b (least recently used)
    cache.set("c", 3)

    assert cache.get("a") == 1
    assert cache.get("c") == 3
    assert cache.get("b") is None

def test_l1_cache_access_order_update():
    """Test that get operation updates access order."""
    cache = L1Cache(max_size=3)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    # Order: a, b, c (LRU -> MRU)

    # Access a
    cache.get("a")
    # Order: b, c, a

    # Add d, should evict b
    cache.set("d", 4)

    assert cache.get("b") is None
    assert cache.get("c") == 3
    assert cache.get("a") == 1
    assert cache.get("d") == 4

def test_l1_cache_expiration():
    """Test that items expire after TTL."""
    cache = L1Cache()

    # Mock time.time to control time
    with patch("time.time") as mock_time:
        current_time = 1000.0
        mock_time.return_value = current_time

        cache.set("a", 1, ttl=10)
        # Expiry set to 1010.0

        # Check immediately (should exist)
        mock_time.return_value = current_time + 5
        assert cache.get("a") == 1

        # Check after expiry (should be gone)
        mock_time.return_value = current_time + 11
        assert cache.get("a") is None

def test_l1_cache_delete():
    """Test manual deletion."""
    cache = L1Cache()
    cache.set("a", 1)
    assert cache.get("a") == 1

    cache.delete("a")
    assert cache.get("a") is None
    assert "a" not in cache.cache
    assert "a" not in cache.access_order

def test_l1_cache_overwrite():
    """Test overwriting existing keys."""
    cache = L1Cache(max_size=2)
    cache.set("a", 1)
    cache.set("b", 2)

    # Overwrite a
    cache.set("a", 10)

    assert cache.get("a") == 10
    assert len(cache.cache) == 2

    # Check that access order is updated (a becomes MRU)
    # Order was a, b -> now b, a
    cache.set("c", 3)
    # Should evict b
    assert cache.get("b") is None
    assert cache.get("a") == 10
    assert cache.get("c") == 3

def test_l1_cache_zero_size():
    """Test behavior with max_size=0.

    Currently expected to fail/crash until fixed.
    Ideally should handle gracefully by not caching anything.
    """
    cache = L1Cache(max_size=0)

    # This should not crash
    try:
        cache.set("a", 1)
    except IndexError:
        pytest.fail("L1Cache crashed with max_size=0")

    assert cache.get("a") is None
    assert len(cache.cache) == 0

if __name__ == "__main__":
    # Allow running as a script
    pytest.main([__file__])
