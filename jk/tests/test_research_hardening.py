"""Tests for research-hardening modules: cacheability labels, utility, tolerance
sweeps, regime generation, portfolio overlap, HPC utilization, research claims,
and SLM exports."""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestCacheabilityLabels(unittest.TestCase):

    def _make_rows(self):
        return [
            {
                "request_id": "r1",
                "workload_family": "exact_repeat_pricing",
                "parameter_hash": "h1",
                "feature_hash": "f1",
                "exact_repeat_group_id": "g1",
                "similarity_group_id": "",
                "cache_hit": False,
                "similarity_hit": False,
            },
            {
                "request_id": "r2",
                "workload_family": "exact_repeat_pricing",
                "parameter_hash": "h1",
                "feature_hash": "f1",
                "exact_repeat_group_id": "g1",
                "similarity_group_id": "",
                "cache_hit": True,
                "similarity_hit": False,
            },
            {
                "request_id": "r3",
                "workload_family": "near_repeat_pricing",
                "parameter_hash": "h2",
                "feature_hash": "f2",
                "exact_repeat_group_id": "",
                "similarity_group_id": "sg1",
                "cache_hit": False,
                "similarity_hit": False,
            },
            {
                "request_id": "r4",
                "workload_family": "near_repeat_pricing",
                "parameter_hash": "h3",
                "feature_hash": "f2",
                "exact_repeat_group_id": "",
                "similarity_group_id": "sg1",
                "cache_hit": False,
                "similarity_hit": True,
            },
            {
                "request_id": "r5",
                "workload_family": "stress_churn_pricing",
                "parameter_hash": "h_unique",
                "feature_hash": "f_unique",
                "exact_repeat_group_id": "",
                "similarity_group_id": "",
                "cache_hit": False,
                "similarity_hit": False,
            },
        ]

    def test_label_assignment_basic(self):
        from qhpc_cache.cacheability_labels import assign_cacheability_labels, CacheabilityLabel
        assignments = assign_cacheability_labels(self._make_rows())
        self.assertEqual(len(assignments), 5)
        self.assertEqual(assignments[0].ground_truth_label, CacheabilityLabel.UNIQUE_FIRST_ACCESS)
        self.assertEqual(assignments[1].ground_truth_label, CacheabilityLabel.EXACT_REUSABLE)

    def test_label_summary(self):
        from qhpc_cache.cacheability_labels import (
            assign_cacheability_labels,
            summarize_cacheability_labels,
        )
        assignments = assign_cacheability_labels(self._make_rows())
        summary = summarize_cacheability_labels(assignments)
        self.assertEqual(summary["total"], 5)
        self.assertIn("label_distribution", summary)
        self.assertIn("unique_first_access_fraction", summary)

    def test_empty_rows(self):
        from qhpc_cache.cacheability_labels import assign_cacheability_labels
        assignments = assign_cacheability_labels([])
        self.assertEqual(len(assignments), 0)

    def test_all_labels_are_valid_enums(self):
        from qhpc_cache.cacheability_labels import (
            assign_cacheability_labels,
            CacheabilityLabel,
        )
        assignments = assign_cacheability_labels(self._make_rows())
        for a in assignments:
            self.assertIsInstance(a.ground_truth_label, CacheabilityLabel)

    def test_failure_taxonomy_coverage(self):
        from qhpc_cache.cacheability_labels import FailureReason
        expected = {
            "engine_unavailable", "dependency_unavailable",
            "feature_representation_insufficient", "policy_too_strict",
            "policy_too_loose", "unique_workload", "unsafe_similarity",
            "data_source_missing", "proxy_measurement_only",
            "cluster_env_mismatch", "output_not_generated",
            "parallelism_not_exercised", "none",
        }
        actual = {f.value for f in FailureReason}
        self.assertEqual(actual, expected)

    def test_epistemic_status_coverage(self):
        from qhpc_cache.cacheability_labels import EpistemicStatus
        expected = {
            "observed", "derived", "proxy", "simulated",
            "skipped", "unavailable", "unsupported",
        }
        actual = {s.value for s in EpistemicStatus}
        self.assertEqual(actual, expected)

    def test_policy_tier_coverage(self):
        from qhpc_cache.cacheability_labels import PolicyTier
        expected = {
            "no_cache", "exact_only", "exact_plus_simple_heuristic",
            "exact_plus_similarity", "exact_similarity_guardrails",
            "exact_similarity_regime_aware",
        }
        actual = {t.value for t in PolicyTier}
        self.assertEqual(actual, expected)


