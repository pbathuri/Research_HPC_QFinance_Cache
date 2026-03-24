"""Smoke tests for unified observability across workload families."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest


class TestUnifiedObservabilitySmoke(unittest.TestCase):
    def test_run_and_export_unified_bundle(self):
        import pandas as pd

        from qhpc_cache.cache_study_analysis import run_cache_study_analysis
        from qhpc_cache.event_library_compare import run_event_set_comparison
        from qhpc_cache.feature_panel_compare import build_feature_panel_comparison_bundle
        from qhpc_cache.portfolio_risk_workloads import run_portfolio_risk_workload_bundle
        from qhpc_cache.pricing_workloads import run_pricing_workload_bundle
        from qhpc_cache.unified_observability import (
            export_unified_observability_bundle,
            run_unified_observability_bundle,
        )

        raw_events = pd.DataFrame(
            [
                {
                    "qhpc_event_identifier": "covid_crash",
                    "qhpc_event_label": "COVID-19 global equity crash",
                    "window_family_label": "d-1_to_d+1",
                    "intraday_slice_label": "none",
                    "permno": 10107,
                    "symbol": "SPY",
                    "window_start_utc": "2020-03-12T14:30:00+00:00",
                    "window_end_utc": "2020-03-16T20:00:00+00:00",
                    "alignment_match_quality": 0.98,
                    "source_datasets": "taq_kdb;wrds_link;crsp",
                    "join_width": 14,
                    "stage_timing_ms": 120.0,
                },
                {
                    "qhpc_event_identifier": "2022_rate_shock",
                    "qhpc_event_label": "2022 policy-rate shock / duration sell-off",
                    "window_family_label": "d-5_to_d+5",
                    "intraday_slice_label": "none",
                    "permno": 84788,
                    "symbol": "TLT",
                    "window_start_utc": "2022-06-08T14:30:00+00:00",
                    "window_end_utc": "2022-06-22T20:00:00+00:00",
                    "alignment_match_quality": 0.94,
                    "source_datasets": "taq_kdb;wrds_link;crsp",
                    "join_width": 12,
                    "stage_timing_ms": 90.0,
                },
            ]
        )
        event_result = run_event_set_comparison(raw_event_rows=raw_events, record_observability=False)
        cache_result = run_cache_study_analysis(
            normalized_event_rows=event_result["event_window_manifest"],
            record_observability=False,
        )

        daily_rows = []
        for perm in (10001, 10002, 10003, 10004):
            for i in range(90):
                daily_rows.append(
                    {
                        "permno": perm,
                        "date": pd.Timestamp("2020-01-01") + pd.Timedelta(days=i),
                        "close": 100.0 + perm * 0.001 + i * 0.2,
                    }
                )
        daily = pd.DataFrame(daily_rows)
        rates = pd.DataFrame(
            {
                "date": [pd.Timestamp("2020-01-01") + pd.Timedelta(days=i) for i in range(90)],
                "risk_free_rate": [0.03] * 90,
                "source": ["unit_test"] * 90,
            }
        )
        tags = pd.DataFrame(
            {
                "permno": [10001, 10003] * 10,
                "date": [pd.Timestamp("2020-02-01") + pd.Timedelta(days=i) for i in range(10)] * 2,
                "event_tag_any": [1] * 20,
            }
        )

        feature_bundle = build_feature_panel_comparison_bundle(
            ohlcv_long=daily,
            panel_key_base="unified_obs_smoke",
            rates_frame=rates,
            event_tags=tags,
            record_observability=False,
        )
        risk_bundle = run_portfolio_risk_workload_bundle(
            daily_panel=daily,
            rates_frame=rates,
            event_tags=tags,
            n_slices=3,
            slice_size=2,
            record_observability=False,
        )
        pricing_bundle = run_pricing_workload_bundle(
            rates_frame=rates,
            batch_sizes=(4, 6),
            benchmark_contract_count=4,
            max_contracts_mac=24,
            max_paths_mac=2_000,
            seed=7,
            record_observability=False,
        )

        unified = run_unified_observability_bundle(
            event_comparison_result=event_result,
            cache_study_result=cache_result,
            feature_panel_bundle=feature_bundle,
            portfolio_risk_bundle=risk_bundle,
            pricing_bundle=pricing_bundle,
        )
        self.assertIn("unified_workload_observations", unified)
        self.assertIn("unified_workload_rankings", unified)
        self.assertGreater(len(unified["unified_workload_observations"]), 0)
        self.assertGreater(len(unified["unified_workload_rankings"]), 0)

        with tempfile.TemporaryDirectory() as td:
            paths = export_unified_observability_bundle(bundle=unified, output_dir=td)
            self.assertTrue(Path(paths["unified_workload_observations_csv"]).exists())
            self.assertTrue(Path(paths["unified_workload_manifest_json"]).exists())
            self.assertTrue(Path(paths["unified_workload_similarity_manifest_json"]).exists())


if __name__ == "__main__":
    unittest.main()

