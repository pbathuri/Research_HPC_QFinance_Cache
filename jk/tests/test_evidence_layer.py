"""Tests for the evidence layer: reuse-distance, locality, economics,
workload registry, HPC provenance, evidence bundle, and budget tracking."""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from qhpc_cache.reuse_distance_analytics import (
    ReuseDistanceRow,
    LocalityMetrics,
    WorkingSetWindow,
    compute_reuse_distances,
    compute_locality_metrics,
    compute_working_set_timeline,
)
from qhpc_cache.cache_economics import (
    CacheEconomicsSummary,
    compute_economics_from_rows,
    compute_similarity_decomposition,
    compute_policy_frontier,
    SimilarityAcceptanceRow,
)
from qhpc_cache.workload_registry import (
    WORKLOAD_FAMILY_REGISTRY,
    get_family_meta,
    get_all_family_metadata,
    get_finance_representative_families,
    get_synthetic_control_families,
    build_workload_regime_summary,
)
from qhpc_cache.hpc_provenance import (
    detect_execution_context,
    build_hpc_provenance_fields,
    build_hpc_execution_summary,
    detect_available_engines,
)
from qhpc_cache.run_profiles import (
    BudgetUtilization,
    RUN_PROFILES,
    get_profile,
    list_profiles,
    generate_slurm_script,
    aggregate_runs,
)


class TestReuseDistanceAnalytics(unittest.TestCase):
    def test_exact_reuse_distance_computation(self) -> None:
        keys = ["a", "b", "c", "a", "b", "a"]
        rows = compute_reuse_distances(keys)
        self.assertEqual(len(rows), 6)
        self.assertTrue(rows[0].first_seen_flag)
        self.assertTrue(math.isnan(rows[0].exact_reuse_distance))
        self.assertEqual(rows[0].reuse_distance_bucket, "first_access")
        self.assertEqual(rows[3].exact_reuse_distance, 2.0)  # a at 0, reappears at 3
        self.assertFalse(rows[3].first_seen_flag)
        self.assertEqual(rows[5].exact_reuse_distance, 1.0)  # a at 3, reappears at 5

    def test_similarity_reuse_distance(self) -> None:
        keys = ["a", "b", "c", "d"]
        sim_groups = ["g1", "g2", "g1", "g2"]
        rows = compute_reuse_distances(keys, similarity_group_stream=sim_groups)
        self.assertTrue(math.isnan(rows[0].similarity_reuse_distance))
        self.assertEqual(rows[2].similarity_reuse_distance, 1.0)  # g1 at 0, reappears at 2

    def test_reuse_distance_buckets(self) -> None:
        keys = ["a", "a", "b", "c", "d", "e", "a"]
        rows = compute_reuse_distances(keys)
        self.assertEqual(rows[1].reuse_distance_bucket, "immediate_reuse")
        self.assertEqual(rows[6].reuse_distance_bucket, "near_reuse_1_4")


class TestLocalityMetrics(unittest.TestCase):
    def test_empty_stream(self) -> None:
        m = compute_locality_metrics([])
        self.assertEqual(m.locality_regime, "empty")
        self.assertEqual(m.total_accesses, 0)

    def test_high_locality_stream(self) -> None:
        keys = ["a", "a", "a", "b", "b", "a", "a", "b"]
        m = compute_locality_metrics(keys)
        self.assertGreater(m.temporal_locality_score, 0.3)
        self.assertGreaterEqual(m.hotset_concentration_ratio, 0.0)
        self.assertEqual(m.total_accesses, 8)
        self.assertEqual(m.unique_keys, 2)

    def test_streaming_no_reuse(self) -> None:
        keys = [f"key_{i}" for i in range(100)]
        m = compute_locality_metrics(keys)
        self.assertEqual(m.one_hit_wonder_fraction, 1.0)
        self.assertEqual(m.unique_keys, 100)

    def test_locality_regime_classification(self) -> None:
        keys = ["a"] * 50 + ["b"] * 30 + ["c"] * 20
        m = compute_locality_metrics(keys)
        self.assertIn(m.locality_regime, [
            "strong_temporal_locality", "moderate_temporal_locality",
            "skewed_popularity", "mixed_or_indeterminate",
        ])


