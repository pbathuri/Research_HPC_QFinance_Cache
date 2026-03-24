"""Tests for advanced cache research metrics."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from qhpc_cache.cache_metrics import (
    CacheAccessRecord,
    CacheResearchTracker,
    compare_policies,
    format_cache_metric_report,
)


class TestCacheResearchTracker(unittest.TestCase):

    def test_empty_tracker(self) -> None:
        t = CacheResearchTracker(policy_name="empty")
        s = t.summary()
        self.assertEqual(s["total_lookups"], 0)
        self.assertEqual(s["exact_hit_rate"], 0.0)
        self.assertEqual(s["miss_rate"], 0.0)

    def test_hit_miss_rates(self) -> None:
        t = CacheResearchTracker(policy_name="test")
        t.record_access(CacheAccessRecord(key="a", hit=True, compute_time_saved=0.1, compute_time_if_miss=0.1))
        t.record_access(CacheAccessRecord(key="b", hit=False, compute_time_if_miss=0.1))
        t.record_access(CacheAccessRecord(key="a", hit=True, compute_time_saved=0.1, compute_time_if_miss=0.1))
        t.record_access(CacheAccessRecord(key="c", hit=False, similarity_hit=True, compute_time_saved=0.05, compute_time_if_miss=0.1))
        s = t.summary()
        self.assertEqual(s["exact_hits"], 2)
        self.assertEqual(s["similarity_hits"], 1)
        self.assertEqual(s["misses"], 1)
        self.assertAlmostEqual(s["exact_hit_rate"], 0.5)
        self.assertAlmostEqual(s["similarity_hit_rate"], 0.25)

    def test_reuse_distance(self) -> None:
        t = CacheResearchTracker(policy_name="reuse")
        t.record_access(CacheAccessRecord(key="x", hit=False, compute_time_if_miss=0.1))
        t.record_access(CacheAccessRecord(key="y", hit=False, compute_time_if_miss=0.1))
        t.record_access(CacheAccessRecord(key="x", hit=True, compute_time_saved=0.1, compute_time_if_miss=0.1))
        self.assertGreater(t.locality_score, 0)
        self.assertLessEqual(t.locality_score, 1.0)

    def test_cache_efficiency(self) -> None:
        t = CacheResearchTracker(policy_name="eff")
        t.record_access(CacheAccessRecord(key="a", hit=True, compute_time_saved=1.0, compute_time_if_miss=1.0))
        t.record_access(CacheAccessRecord(key="b", hit=False, compute_time_if_miss=1.0))
        self.assertAlmostEqual(t.cache_efficiency, 0.5)

    def test_compare_policies(self) -> None:
        t1 = CacheResearchTracker(policy_name="A")
        t2 = CacheResearchTracker(policy_name="B")
        t1.record_access(CacheAccessRecord(key="x", hit=True, compute_time_saved=0.1, compute_time_if_miss=0.1))
        t2.record_access(CacheAccessRecord(key="x", hit=False, compute_time_if_miss=0.1))
        result = compare_policies([t1, t2])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["policy_name"], "A")

    def test_format_report(self) -> None:
        t = CacheResearchTracker(policy_name="demo")
        t.record_access(CacheAccessRecord(key="k", hit=True, compute_time_saved=0.1, compute_time_if_miss=0.1))
        report = format_cache_metric_report([t])
        self.assertIn("demo", report)
        self.assertIn("Cache Policy Comparison", report)

    def test_flush_to_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["QHPC_METRICS_DIR"] = tmp
            try:
                t = CacheResearchTracker(policy_name="csv_test")
                t.record_access(CacheAccessRecord(key="k", hit=True, compute_time_saved=0.1, compute_time_if_miss=0.1))
                t.flush_to_csv("test_run")
                self.assertTrue((Path(tmp) / "cache_metrics.csv").exists())
            finally:
                os.environ.pop("QHPC_METRICS_DIR", None)


if __name__ == "__main__":
    unittest.main()
