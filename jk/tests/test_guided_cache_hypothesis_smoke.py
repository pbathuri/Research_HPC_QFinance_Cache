"""Smoke tests for guided-cache architecture hypothesis layer."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest


class TestGuidedCacheHypothesisSmoke(unittest.TestCase):
    def test_run_and_export_guided_bundle(self):
        import pandas as pd

        from qhpc_cache.guided_cache_hypothesis import (
            export_guided_cache_hypothesis_bundle,
            run_guided_cache_hypothesis_bundle,
        )

        unified_obs = pd.DataFrame(
            [
                {
                    "workload_family": "event_workloads",
                    "workload_variant": "event_library_compare",
                    "workload_spine_id": "event_window",
                    "workload_spine_rank": 4,
                    "deterministic_label": "event::1",
                    "source_dataset_labels": "taq;crsp",
                    "source_outputs_used": "event_library_comparison",
                    "n_rows": 2000,
                    "n_entities": 42,
                    "n_dates_or_periods": 12,
                    "join_width": 14,
                    "feature_dim_before": 14,
                    "feature_dim_after": 14,
                    "scenario_count": 0,
                    "batch_size": 0,
                    "parameter_grid_width": 0,
                    "timing_p50": 80.0,
                    "timing_p90": 120.0,
                    "timing_p99": 140.0,
                    "timing_p999": 160.0,
                    "reuse_proxy_count": 80,
                    "reconstruction_proxy_count": 50,
                    "cache_proxy_reuse_density": 0.2,
                    "cache_proxy_locality_hint": 0.12,
                    "cache_proxy_alignment_penalty": 0.02,
                    "execution_environment": "darwin::arm64",
                    "mac_executable_now": True,
                    "deferred_to_hpc": False,
                    "metric_lineage": "direct+derived+proxy",
                    "unavailable_fields": "",
                    "notes": "test",
                },
                {
                    "workload_family": "feature_panel_workloads",
                    "workload_variant": "event_aware_raw",
                    "workload_spine_id": "feature_panel",
                    "workload_spine_rank": 1,
                    "deterministic_label": "panel::1",
                    "source_dataset_labels": "crsp.dsf;rates",
                    "source_outputs_used": "feature_panel_summary",
                    "n_rows": 5000,
                    "n_entities": 100,
                    "n_dates_or_periods": 90,
                    "join_width": 28,
                    "feature_dim_before": 28,
                    "feature_dim_after": 28,
                    "scenario_count": 0,
                    "batch_size": 0,
                    "parameter_grid_width": 0,
                    "timing_p50": 160.0,
                    "timing_p90": 220.0,
                    "timing_p99": 260.0,
                    "timing_p999": 280.0,
                    "reuse_proxy_count": 140,
                    "reconstruction_proxy_count": 30,
                    "cache_proxy_reuse_density": 0.24,
                    "cache_proxy_locality_hint": 0.0,
                    "cache_proxy_alignment_penalty": 0.0,
                    "execution_environment": "darwin::arm64",
                    "mac_executable_now": True,
                    "deferred_to_hpc": False,
                    "metric_lineage": "direct+derived+proxy",
                    "unavailable_fields": "",
                    "notes": "test",
                },
                {
                    "workload_family": "pricing_workloads",
                    "workload_variant": "contract_batch_price_plus_greeks",
                    "workload_spine_id": "option_pricing",
                    "workload_spine_rank": 3,
                    "deterministic_label": "pricing::1",
                    "source_dataset_labels": "pricing;rates",
                    "source_outputs_used": "pricing_workload_summary",
                    "n_rows": 10000,
                    "n_entities": 80,
                    "n_dates_or_periods": 0,
                    "join_width": 64,
                    "feature_dim_before": 64,
                    "feature_dim_after": 68,
                    "scenario_count": 0,
                    "batch_size": 64,
                    "parameter_grid_width": 64,
                    "timing_p50": 350.0,
                    "timing_p90": 520.0,
                    "timing_p99": 700.0,
                    "timing_p999": 700.0,
                    "reuse_proxy_count": 220,
                    "reconstruction_proxy_count": 170,
                    "cache_proxy_reuse_density": 0.35,
                    "cache_proxy_locality_hint": 0.0,
                    "cache_proxy_alignment_penalty": 0.0,
                    "execution_environment": "darwin::arm64",
                    "mac_executable_now": True,
                    "deferred_to_hpc": True,
                    "metric_lineage": "direct+derived+proxy",
                    "unavailable_fields": "",
                    "notes": "test",
                },
            ]
        )
        unified_rankings = pd.DataFrame(
            [
                {
                    "ranking_axis": "family_cache_study_value",
                    "workload_family": "pricing_workloads",
                    "workload_variant": "",
                    "score": 0.85,
                    "rank": 1,
                    "priority_label": "",
                    "notes": "test",
                },
                {
                    "ranking_axis": "family_cache_study_value",
                    "workload_family": "feature_panel_workloads",
                    "workload_variant": "",
                    "score": 0.70,
                    "rank": 2,
                    "priority_label": "",
                    "notes": "test",
                },
                {
                    "ranking_axis": "family_cache_study_value",
                    "workload_family": "event_workloads",
                    "workload_variant": "",
                    "score": 0.65,
                    "rank": 3,
                    "priority_label": "",
                    "notes": "test",
                },
            ]
        )
        similarity_candidates = pd.DataFrame(
            [
                {
                    "similarity_candidate_id": "c1",
                    "anchor_workload_family": "pricing_workloads",
                    "anchor_workload_variant": "contract_batch_price_plus_greeks",
                    "anchor_deterministic_label": "pricing::1",
                    "neighbor_workload_family": "pricing_workloads",
                    "neighbor_workload_variant": "contract_batch_price_plus_greeks",
                    "neighbor_deterministic_label": "pricing::1",
                    "analysis_scope": "within_family",
                    "operational_similarity_type": "pricing_batch_similarity",
                    "similarity_relationship": "exact_identity_similarity",
                    "overall_similarity": 1.0,
                    "structure_distance": 0.0,
                    "parameter_distance": 0.0,
                    "timing_distance": 0.0,
                    "reuse_distance": 0.0,
                    "exact_identity_match": True,
                    "neighborhood_match": True,
                    "reuse_affinity": 1.0,
                    "reuse_density_affinity": 0.35,
                    "deferred_to_hpc_pair": True,
                    "evidence_label": "measured",
                },
                {
                    "similarity_candidate_id": "c2",
                    "anchor_workload_family": "feature_panel_workloads",
                    "anchor_workload_variant": "event_aware_raw",
                    "anchor_deterministic_label": "panel::1",
                    "neighbor_workload_family": "event_workloads",
                    "neighbor_workload_variant": "event_library_compare",
                    "neighbor_deterministic_label": "event::1",
                    "analysis_scope": "cross_family",
                    "operational_similarity_type": "cross_family_shape_similarity",
                    "similarity_relationship": "parameter_neighborhood_similarity",
                    "overall_similarity": 0.62,
                    "structure_distance": 0.20,
                    "parameter_distance": 0.25,
                    "timing_distance": 0.30,
                    "reuse_distance": 0.22,
                    "exact_identity_match": False,
                    "neighborhood_match": True,
                    "reuse_affinity": 0.68,
                    "reuse_density_affinity": 0.22,
                    "deferred_to_hpc_pair": False,
                    "evidence_label": "proxy-supported",
                },
            ]
        )
        similarity_rankings = pd.DataFrame(
            [
                {
                    "hypothesis_id": "supported_exact_identity_neighbors",
                    "hypothesis_focus": "Exact candidates exist",
                    "evidence_level": "measured",
                    "strength_score": 1.0,
                    "notes": "test",
                    "rank": 1,
                },
                {
                    "hypothesis_id": "deferred_hardware_cache_behavior_proof",
                    "hypothesis_focus": "Hardware proof deferred",
                    "evidence_level": "deferred",
                    "strength_score": 0.0,
                    "notes": "test",
                    "rank": 2,
                },
            ]
        )

        tables = {
            "event_library_comparison": pd.DataFrame(
                [{"event_set_id": "set_a", "defined_event_count": 1, "materialized_row_count": 5}]
            ),
            "feature_panel_comparison_summary": pd.DataFrame(
                [{"panel_variant_label": "event_aware_raw", "n_rows": 5000}]
            ),
            "portfolio_risk_rankings": pd.DataFrame(
                [{"risk_workload_variant_label": "portfolio_slice_scenario_risk", "rank": 1}]
            ),
            "pricing_workload_rankings": pd.DataFrame(
                [{"workload_variant_label": "contract_batch_price_plus_greeks", "rank": 1}]
            ),
            "unified_workload_observations": unified_obs,
            "unified_workload_rankings": unified_rankings,
            "similarity_candidate_summary": similarity_candidates,
            "similarity_hypothesis_rankings": similarity_rankings,
        }

        bundle = run_guided_cache_hypothesis_bundle(evidence_tables=tables)
        self.assertGreater(len(bundle["guided_cache_evidence_matrix"]), 0)
        self.assertGreater(len(bundle["guided_cache_supported_claims"]), 0)
        self.assertGreater(len(bundle["guided_cache_hypothesis_rankings"]), 0)

        with tempfile.TemporaryDirectory() as td:
            paths = export_guided_cache_hypothesis_bundle(bundle=bundle, output_dir=td)
            self.assertTrue(Path(paths["guided_cache_evidence_matrix_csv"]).exists())
            self.assertTrue(Path(paths["guided_cache_hypothesis_manifest_json"]).exists())
            self.assertTrue(Path(paths["guided_cache_architecture_hypothesis_md"]).exists())


if __name__ == "__main__":
    unittest.main()