class TestWorkingSetTimeline(unittest.TestCase):
    def test_basic_timeline(self) -> None:
        keys = ["a", "b", "a", "c", "b", "d", "a", "e"]
        hits = [False, False, True, False, True, False, True, False]
        windows = compute_working_set_timeline(keys, hits, window_size=4)
        self.assertGreater(len(windows), 0)
        self.assertEqual(windows[0].time_index_start, 0)
        self.assertEqual(windows[0].time_index_end, 4)
        self.assertGreater(windows[0].working_set_size, 0)

    def test_empty_stream(self) -> None:
        self.assertEqual(compute_working_set_timeline([], []), [])


class TestCacheEconomics(unittest.TestCase):
    def test_economics_with_hits_and_misses(self) -> None:
        rows = [
            {"cache_hit": True, "similarity_hit": False, "total_runtime_ms": 0.1,
             "pricing_compute_time_ms": 0.0, "compute_avoided_proxy": 5.0, "time_saved_proxy": 4.9},
            {"cache_hit": False, "similarity_hit": False, "total_runtime_ms": 5.0,
             "pricing_compute_time_ms": 5.0, "compute_avoided_proxy": 0.0, "time_saved_proxy": 0.0},
            {"cache_hit": True, "similarity_hit": False, "total_runtime_ms": 0.1,
             "pricing_compute_time_ms": 0.0, "compute_avoided_proxy": 5.0, "time_saved_proxy": 4.9},
        ]
        econ = compute_economics_from_rows(rows, label="test")
        self.assertEqual(econ.exact_hits, 2)
        self.assertEqual(econ.misses, 1)
        self.assertTrue(econ.net_benefit_flag)
        self.assertGreater(econ.net_cache_value_ms, 0)

    def test_zero_hit_economics(self) -> None:
        rows = [
            {"cache_hit": False, "similarity_hit": False, "total_runtime_ms": 10.0,
             "pricing_compute_time_ms": 10.0, "compute_avoided_proxy": 0.0, "time_saved_proxy": 0.0},
        ]
        econ = compute_economics_from_rows(rows, label="no_hits")
        self.assertEqual(econ.exact_hits, 0)
        self.assertFalse(econ.net_benefit_flag)

    def test_similarity_decomposition(self) -> None:
        rows = [
            {"cache_hit": True, "similarity_hit": False, "similarity_group_id": "g1"},
            {"cache_hit": False, "similarity_hit": True, "similarity_group_id": "g1"},
            {"cache_hit": False, "similarity_hit": False, "similarity_group_id": ""},
        ]
        decomp = compute_similarity_decomposition(rows)
        self.assertEqual(decomp["exact_hit_count"], 1)
        self.assertEqual(decomp["similarity_accepted_count"], 1)
        self.assertAlmostEqual(decomp["combined_hit_rate"], 2.0 / 3.0, places=4)

    def test_policy_frontier(self) -> None:
        sim_rows = [
            SimilarityAcceptanceRow(
                event_index=i, source_key_hash="a", target_key_hash="b",
                similarity_score=0.5 + i * 0.05, accepted=True,
                estimated_pricing_delta=0.01, reuse_savings_ms=2.0,
                approximation_error_abs=0.005, approximation_error_rel=0.01,
                policy_decision_reason="threshold",
            )
            for i in range(10)
        ]
        frontier = compute_policy_frontier(sim_rows)
        self.assertGreater(len(frontier), 0)
        self.assertTrue(all(f.threshold >= 0.5 for f in frontier))


