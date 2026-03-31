"""Smoke tests for WRDS query layout (no live connection required)."""

import unittest


class TestWrdsQueries(unittest.TestCase):
    def test_roadmap_non_empty(self):
        from qhpc_cache.wrds_queries import WRDS_INTEGRATION_ROADMAP

        self.assertGreater(len(WRDS_INTEGRATION_ROADMAP), 0)

    def test_canonical_wrds_tables(self):
        from qhpc_cache import wrds_queries as wq

        self.assertEqual(wq.CANONICAL_CRSP_TFZ_DLY, ("crsp", "tfz_dly"))
        self.assertEqual(wq.CANONICAL_CRSP_TFZ_MTH, ("crsp", "tfz_mth"))
        self.assertEqual(wq.CANONICAL_CRSP_STOCKNAMES, ("crsp", "stocknames"))
        self.assertEqual(wq.CANONICAL_TAQ_CRSP_TCLINK[0], "wrdsapps_link_crsp_taq")
        self.assertEqual(wq.CANONICAL_TAQ_CRSP_TCLINK[1], "tclink")

    def test_roadmap_is_canonical_in_wrds_queries(self):
        from qhpc_cache import wrds_queries as wq

        roadmap = wq.WRDS_INTEGRATION_ROADMAP
        self.assertGreater(len(roadmap), 0)
        self.assertEqual(
            sorted(slot.priority_rank for slot in roadmap),
            list(range(1, len(roadmap) + 1)),
        )


class TestWorkloadMetricsRow(unittest.TestCase):
    def test_workload_row_writes(self):
        import tempfile
        from pathlib import Path

        from qhpc_cache.cache_metrics import CacheAccessRecord, CacheResearchTracker
        from qhpc_cache.metrics_sink import WorkloadCacheObservationRow, append_metric_row

        tr = CacheResearchTracker(policy_name="p1")
        tr.record_access(CacheAccessRecord("k1", True))
        row = WorkloadCacheObservationRow(
            run_id="t1",
            workload_family="wl_test",
            portfolio_family="pf1",
            model_family="m1",
            pipeline_stage="test",
            exact_hit_rate=1.0,
        )
        with tempfile.TemporaryDirectory() as td:
            import os

            os.environ["QHPC_METRICS_DIR"] = td
            p = append_metric_row("workload_test.csv", row)
            self.assertTrue(Path(p).exists())


if __name__ == "__main__":
    unittest.main()
