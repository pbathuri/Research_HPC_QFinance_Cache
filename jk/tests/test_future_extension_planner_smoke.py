"""Smoke tests for optional HPC/QHPC future extension planning."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest


class TestFutureExtensionPlannerSmoke(unittest.TestCase):
    def test_run_and_export_future_extension_bundle(self):
        import pandas as pd

        from qhpc_cache.future_extension_planner import (
            export_future_extension_planning_bundle,
            run_future_extension_planning_bundle,
        )

        source_tables = {
            "unified_workload_observations": pd.DataFrame(
                [
                    {
                        "workload_family": "event_workloads",
                        "workload_variant": "event_lib",
                        "n_rows": 2000,
                        "timing_p90": 120.0,
                        "reuse_proxy_count": 80,
                        "deferred_to_hpc": False,
                    },
                    {
                        "workload_family": "pricing_workloads",
                        "workload_variant": "pricing_batch",
                        "n_rows": 15000,
                        "timing_p90": 520.0,
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
            "guided_cache_candidate_workloads": pd.DataFrame(
                [
                    {
                        "workload_family": "pricing_workloads",
                        "workload_variant": "pricing_batch",
                        "deterministic_label": "pricing::1",
                        "candidate_layer": "similarity_aware_reuse_layer",
                        "candidate_evidence_level": "proxy-supported",
                        "candidate_score": 0.95,
                    },
                    {
                        "workload_family": "event_workloads",
                        "workload_variant": "event_lib",
                        "deterministic_label": "event::1",
                        "candidate_layer": "exact_match_reuse_layer",
                        "candidate_evidence_level": "measured",
                        "candidate_score": 0.72,
                    },
                ]
            ),
            "similarity_candidate_summary": pd.DataFrame(),
            "paper_claims_matrix": pd.DataFrame(),
        }

        bundle = run_future_extension_planning_bundle(source_tables=source_tables)
        self.assertGreater(len(bundle["future_extension_workload_priority"]), 0)
        self.assertGreater(len(bundle["pmu_validation_priority"]), 0)
        self.assertGreater(len(bundle["bigred200_candidate_workloads"]), 0)
        self.assertGreater(len(bundle["phase2_research_program_summary"]), 0)

        with tempfile.TemporaryDirectory() as td:
            paths = export_future_extension_planning_bundle(bundle=bundle, output_dir=td)
            self.assertTrue(Path(paths["future_extension_workload_priority_csv"]).exists())
            self.assertTrue(Path(paths["pmu_validation_manifest_json"]).exists())
            self.assertTrue(Path(paths["plot_future_extension_roadmap_png"]).exists())


if __name__ == "__main__":
    unittest.main()