class TestReuseUtility(unittest.TestCase):

    def _make_rows(self):
        return [
            {
                "request_id": "r1",
                "cache_hit": True,
                "similarity_hit": False,
                "time_saved_proxy": 50.0,
                "pricing_compute_time_ms": 0.0,
                "ground_truth_cacheability_label": "exact_reusable",
            },
            {
                "request_id": "r2",
                "cache_hit": False,
                "similarity_hit": True,
                "time_saved_proxy": 0.0,
                "pricing_compute_time_ms": 20.0,
                "estimated_price_deviation": 0.001,
                "ground_truth_cacheability_label": "similarity_reusable_safe",
            },
            {
                "request_id": "r3",
                "cache_hit": False,
                "similarity_hit": False,
                "time_saved_proxy": 0.0,
                "pricing_compute_time_ms": 30.0,
                "ground_truth_cacheability_label": "exact_reusable",
            },
        ]

    def test_utility_computation(self):
        from qhpc_cache.reuse_utility import compute_reuse_utility
        rows = compute_reuse_utility(self._make_rows())
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].reuse_type, "exact_hit")
        self.assertEqual(rows[1].reuse_type, "similarity_hit")
        self.assertTrue(rows[2].is_false_miss)

    def test_utility_summary(self):
        from qhpc_cache.reuse_utility import compute_reuse_utility, summarize_utility
        rows = compute_reuse_utility(self._make_rows())
        summary = summarize_utility(rows, label="test")
        self.assertEqual(summary["count"], 3)
        self.assertEqual(summary["exact_hits"], 1)
        self.assertEqual(summary["false_miss_count"], 1)

    def test_exact_hit_positive_utility(self):
        from qhpc_cache.reuse_utility import compute_reuse_utility
        rows = compute_reuse_utility(self._make_rows())
        self.assertGreater(rows[0].utility_score, 0.0)

    def test_false_miss_negative_utility(self):
        from qhpc_cache.reuse_utility import compute_reuse_utility
        rows = compute_reuse_utility(self._make_rows())
        self.assertLess(rows[2].utility_score, 0.0)

    def test_policy_comparison(self):
        from qhpc_cache.reuse_utility import compare_policy_tiers
        comparisons = compare_policy_tiers(self._make_rows())
        self.assertEqual(len(comparisons), 6)
        for comp in comparisons:
            self.assertIn("label", comp)
            self.assertIn("total_utility", comp)


class TestToleranceSurfaces(unittest.TestCase):

    def _make_pairs(self):
        base = {"S0": 100.0, "K": 100.0, "sigma": 0.2, "T": 1.0, "num_paths": 10000}
        near = {
            "S0": 100.5, "K": 100.3, "sigma": 0.21, "T": 1.0, "num_paths": 10000,
            "realized_price_error": 0.002, "latency_saved_ms": 15.0,
        }
        far = {
            "S0": 120.0, "K": 115.0, "sigma": 0.45, "T": 2.0, "num_paths": 50000,
            "realized_price_error": 0.15, "latency_saved_ms": 20.0,
        }
        return [(base, near), (base, far)]

    def test_sweep_produces_points(self):
        from qhpc_cache.tolerance_surfaces import run_tolerance_sweep
        points = run_tolerance_sweep(self._make_pairs())
        self.assertGreater(len(points), 0)
        for p in points:
            self.assertIsInstance(p.safe_region_flag, bool)

    def test_pareto_front(self):
        from qhpc_cache.tolerance_surfaces import run_tolerance_sweep, build_pareto_front
        points = run_tolerance_sweep(self._make_pairs())
        front = build_pareto_front(points)
        self.assertGreater(len(front), 0)

    def test_sensitivity_table(self):
        from qhpc_cache.tolerance_surfaces import run_tolerance_sweep, generate_sensitivity_table
        points = run_tolerance_sweep(self._make_pairs())
        table = generate_sensitivity_table(points, vary_dimension="price_tolerance")
        self.assertGreater(len(table), 0)
        for row in table:
            self.assertIn("price_tolerance", row)
            self.assertIn("safe_fraction", row)

    def test_strict_tolerance_rejects_far(self):
        from qhpc_cache.tolerance_surfaces import run_tolerance_sweep
        points = run_tolerance_sweep(
            self._make_pairs(),
            price_tolerances=[0.001],
            sigma_tolerances=[0.001],
            maturity_tolerances=[0.001],
            path_tolerances=[0.0],
        )
        self.assertEqual(len(points), 1)
        self.assertLessEqual(points[0].accepted_count, 1)


