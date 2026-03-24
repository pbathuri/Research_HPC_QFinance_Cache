"""Smoke tests for canonical portfolio risk workload bundle."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest


class TestPortfolioRiskWorkloadsSmoke(unittest.TestCase):
    def test_run_and_export_bundle(self):
        import pandas as pd

        from qhpc_cache.portfolio_risk_workloads import (
            export_portfolio_risk_workload_bundle,
            run_portfolio_risk_workload_bundle,
        )

        rows = []
        for perm in (10001, 10002, 10003, 10004, 10005, 10006):
            for i in range(120):
                rows.append(
                    {
                        "permno": perm,
                        "date": pd.Timestamp("2020-01-01") + pd.Timedelta(days=i),
                        "close": 75.0 + perm * 0.002 + i * 0.1,
                    }
                )
        daily = pd.DataFrame(rows)
        rates = pd.DataFrame(
            {
                "date": [pd.Timestamp("2020-01-01") + pd.Timedelta(days=i) for i in range(120)],
                "risk_free_rate": [0.03] * 120,
                "source": ["unit_test"] * 120,
            }
        )
        tags = pd.DataFrame(
            {
                "permno": [10001, 10003, 10005] * 12,
                "date": [pd.Timestamp("2020-02-01") + pd.Timedelta(days=i) for i in range(12)] * 3,
                "event_tag_any": [1] * 36,
            }
        )

        bundle = run_portfolio_risk_workload_bundle(
            daily_panel=daily,
            rates_frame=rates,
            event_tags=tags,
            n_slices=4,
            slice_size=3,
            record_observability=False,
        )
        self.assertIn("historical_risk_summary", bundle)
        self.assertIn("portfolio_scenario_summary", bundle)
        self.assertGreater(len(bundle["historical_risk_summary"]), 0)
        self.assertGreater(len(bundle["portfolio_scenario_summary"]), 0)
        self.assertEqual(len(bundle["portfolio_risk_rankings"]), 2)

        with tempfile.TemporaryDirectory() as td:
            paths = export_portfolio_risk_workload_bundle(bundle=bundle, output_dir=td)
            self.assertTrue(Path(paths["portfolio_risk_workload_manifest_csv"]).exists())
            self.assertTrue(Path(paths["portfolio_risk_workload_manifest_json"]).exists())


if __name__ == "__main__":
    unittest.main()
