"""Tests for the extended cache store with access logging."""

import tempfile
import unittest
from pathlib import Path

from qhpc_cache.cache_store import SimpleCacheStore


class TestCacheStoreLogging(unittest.TestCase):
    def test_access_log_on_miss(self):
        store = SimpleCacheStore(enable_logging=True)
        features = {"S0": 100, "K": 100, "engine": "test"}
        with self.assertRaises(KeyError):
            store.get(features, engine_name="test_engine")
        self.assertEqual(len(store.access_log), 1)
        self.assertFalse(store.access_log[0].hit)

    def test_access_log_on_hit(self):
        store = SimpleCacheStore(enable_logging=True)
        features = {"S0": 100, "K": 100}
        store.put(features, {"price": 10.5}, engine_name="ql", compute_time_ms=5.0)
        val = store.get(features, engine_name="ql")
        self.assertEqual(val["price"], 10.5)
        self.assertTrue(store.access_log[-1].hit)

    def test_stats_include_total_accesses(self):
        store = SimpleCacheStore()
        store.put({"a": 1}, "val")
        store.get({"a": 1})
        stats = store.stats()
        self.assertIn("total_accesses", stats)
        self.assertGreater(stats["total_accesses"], 0)

    def test_flush_csv(self):
        store = SimpleCacheStore()
        store.put({"x": 1}, "v1", engine_name="eng1", compute_time_ms=1.5)
        store.get({"x": 1}, engine_name="eng1")
        with tempfile.TemporaryDirectory() as td:
            path = store.flush_access_log_csv(Path(td) / "log.csv")
            self.assertTrue(path.exists())
            lines = path.read_text().strip().split("\n")
            self.assertGreater(len(lines), 1)

    def test_clear_resets_everything(self):
        store = SimpleCacheStore()
        store.put({"a": 1}, "v")
        store.get({"a": 1})
        store.clear()
        self.assertEqual(store.stats()["entries"], 0)
        self.assertEqual(store.stats()["total_accesses"], 0)

    def test_logging_disabled(self):
        store = SimpleCacheStore(enable_logging=False)
        store.put({"a": 1}, "v")
        store.get({"a": 1})
        self.assertEqual(len(store.access_log), 0)


if __name__ == "__main__":
    unittest.main()
