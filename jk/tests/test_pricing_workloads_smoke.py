"""Smoke tests for canonical option-pricing workload family bundle."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest


class TestPricingWorkloadsSmoke(unittest.TestCase):
    def test_run_and_export_bundle(self):
        import pandas as pd

        from qhpc_cache.pricing_workloads import (
            export_pricing_workload_bundle,
            run_pricing_workload_bundle,
        )

        rates = pd.DataFrame(
            {
                "date": [pd.Timestamp("2020-01-02"), pd.Timestamp("2020-01-03")],
                "risk_free_rate": [0.03, 0.031],
                "source": ["unit_test", "unit_test"],
            }
        )

        bundle = run_pricing_workload_bundle(
            rates_frame=rates,
            batch_sizes=(4, 6),
            benchmark_contract_count=4,
            max_contracts_mac=24,
            max_paths_mac=2_000,
            seed=7,
            record_observability=False,
        )
        self.assertIn("pricing_model_family_summary", bundle)
        self.assertIn("pricing_workload_rankings", bundle)
        self.assertGreater(len(bundle["pricing_workload_manifest"]), 0)
        self.assertGreater(len(bundle["pricing_model_family_summary"]), 0)
        self.assertGreater(len(bundle["pricing_workload_rankings"]), 0)

        with tempfile.TemporaryDirectory() as td:
            paths = export_pricing_workload_bundle(bundle=bundle, output_dir=td)
            self.assertTrue(Path(paths["pricing_workload_manifest"]).exists())
            self.assertTrue(Path(paths["pricing_model_family_manifest_json"]).exists())
            self.assertTrue(Path(paths["pricing_batch_manifest_json"]).exists())


if __name__ == "__main__":
    unittest.main()