class TestWorkloadRegistry(unittest.TestCase):
    def test_all_original_families_registered(self) -> None:
        original = [
            "exact_repeat_pricing", "near_repeat_pricing", "path_ladder_pricing",
            "portfolio_cluster_condensation", "overlapping_event_window_rebuild",
            "stress_churn_pricing",
        ]
        for fam in original:
            self.assertIn(fam, WORKLOAD_FAMILY_REGISTRY)
            meta = get_family_meta(fam)
            self.assertIn(meta.realism_tier, [
                "finance_inspired", "finance_analogous", "synthetic_control", "stress_control",
            ])

    def test_new_families_registered(self) -> None:
        new_families = [
            "intraday_scenario_ladder", "cross_sectional_basket_repricing",
            "rolling_horizon_refresh", "hotset_coldset_mixed", "parameter_shock_grid",
        ]
        for fam in new_families:
            self.assertIn(fam, WORKLOAD_FAMILY_REGISTRY)

    def test_synthetic_controls_flagged(self) -> None:
        synthetics = get_synthetic_control_families()
        self.assertIn("stress_churn_pricing", synthetics)
        for fid in synthetics:
            self.assertTrue(WORKLOAD_FAMILY_REGISTRY[fid].synthetic_control_flag)

    def test_finance_representative_excludes_synthetics(self) -> None:
        finance = get_finance_representative_families()
        for fid in finance:
            self.assertFalse(WORKLOAD_FAMILY_REGISTRY[fid].synthetic_control_flag)

    def test_regime_summary_from_rows(self) -> None:
        rows = [
            {"workload_family": "exact_repeat_pricing", "cache_hit": True, "similarity_hit": False},
            {"workload_family": "exact_repeat_pricing", "cache_hit": False, "similarity_hit": False},
            {"workload_family": "stress_churn_pricing", "cache_hit": False, "similarity_hit": False},
        ]
        summary = build_workload_regime_summary(rows)
        families = {s["workload_family"] for s in summary}
        self.assertIn("exact_repeat_pricing", families)
        self.assertIn("stress_churn_pricing", families)

    def test_metadata_has_required_fields(self) -> None:
        all_meta = get_all_family_metadata()
        required_keys = {
            "workload_family", "realism_tier", "finance_context",
            "expected_reuse_mode", "expected_locality_mode",
            "approximation_risk", "synthetic_control_flag", "comments",
        }
        for meta in all_meta:
            self.assertTrue(required_keys.issubset(set(meta.keys())), msg=f"Missing keys in {meta['workload_family']}")


class TestHpcProvenance(unittest.TestCase):
    def test_execution_context_detection(self) -> None:
        ctx = detect_execution_context()
        self.assertIn("execution_host", ctx)
        self.assertIn("physical_execution_context", ctx)
        self.assertIn(ctx["physical_execution_context"], [
            "local_workstation", "bigred200_login_node",
            "slurm_batch", "slurm_array_task",
        ])

    def test_provenance_fields_flat(self) -> None:
        fields = build_hpc_provenance_fields()
        self.assertIn("execution_host", fields)
        self.assertIn("backend_intent", fields)
        self.assertIn("physical_execution_context", fields)

    def test_engine_detection(self) -> None:
        engines = detect_available_engines()
        self.assertIn("classical_mc", engines)
        self.assertTrue(engines["classical_mc"]["available"])
        for name, info in engines.items():
            self.assertIn("available", info)
            self.assertIn("reason", info)

    def test_hpc_summary_generation(self) -> None:
        summary = build_hpc_execution_summary()
        self.assertIn("execution_context", summary)
        self.assertIn("python_environment", summary)
        self.assertIn("available_engines", summary)
        self.assertIn("cluster_specific_notes", summary)


class TestBudgetUtilization(unittest.TestCase):
    def test_workload_limited(self) -> None:
        b = BudgetUtilization(requested_budget_minutes=60.0)
        b.finalize(30.0, total_pricings=500, max_pricings=10000)
        self.assertTrue(b.workload_limited_flag)
        self.assertEqual(b.termination_reason, "workload_exhausted_before_budget")
        self.assertAlmostEqual(b.budget_utilization_fraction, 0.5 / 60.0, places=2)

    def test_budget_limited(self) -> None:
        b = BudgetUtilization(requested_budget_minutes=1.0)
        b.finalize(58.0, total_pricings=500, max_pricings=10000)
        self.assertTrue(b.budget_limited_flag)
        self.assertEqual(b.termination_reason, "budget_exhausted")

    def test_pricing_cap_reached(self) -> None:
        b = BudgetUtilization(requested_budget_minutes=60.0)
        b.finalize(30.0, total_pricings=10000, max_pricings=10000)
        self.assertTrue(b.pricing_cap_reached)
        self.assertEqual(b.termination_reason, "pricing_cap_reached")


class TestRunProfiles(unittest.TestCase):
    def test_all_profiles_valid(self) -> None:
        profiles = list_profiles()
        self.assertGreater(len(profiles), 5)
        for p in profiles:
            self.assertIn("name", p)
            self.assertIn("description", p)
            profile = get_profile(p["name"])
            self.assertIn("scale_label", profile)
            self.assertIn("slurm", profile)

    def test_slurm_script_generation(self) -> None:
        script = generate_slurm_script("smoke_cluster_validation")
        self.assertIn("#!/bin/bash", script)
        self.assertIn("#SBATCH", script)
        self.assertIn("run_repeated_workload_study.py", script)

    def test_array_job_script(self) -> None:
        script = generate_slurm_script("repeated_array_seed_sweep")
        self.assertIn("--array", script)
        self.assertIn("SLURM_ARRAY_TASK_ID", script)


