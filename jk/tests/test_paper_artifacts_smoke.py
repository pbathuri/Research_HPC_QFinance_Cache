"""Smoke tests for formal paper-packaging artifacts."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest


class TestPaperArtifactsSmoke(unittest.TestCase):
    def test_run_and_export_paper_packaging(self):
        import pandas as pd

        from qhpc_cache.paper_artifacts import (
            export_paper_packaging_bundle,
            run_paper_packaging_bundle,
        )

        source_tables = {
            "event_library_comparison": pd.DataFrame(
                [
                    {
                        "event_set_id": "set_a",
                        "defined_event_count": 1,
                        "materialized_row_count": 5,
                        "aligned_permno_count": 5,
                        "timing_p90_ms": 60.0,
                        "cache_proxy_reuse_density": 0.1,
                    }
                ]
            ),
            "cache_study_rankings": pd.DataFrame(
                [{"event_set_id": "set_a", "cache_study_value_score": 0.62}]
            ),
            "feature_panel_comparison_summary": pd.DataFrame(
                [
                    {
                        "panel_variant_label": "event_aware_raw",
                        "event_aware": True,
                        "condensed": False,
                        "n_rows": 1000,
                        "n_securities": 20,
                        "n_dates": 50,
                        "feature_count_before_condense": 8,
                        "feature_count_after_condense": 8,
                        "panel_build_timing_ms": 80.0,
                        "reuse_density": 0.02,
                    }
                ]
            ),
            "portfolio_risk_rankings": pd.DataFrame(
                [
                    {
                        "risk_workload_variant_label": "portfolio_slice_scenario_risk",
                        "n_securities": 40,
                        "recomputation_count": 20,
                        "reuse_proxy": 0.8,
                        "cache_study_value_score": 0.75,
                        "rank": 1,
                    }
                ]
            ),
            "pricing_workload_rankings": pd.DataFrame(
                [
                    {
                        "workload_variant_label": "contract_batch_price_plus_greeks",
                        "cache_study_value_score": 1.1,
                        "repeat_score": 5.0,
                        "size_score": 8.0,
                        "greek_bonus": 1.2,
                        "rank": 1,
                    }
                ]
            ),
            "unified_workload_observations": pd.DataFrame(
                [
                    {
                        "workload_family": "event_workloads",
                        "workload_variant": "event_library_compare",
                        "n_rows": 1200,
                        "timing_p90": 120.0,
                        "reuse_proxy_count": 80,
                        "deferred_to_hpc": False,
                    },
                    {
                        "workload_family": "pricing_workloads",
                        "workload_variant": "contract_batch_price_plus_greeks",
                        "n_rows": 12000,
                        "timing_p90": 480.0,
                        "reuse_proxy_count": 220,
                        "deferred_to_hpc": True,
                    },
                ]
            ),
            "unified_workload_rankings": pd.DataFrame(
                [
                    {
                        "ranking_axis": "family_cache_study_value",
                        "workload_family": "pricing_workloads",
                        "workload_variant": "",
                        "score": 0.82,
                        "rank": 1,
                    },
                    {
                        "ranking_axis": "family_cache_study_value",
                        "workload_family": "event_workloads",
                        "workload_variant": "",
                        "score": 0.63,
                        "rank": 2,
                    },
                ]
            ),
            "similarity_hypothesis_rankings": pd.DataFrame(
                [
                    {
                        "hypothesis_id": "supported_similarity_clusters_present",
                        "evidence_level": "derived",
                        "strength_score": 4.0,
                        "rank": 1,
                    }
                ]
            ),
            "guided_cache_evidence_matrix": pd.DataFrame(
                [
                    {
                        "claim_id": "claim_exact_match",
                        "claim_area": "exact_match_reuse_layer",
                        "architecture_component": "exact_match_reuse_layer",
                        "source_families": "all",
                        "source_artifacts": "similarity_candidate_summary.csv",
                        "evidence_level": "measured",
                        "support_strength": 2.0,
                        "claim_text": "Exact candidates exist",
                        "what_strengthens_later": "replay validation",
                    },
                    {
                        "claim_id": "claim_hardware_deferred",
                        "claim_area": "deferred_hardware_aware_layer",
                        "architecture_component": "deferred_hardware_aware_layer",
                        "source_families": "all",
                        "source_artifacts": "mac_vs_hpc_policy",
                        "evidence_level": "deferred",
                        "support_strength": 1.0,
                        "claim_text": "PMU-level hardware proof deferred",
                        "what_strengthens_later": "HPC PMU studies",
                    },
                ]
            ),
        }

        bundle = run_paper_packaging_bundle(source_tables=source_tables)
        self.assertIn("paper_tables", bundle)
        self.assertIn("paper_claims_matrix", bundle)
        self.assertGreater(len(bundle["paper_results_tables"]), 0)

        with tempfile.TemporaryDirectory() as td:
            paths = export_paper_packaging_bundle(bundle=bundle, output_dir=td)
            self.assertTrue(Path(paths["paper_results_tables_csv"]).exists())
            self.assertTrue(Path(paths["paper_packaging_manifest_json"]).exists())
            self.assertTrue(Path(paths["figure_guided_cache_evidence_png"]).exists())
            self.assertTrue(Path(paths["table_guided_cache_claims_summary_csv"]).exists())


if __name__ == "__main__":
    unittest.main()

