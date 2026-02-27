import unittest
import time
from core.caching import L1Cache

class TestL1Cache(unittest.TestCase):
    def setUp(self):
        self.cache = L1Cache(max_size=3)

    def test_l1_cache_expiry(self):
        """Test that expired items are removed and return None."""
        key = "test_key"
        value = "test_value"
        ttl = 0.5  # 0.5 seconds

        # Set value with short TTL
        self.cache.set(key, value, ttl=ttl)

        # Verify immediate retrieval
        self.assertEqual(self.cache.get(key), value, "Value should be retrievable before expiry")

        # Wait for expiry
        time.sleep(ttl + 0.1)

        # Verify retrieval after expiry
        result = self.cache.get(key)
        self.assertIsNone(result, "Value should be None after expiry")

        # Verify key is removed from internal storage
        self.assertNotIn(key, self.cache.cache, "Key should be removed from cache after expiry")

    def test_l1_cache_eviction(self):
        """Test LRU eviction when max_size is exceeded."""
        # Fill cache to max_size (3)
        self.cache.set("k1", "v1")
        self.cache.set("k2", "v2")
        self.cache.set("k3", "v3")

        self.assertIn("k1", self.cache.cache)
        self.assertIn("k2", self.cache.cache)
        self.assertIn("k3", self.cache.cache)

        # Add one more to trigger eviction
        self.cache.set("k4", "v4")

        # k1 was oldest (inserted first), so it should be gone
        self.assertNotIn("k1", self.cache.cache, "Oldest key should be evicted")
        self.assertIn("k4", self.cache.cache)
        self.assertEqual(len(self.cache.cache), 3)

    def test_l1_cache_access_order_update(self):
        """Test that accessing a key updates its LRU position."""
        self.cache.set("k1", "v1")
        self.cache.set("k2", "v2")
        self.cache.set("k3", "v3")

        # Access k1, making it most recently used
        self.cache.get("k1")

        # Add k4, should evict k2 (now the oldest) instead of k1
        self.cache.set("k4", "v4")

        self.assertIn("k1", self.cache.cache, "Accessed key should not be evicted")
        self.assertNotIn("k2", self.cache.cache, "Oldest unaccessed key should be evicted")
        self.assertIn("k4", self.cache.cache)

if __name__ == "__main__":
    unittest.main()
