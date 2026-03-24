"""Smoke tests for canonical feature-panel comparison layer."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest


class TestFeaturePanelCompareSmoke(unittest.TestCase):
    def test_build_and_export_bundle(self):
        import pandas as pd

        from qhpc_cache.feature_panel_compare import (
            LOCKED_PANEL_VARIANTS,
            build_feature_panel_comparison_bundle,
            export_feature_panel_comparison_bundle,
        )

        rows = []
        for perm in (10001, 10002, 10003):
            for i in range(100):
                rows.append(
                    {
                        "permno": perm,
                        "date": pd.Timestamp("2021-01-01") + pd.Timedelta(days=i),
                        "close": 90.0 + perm * 0.001 + i * 0.2,
                    }
                )
        ohlcv = pd.DataFrame(rows)
        rates = pd.DataFrame(
            {
                "date": [pd.Timestamp("2021-01-01") + pd.Timedelta(days=i) for i in range(100)],
                "risk_free_rate": [0.03] * 100,
                "source": ["unit_test"] * 100,
            }
        )
        event_tags = pd.DataFrame(
            {
                "permno": [10001, 10002, 10003] * 10,
                "date": [pd.Timestamp("2021-02-01") + pd.Timedelta(days=i) for i in range(10)] * 3,
                "event_tag_stress": [1] * 30,
            }
        )

        bundle = build_feature_panel_comparison_bundle(
            ohlcv,
            panel_key_base="unit_panel",
            rates_frame=rates,
            event_tags=event_tags,
            record_observability=False,
        )
        self.assertIn("variant_manifest", bundle)
        labels = set(bundle["variant_manifest"]["panel_variant_label"].tolist())
        self.assertEqual(labels, set(LOCKED_PANEL_VARIANTS))
        self.assertEqual(len(bundle["rankings"]), 4)

        with tempfile.TemporaryDirectory() as td:
            paths = export_feature_panel_comparison_bundle(bundle=bundle, output_dir=td)
            self.assertTrue(Path(paths["feature_panel_variant_manifest_csv"]).exists())
            self.assertTrue(Path(paths["feature_panel_comparison_manifest_json"]).exists())


if __name__ == "__main__":
    unittest.main()
