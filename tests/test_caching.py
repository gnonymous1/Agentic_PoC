import unittest
import time
from unittest.mock import patch
from core.caching import L1Cache

class TestL1Cache(unittest.TestCase):
    def setUp(self):
        self.cache = L1Cache(max_size=3)

    def test_basic_set_get(self):
        self.cache.set("a", 1)
        self.assertEqual(self.cache.get("a"), 1)
        self.assertIsNone(self.cache.get("b"))

    def test_lru_eviction(self):
        self.cache = L1Cache(max_size=2)
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        self.cache.set("c", 3)  # Should evict "a"

        self.assertIsNone(self.cache.get("a"))
        self.assertEqual(self.cache.get("b"), 2)
        self.assertEqual(self.cache.get("c"), 3)

    def test_lru_update_on_get(self):
        self.cache = L1Cache(max_size=2)
        self.cache.set("a", 1)
        self.cache.set("b", 2)

        # Access "a" to make it most recent
        self.cache.get("a")

        # Set "c", should evict "b" (since "a" was recently accessed)
        self.cache.set("c", 3)

        self.assertIsNone(self.cache.get("b"))
        self.assertEqual(self.cache.get("a"), 1)
        self.assertEqual(self.cache.get("c"), 3)

    def test_expiry_logic(self):
        # Using patch for deterministic time testing
        with patch('time.time') as mock_time:
            now = 1000.0
            mock_time.return_value = now

            self.cache.set("exp", "value", ttl=1)

            # Check before expiry
            mock_time.return_value = now + 0.5
            self.assertEqual(self.cache.get("exp"), "value")

            # Check after expiry
            mock_time.return_value = now + 1.1
            self.assertIsNone(self.cache.get("exp"))

    def test_delete(self):
        self.cache.set("key", "val")
        self.cache.delete("key")
        self.assertIsNone(self.cache.get("key"))

if __name__ == "__main__":
    unittest.main()