class TestRegimeGenerator(unittest.TestCase):

    def test_all_regimes_registered(self):
        from qhpc_cache.regime_generator import MarketRegime, REGIME_CONFIGS
        for regime in MarketRegime:
            self.assertIn(regime, REGIME_CONFIGS)

    def test_apply_regime(self):
        from qhpc_cache.regime_generator import apply_regime_to_request, MarketRegime
        base = {"S0": 100.0, "K": 100.0, "sigma": 0.2, "T": 1.0, "num_paths": 10000, "random_seed": 42}
        result = apply_regime_to_request(base, MarketRegime.CALM_LOW_VOL, request_index=0)
        self.assertIn("regime_tag", result)
        self.assertEqual(result["regime_tag"], "calm_low_vol")
        self.assertGreater(result["sigma"], 0)

    def test_generate_workload(self):
        from qhpc_cache.regime_generator import generate_regime_tagged_workload, MarketRegime
        bases = [{"S0": 100.0, "K": 100.0, "sigma": 0.2, "T": 1.0, "num_paths": 10000, "random_seed": 42}]
        workload = generate_regime_tagged_workload(bases, MarketRegime.HIGH_VOL, count=20, seed=42)
        self.assertEqual(len(workload), 20)
        for req in workload:
            self.assertEqual(req["workload_regime"], "high_vol")

    def test_jump_regime_high_unique_fraction(self):
        from qhpc_cache.regime_generator import REGIME_CONFIGS, MarketRegime
        jump = REGIME_CONFIGS[MarketRegime.JUMP]
        calm = REGIME_CONFIGS[MarketRegime.CALM_LOW_VOL]
        self.assertGreater(jump.unique_fraction, calm.unique_fraction)

    def test_regime_metadata_complete(self):
        from qhpc_cache.regime_generator import get_regime_metadata
        meta = get_regime_metadata()
        self.assertEqual(len(meta), 7)
        for m in meta:
            self.assertIn("regime", m)
            self.assertIn("description", m)


class TestPortfolioOverlap(unittest.TestCase):

    def _make_rows(self):
        return [
            {"parameter_hash": "h1", "feature_hash": "f1", "cluster_id": "c1",
             "event_window_id": "w1", "S0": 100, "K": 100, "sigma": 0.2, "T": 1.0},
            {"parameter_hash": "h1", "feature_hash": "f1", "cluster_id": "c1",
             "event_window_id": "w1", "S0": 100, "K": 100, "sigma": 0.2, "T": 1.0},
            {"parameter_hash": "h2", "feature_hash": "f2", "cluster_id": "c2",
             "event_window_id": "w2", "S0": 120, "K": 115, "sigma": 0.3, "T": 2.0},
            {"parameter_hash": "h3", "feature_hash": "f3", "cluster_id": "c2",
             "event_window_id": "w2", "S0": 122, "K": 117, "sigma": 0.31, "T": 2.0},
        ]

    def test_portfolio_overlap(self):
        from qhpc_cache.portfolio_overlap import compute_portfolio_overlap
        metrics = compute_portfolio_overlap(self._make_rows())
        self.assertEqual(len(metrics), 1)
        m = metrics[0]
        self.assertEqual(m.position_count, 4)
        self.assertGreater(m.param_overlap_ratio, 0.0)

    def test_scenario_overlap(self):
        from qhpc_cache.portfolio_overlap import compute_scenario_overlap
        metrics = compute_scenario_overlap(self._make_rows())
        self.assertEqual(len(metrics), 2)

    def test_empty_rows(self):
        from qhpc_cache.portfolio_overlap import compute_portfolio_overlap
        metrics = compute_portfolio_overlap([])
        self.assertEqual(len(metrics), 0)