class TestEvidenceBundleIntegration(unittest.TestCase):
    def test_evidence_bundle_generation(self) -> None:
        from qhpc_cache.cache_evidence_bundle import generate_evidence_bundle

        rows = [
            {
                "request_key_hash": f"key_{i % 5}",
                "cache_hit": i >= 5 and (i % 5) < 3,
                "similarity_hit": False,
                "similarity_group_id": f"g_{i % 3}",
                "workload_family": "exact_repeat_pricing" if i < 5 else "near_repeat_pricing",
                "pricing_compute_time_ms": 2.0 if not (i >= 5 and (i % 5) < 3) else 0.0,
                "total_runtime_ms": 0.1 if (i >= 5 and (i % 5) < 3) else 2.0,
                "compute_avoided_proxy": 2.0 if (i >= 5 and (i % 5) < 3) else 0.0,
                "time_saved_proxy": 1.9 if (i >= 5 and (i % 5) < 3) else 0.0,
            }
            for i in range(10)
        ]
        with tempfile.TemporaryDirectory() as td:
            artifacts = generate_evidence_bundle(
                rows,
                Path(td) / "evidence",
                run_label="test_run",
                emit_plots=False,
            )
            self.assertIn("cache_evidence_summary_json", artifacts)
            self.assertIn("cache_reuse_distance_csv", artifacts)
            self.assertIn("cache_locality_summary_csv", artifacts)
            self.assertIn("working_set_timeline_csv", artifacts)
            self.assertIn("cache_policy_value_summary_csv", artifacts)
            self.assertIn("similarity_acceptance_summary_csv", artifacts)
            self.assertIn("workload_regime_summary_csv", artifacts)

            summary = json.loads(Path(artifacts["cache_evidence_summary_json"]).read_text())
            self.assertIn("aggregate_locality", summary)
            self.assertIn("aggregate_economics", summary)
            self.assertIn("hpc_provenance", summary)

    def test_zero_hit_run_produces_valid_evidence(self) -> None:
        from qhpc_cache.cache_evidence_bundle import generate_evidence_bundle

        rows = [
            {
                "request_key_hash": f"unique_key_{i}",
                "cache_hit": False,
                "similarity_hit": False,
                "similarity_group_id": "",
                "workload_family": "stress_churn_pricing",
                "pricing_compute_time_ms": 5.0,
                "total_runtime_ms": 5.0,
                "compute_avoided_proxy": 0.0,
                "time_saved_proxy": 0.0,
            }
            for i in range(20)
        ]
        with tempfile.TemporaryDirectory() as td:
            artifacts = generate_evidence_bundle(
                rows, Path(td) / "evidence", emit_plots=False,
            )
            summary = json.loads(Path(artifacts["cache_evidence_summary_json"]).read_text())
            econ = summary["aggregate_economics"]
            self.assertEqual(econ["exact_hits"], 0)
            self.assertFalse(econ["net_benefit_flag"])
            loc = summary["aggregate_locality"]
            self.assertEqual(loc["one_hit_wonder_fraction"], 1.0)


class TestRunAggregation(unittest.TestCase):
    def test_aggregate_empty_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            result = aggregate_runs(
                [Path(td) / "nonexistent_a", Path(td) / "nonexistent_b"],
                Path(td) / "aggregated",
            )
            self.assertEqual(result["run_count"], 2)
            self.assertTrue(Path(result["comparison_json"]).exists())


class TestOptionalEngineSkipHonesty(unittest.TestCase):
    def test_optional_engines_have_reason_codes(self) -> None:
        engines = detect_available_engines()
        for name in ["quantlib_mc", "cirq_qmci", "monaco_mc"]:
            self.assertIn(name, engines)
            if not engines[name]["available"]:
                self.assertIn(engines[name]["reason"], [
                    "dependency_missing", "import_failed", "platform_incompatible",
                ] + [r for r in [engines[name]["reason"]] if r.startswith("import_failed:")])


if __name__ == "__main__":
    unittest.main()
