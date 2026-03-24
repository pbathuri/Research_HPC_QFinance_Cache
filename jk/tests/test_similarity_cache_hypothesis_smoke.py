"""Smoke tests for similarity-caching hypothesis layer."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest


class TestSimilarityCacheHypothesisSmoke(unittest.TestCase):
    def test_run_and_export_bundle(self):
        import pandas as pd

        from qhpc_cache.similarity_cache_hypothesis import (
            export_similarity_caching_hypothesis_bundle,
            run_similarity_caching_hypothesis_bundle,
        )

        rows = [
            {
                "workload_family": "event_workloads",
                "workload_variant": "aligned_event_windows",
                "workload_spine_id": "event_window",
                "workload_spine_rank": 4,
                "deterministic_label": "event::a1",
                "source_dataset_labels": "taq_kdb;wrds_link;crsp",
                "source_outputs_used": "event_window_manifest",
                "n_rows": 1200,
                "n_entities": 40,
                "n_dates_or_periods": 8,
                "join_width": 14,
                "feature_dim_before": 14,
                "feature_dim_after": 14,
                "scenario_count": 0,
                "batch_size": 0,
                "parameter_grid_width": 0,
                "timing_p50": 80.0,
                "timing_p90": 120.0,
                "timing_p99": 180.0,
                "timing_p999": 220.0,
                "reuse_proxy_count": 90,
                "reconstruction_proxy_count": 45,
                "cache_proxy_reuse_density": 0.18,
                "cache_proxy_locality_hint": 0.14,
                "cache_proxy_alignment_penalty": 0.02,
                "execution_environment": "darwin::arm64",
                "mac_executable_now": True,
                "deferred_to_hpc": False,
                "metric_lineage": "direct+derived+proxy",
                "unavailable_fields": "",
                "notes": "unit_test",
            },
            {
                "workload_family": "event_workloads",
                "workload_variant": "cache_study_event_analysis",
                "workload_spine_id": "event_window",
                "workload_spine_rank": 4,
                "deterministic_label": "event::a2",
                "source_dataset_labels": "event_window_manifest",
                "source_outputs_used": "cache_study_analysis",
                "n_rows": 1100,
                "n_entities": 38,
                "n_dates_or_periods": 8,
                "join_width": 13,
                "feature_dim_before": 13,
                "feature_dim_after": 13,
                "scenario_count": 0,
                "batch_size": 0,
                "parameter_grid_width": 0,
                "timing_p50": 70.0,
                "timing_p90": 115.0,
                "timing_p99": 170.0,
                "timing_p999": 210.0,
                "reuse_proxy_count": 88,
                "reconstruction_proxy_count": 44,
                "cache_proxy_reuse_density": 0.17,
                "cache_proxy_locality_hint": 0.13,
                "cache_proxy_alignment_penalty": 0.03,
                "execution_environment": "darwin::arm64",
                "mac_executable_now": True,
                "deferred_to_hpc": False,
                "metric_lineage": "direct+derived+proxy",
                "unavailable_fields": "",
                "notes": "unit_test",
            },
            {
                "workload_family": "feature_panel_workloads",
                "workload_variant": "event_aware_raw",
                "workload_spine_id": "feature_panel",
                "workload_spine_rank": 1,
                "deterministic_label": "panel::b1",
                "source_dataset_labels": "crsp.dsf;rates_data;event_tags",
                "source_outputs_used": "feature_panel_variant_manifest",
                "n_rows": 5000,
                "n_entities": 120,
                "n_dates_or_periods": 100,
                "join_width": 28,
                "feature_dim_before": 28,
                "feature_dim_after": 28,
                "scenario_count": 0,
                "batch_size": 0,
                "parameter_grid_width": 0,
                "timing_p50": 180.0,
                "timing_p90": 260.0,
                "timing_p99": 310.0,
                "timing_p999": 340.0,
                "reuse_proxy_count": 150,
                "reconstruction_proxy_count": 20,
                "cache_proxy_reuse_density": 0.22,
                "cache_proxy_locality_hint": 0.0,
                "cache_proxy_alignment_penalty": 0.0,
                "execution_environment": "darwin::arm64",
                "mac_executable_now": True,
                "deferred_to_hpc": False,
                "metric_lineage": "direct+derived+proxy",
                "unavailable_fields": "scenario_count;batch_size",
                "notes": "unit_test",
            },
            {
                "workload_family": "pricing_workloads",
                "workload_variant": "contract_batch_price_plus_greeks",
                "workload_spine_id": "option_pricing",
                "workload_spine_rank": 3,
                "deterministic_label": "pricing::c1",
                "source_dataset_labels": "pricing.py;analytic_pricing.py;rates_data",
                "source_outputs_used": "pricing_workload_manifest",
                "n_rows": 15000,
                "n_entities": 96,
                "n_dates_or_periods": 0,
                "join_width": 64,
                "feature_dim_before": 64,
                "feature_dim_after": 68,
                "scenario_count": 0,
                "batch_size": 64,
                "parameter_grid_width": 64,
                "timing_p50": 320.0,
                "timing_p90": 510.0,
                "timing_p99": 760.0,
                "timing_p999": 760.0,
                "reuse_proxy_count": 220,
                "reconstruction_proxy_count": 180,
                "cache_proxy_reuse_density": 0.35,
                "cache_proxy_locality_hint": 0.0,
                "cache_proxy_alignment_penalty": 0.0,
                "execution_environment": "darwin::arm64",
                "mac_executable_now": True,
                "deferred_to_hpc": True,
                "metric_lineage": "direct+derived+proxy",
                "unavailable_fields": "scenario_count",
                "notes": "unit_test",
            },
        ]
        unified_obs = pd.DataFrame(rows)

        bundle = run_similarity_caching_hypothesis_bundle(
            unified_observations=unified_obs,
            top_k_neighbors=3,
            min_similarity=0.30,
        )
        self.assertIn("similarity_signature_table", bundle)
        self.assertIn("similarity_candidate_summary", bundle)
        self.assertIn("similarity_hypothesis_rankings", bundle)
        self.assertGreater(len(bundle["similarity_signature_table"]), 0)
        self.assertGreater(len(bundle["similarity_hypothesis_rankings"]), 0)

        with tempfile.TemporaryDirectory() as td:
            paths = export_similarity_caching_hypothesis_bundle(bundle=bundle, output_dir=td)
            self.assertTrue(Path(paths["similarity_signature_table_csv"]).exists())
            self.assertTrue(Path(paths["similarity_signature_manifest_json"]).exists())
            self.assertTrue(Path(paths["similarity_hypothesis_manifest_json"]).exists())


if __name__ == "__main__":
    unittest.main()