class TestHpcUtilization(unittest.TestCase):

    def _make_rows(self):
        return [
            {"pricing_compute_time_ms": 10.0, "total_runtime_ms": 12.0, "row_semantics": "lookup_single_attempt"},
            {"pricing_compute_time_ms": 0.0, "total_runtime_ms": 2.0, "row_semantics": "lookup_single_attempt"},
            {"pricing_compute_time_ms": 50.0, "total_runtime_ms": 55.0, "row_semantics": "put_single_compute_result"},
        ]

    def test_utilization_breakdown(self):
        from qhpc_cache.hpc_utilization_analysis import compute_utilization_breakdown
        bd = compute_utilization_breakdown(self._make_rows(), total_wall_clock_ms=500.0)
        self.assertEqual(bd.total_wall_clock_ms, 500.0)
        self.assertAlmostEqual(bd.total_compute_ms, 60.0)
        self.assertGreater(bd.overhead_fraction, 0.0)

    def test_amdahl_speedup(self):
        from qhpc_cache.hpc_utilization_analysis import amdahl_speedup
        self.assertEqual(amdahl_speedup(1.0, 10), 1.0)
        speedup_4 = amdahl_speedup(0.1, 4)
        self.assertGreater(speedup_4, 1.0)
        self.assertLess(speedup_4, 4.0)

    def test_scaling_projection(self):
        from qhpc_cache.hpc_utilization_analysis import (
            compute_utilization_breakdown,
            compute_scaling_projection,
        )
        bd = compute_utilization_breakdown(self._make_rows(), total_wall_clock_ms=500.0)
        projections = compute_scaling_projection(bd)
        self.assertGreater(len(projections), 0)
        for p in projections:
            self.assertIn("cores", p)
            self.assertIn("theoretical_speedup", p)


class TestResearchClaims(unittest.TestCase):

    def test_canonical_claims_exist(self):
        from qhpc_cache.research_claims import CANONICAL_CLAIMS
        self.assertGreaterEqual(len(CANONICAL_CLAIMS), 8)

    def test_evaluate_with_evidence(self):
        from qhpc_cache.research_claims import evaluate_claims, ClaimStatus
        evidence = {
            "total_pricings": 100,
            "exact_hit_rate": 0.15,
            "families_tested": ["exact_repeat_pricing", "near_repeat_pricing", "stress_churn_pricing"],
            "utility_summary": {"count": 100},
        }
        claims = evaluate_claims(evidence)
        c1 = next(c for c in claims if c.claim_id == "C1_exact_reuse_exists")
        self.assertEqual(c1.support_status, ClaimStatus.SUPPORTED)

    def test_evaluate_zero_hits(self):
        from qhpc_cache.research_claims import evaluate_claims, ClaimStatus
        evidence = {"total_pricings": 50, "exact_hit_rate": 0.0}
        claims = evaluate_claims(evidence)
        c1 = next(c for c in claims if c.claim_id == "C1_exact_reuse_exists")
        self.assertEqual(c1.support_status, ClaimStatus.NOT_SUPPORTED)

    def test_write_claims_manifest(self):
        from qhpc_cache.research_claims import CANONICAL_CLAIMS, write_claims_manifest
        with tempfile.TemporaryDirectory() as td:
            paths = write_claims_manifest(CANONICAL_CLAIMS, Path(td))
            self.assertTrue(Path(paths["json"]).exists())
            self.assertTrue(Path(paths["md"]).exists())
            data = json.loads(Path(paths["json"]).read_text())
            self.assertEqual(data["summary"]["total_claims"], len(CANONICAL_CLAIMS))


class TestSlmExports(unittest.TestCase):

    def _make_rows(self):
        return [
            {
                "request_id": "r1",
                "workload_family": "exact_repeat_pricing",
                "engine": "classical_mc",
                "cache_hit": True,
                "similarity_hit": False,
                "time_saved_proxy": 10.0,
                "pricing_compute_time_ms": 0.0,
                "parameter_hash": "h1",
                "feature_hash": "f1",
                "cluster_id": "c1",
                "reuse_distance_events": 3.0,
                "S0": 100.0,
                "K": 100.0,
                "sigma": 0.2,
                "T": 1.0,
                "r": 0.05,
                "num_paths": 10000,
            },
            {
                "request_id": "r2",
                "workload_family": "stress_churn_pricing",
                "engine": "classical_mc",
                "cache_hit": False,
                "similarity_hit": False,
                "time_saved_proxy": 0.0,
                "pricing_compute_time_ms": 25.0,
                "parameter_hash": "h2",
                "feature_hash": "f2",
                "cluster_id": "c2",
                "reuse_distance_events": float("nan"),
                "S0": 120.0,
                "K": 115.0,
                "sigma": 0.35,
                "T": 0.5,
                "r": 0.03,
                "num_paths": 50000,
            },
        ]

    def test_export_produces_files(self):
        from qhpc_cache.slm_exports import export_slm_dataset
        with tempfile.TemporaryDirectory() as td:
            paths = export_slm_dataset(self._make_rows(), Path(td), run_label="test")
            for key, path_str in paths.items():
                self.assertTrue(Path(path_str).exists(), f"{key} not found at {path_str}")

    def test_jsonl_schema(self):
        from qhpc_cache.slm_exports import export_slm_dataset, SLM_FEATURE_SCHEMA
        with tempfile.TemporaryDirectory() as td:
            paths = export_slm_dataset(self._make_rows(), Path(td), run_label="test")
            with open(paths["slm_training_jsonl"]) as f:
                for line in f:
                    record = json.loads(line)
                    for field in SLM_FEATURE_SCHEMA:
                        self.assertIn(field, record, f"Missing field: {field}")

    def test_build_record_fields(self):
        from qhpc_cache.slm_exports import build_slm_record
        row = self._make_rows()[0]
        record = build_slm_record(row, cacheability_label="exact_reusable")
        self.assertEqual(record["ground_truth_cacheability_label"], "exact_reusable")
        self.assertEqual(record["exact_match_flag"], True)
        self.assertEqual(record["workload_family"], "exact_repeat_pricing")

    def test_family_dataset(self):
        from qhpc_cache.slm_exports import export_slm_dataset
        with tempfile.TemporaryDirectory() as td:
            paths = export_slm_dataset(self._make_rows(), Path(td), run_label="test")
            import csv as csv_mod
            with open(paths["workload_family_csv"]) as f:
                reader = csv_mod.DictReader(f)
                rows = list(reader)
                self.assertEqual(len(rows), 2)


class TestIntegration(unittest.TestCase):
    """Verify the full study runner integrates new research modules."""

    def test_study_produces_research_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            from qhpc_cache.repeated_workload_study import run_repeated_workload_study
            result = run_repeated_workload_study(
                output_dir=td,
                lane_selection="lane_a",
                scale_label="smoke",
                seed=42,
                emit_plots=False,
                budget_minutes=1.0,
            )
            manifest = result["manifest"]

            self.assertIn("cacheability_summary", manifest)
            self.assertIn("utility_summary", manifest)
            self.assertIn("research_claims", manifest)
            self.assertIn("slm_exports", manifest)
            self.assertIn("hpc_utilization", manifest)

            research_dir = Path(td) / "research"
            self.assertTrue((research_dir / "cacheability_summary.json").exists())
            self.assertTrue((research_dir / "utility_summary.json").exists())
            self.assertTrue((research_dir / "research_claims_manifest.json").exists())

            slm_dir = Path(td) / "slm_datasets"
            self.assertTrue((slm_dir / "slm_training_examples.jsonl").exists())
            self.assertTrue((slm_dir / "reuse_decision_dataset.csv").exists())

    def test_cacheability_labels_are_plausible(self):
        with tempfile.TemporaryDirectory() as td:
            from qhpc_cache.repeated_workload_study import run_repeated_workload_study
            result = run_repeated_workload_study(
                output_dir=td,
                lane_selection="lane_a",
                scale_label="smoke",
                seed=42,
                emit_plots=False,
            )
            summary = result["manifest"].get("cacheability_summary", {})
            self.assertGreater(summary.get("total", 0), 0)
            dist = summary.get("label_distribution", {})
            self.assertGreater(len(dist), 0)


if __name__ == "__main__":
    unittest.main()
