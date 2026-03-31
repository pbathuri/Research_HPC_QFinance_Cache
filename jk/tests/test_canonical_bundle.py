"""Tests for the canonical research bundle, similarity validation,
honesty manifest, expanded metrics, aggregation, and SLM completeness."""

from __future__ import annotations

import csv
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestSimilarityValidation(unittest.TestCase):

    def test_validator_probabilistic(self):
        from qhpc_cache.similarity_validation import SimilarityValidator, ValidationConfig
        cfg = ValidationConfig(mode="probabilistic", validation_rate=0.5, seed=42)
        v = SimilarityValidator(cfg)
        decisions = [v.should_validate("fam") for _ in range(100)]
        true_count = sum(decisions)
        self.assertGreater(true_count, 20)
        self.assertLess(true_count, 80)

    def test_validator_deterministic(self):
        from qhpc_cache.similarity_validation import SimilarityValidator, ValidationConfig
        cfg = ValidationConfig(mode="deterministic")
        v = SimilarityValidator(cfg)
        self.assertTrue(all(v.should_validate("fam") for _ in range(10)))

    def test_validator_off(self):
        from qhpc_cache.similarity_validation import SimilarityValidator, ValidationConfig
        cfg = ValidationConfig(mode="off")
        v = SimilarityValidator(cfg)
        self.assertFalse(any(v.should_validate("fam") for _ in range(10)))

    def test_validate_reuse_produces_result(self):
        from qhpc_cache.similarity_validation import SimilarityValidator, ValidationConfig

        class FakeEngine:
            def price(self, **kw):
                class R:
                    price = 10.5
                    std_error = 0.05
                    wall_clock_ms = 1.0
                return R()

        cfg = ValidationConfig(mode="deterministic")
        v = SimilarityValidator(cfg)
        req = {
            "request_id": "r1", "workload_family": "exact_repeat_pricing",
            "S0": 100, "K": 100, "r": 0.05, "sigma": 0.2, "T": 1.0,
            "num_paths": 10000, "random_seed": 42,
            "feature_hash": "fh1", "parameter_hash": "ph1",
            "similarity_group_id": "sg1",
        }
        result = v.validate_reuse(
            request=req, engine=FakeEngine(),
            reused_result={"price": 10.4, "std_error": 0.06},
            reuse_type="exact", engine_name="fake",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.request_id, "r1")
        self.assertGreaterEqual(result.absolute_error, 0)

    def test_summary_with_results(self):
        from qhpc_cache.similarity_validation import SimilarityValidator, ValidationConfig

        class FakeEngine:
            def price(self, **kw):
                class R:
                    price = 10.5
                    std_error = 0.05
                    wall_clock_ms = 1.0
                return R()

        cfg = ValidationConfig(mode="deterministic")
        v = SimilarityValidator(cfg)
        for i in range(5):
            req = {
                "request_id": f"r{i}", "workload_family": "near_repeat",
                "S0": 100, "K": 100, "r": 0.05, "sigma": 0.2, "T": 1.0,
                "num_paths": 10000, "random_seed": 42 + i,
                "feature_hash": "fh", "parameter_hash": "ph",
                "similarity_group_id": "sg",
            }
            v.validate_reuse(
                request=req, engine=FakeEngine(),
                reused_result={"price": 10.5 + i * 0.01, "std_error": 0.05},
                reuse_type="similarity", engine_name="fake",
            )
        summary = v.summarize()
        self.assertEqual(summary["validation_count"], 5)
        self.assertIn("tolerance_pass_rate", summary)
        self.assertIn("by_family", summary)

    def test_write_artifacts(self):
        from qhpc_cache.similarity_validation import (
            SimilarityValidator, ValidationConfig, write_validation_artifacts,
        )

        class FakeEngine:
            def price(self, **kw):
                class R:
                    price = 10.5
                    std_error = 0.05
                    wall_clock_ms = 1.0
                return R()

        v = SimilarityValidator(ValidationConfig(mode="deterministic"))
        v.validate_reuse(
            request={"request_id": "r1", "workload_family": "test",
                     "S0": 100, "K": 100, "r": 0.05, "sigma": 0.2, "T": 1.0,
                     "num_paths": 10000, "random_seed": 42,
                     "feature_hash": "fh", "parameter_hash": "ph",
                     "similarity_group_id": "sg"},
            engine=FakeEngine(),
            reused_result={"price": 10.5, "std_error": 0.05},
            reuse_type="exact", engine_name="fake",
        )
        with tempfile.TemporaryDirectory() as td:
            paths = write_validation_artifacts(v, Path(td))
            self.assertTrue(Path(paths["summary"]).exists())
            self.assertTrue(Path(paths["examples_csv"]).exists())


class TestResearchHonesty(unittest.TestCase):

    def test_build_manifest(self):
        from qhpc_cache.research_honesty import build_honesty_manifest
        m = build_honesty_manifest(
            engines_available=["classical_mc"],
            engines_skipped={"quantlib_mc": "import_failed", "cirq_qmci": "not_installed"},
            similarity_validated=True,
            validation_coverage=0.25,
        )
        self.assertIn("flags", m)
        self.assertIn("engines_available", m)
        flags = m["flags"]
        flag_ids = {f["flag_id"] for f in flags}
        self.assertIn("engine_available_classical_mc", flag_ids)
        self.assertIn("engine_skipped_quantlib_mc", flag_ids)
        self.assertIn("similarity_control_validated", flag_ids)

    def test_write_manifest(self):
        from qhpc_cache.research_honesty import build_honesty_manifest, write_honesty_manifest
        m = build_honesty_manifest(
            engines_available=["classical_mc"],
            engines_skipped={},
        )
        with tempfile.TemporaryDirectory() as td:
            paths = write_honesty_manifest(m, Path(td))
            self.assertTrue(Path(paths["json"]).exists())
            self.assertTrue(Path(paths["md"]).exists())
            data = json.loads(Path(paths["json"]).read_text())
            self.assertIn("summary", data)

    def test_honesty_flags_schema(self):
        from qhpc_cache.research_honesty import build_honesty_manifest
        m = build_honesty_manifest(
            engines_available=["classical_mc"],
            engines_skipped={"cirq_qmci": "unavailable"},
            cpu_only=True, single_node=True, pmu_proxy=True,
        )
        for flag in m["flags"]:
            self.assertIn("flag_id", flag)
            self.assertIn("status", flag)
            self.assertIn(flag["status"], {"true", "false", "partial", "skipped", "unavailable"})
            self.assertIn("category", flag)


class TestExpandedMetrics(unittest.TestCase):

    def _make_rows(self):
        return [
            {"cache_hit": True, "similarity_hit": False, "reuse_distance_events": 2.0,
             "ground_truth_cacheability_label": "exact_reusable", "workload_family": "exact_repeat",
             "similarity_group_id": "", "request_key_hash": "k1", "request_id": "r1"},
            {"cache_hit": False, "similarity_hit": True, "reuse_distance_events": 5.0,
             "ground_truth_cacheability_label": "similarity_reusable_safe", "workload_family": "near_repeat",
             "similarity_group_id": "sg1", "request_key_hash": "k2", "request_id": "r2"},
            {"cache_hit": False, "similarity_hit": False, "reuse_distance_events": float("nan"),
             "ground_truth_cacheability_label": "unique_first_access", "workload_family": "stress",
             "similarity_group_id": "", "request_key_hash": "k3", "request_id": "r3"},
        ]

    def test_expanded_metrics_basic(self):
        from qhpc_cache.expanded_metrics import compute_expanded_metrics
        m = compute_expanded_metrics(self._make_rows())
        self.assertEqual(m["total_requests"], 3)
        self.assertIn("useful_hit_rate", m)
        self.assertIn("harmful_hit_rate", m)
        self.assertIn("accepted_similarity_rate", m)
        self.assertIn("temporal_locality_score", m)
        self.assertIn("working_set_growth_rate", m)
        self.assertIn("by_family", m)

    def test_expanded_metrics_with_validation(self):
        from qhpc_cache.expanded_metrics import compute_expanded_metrics
        val = [{"request_id": "r1", "relative_error": 0.01, "tolerance_pass": True, "workload_family": "exact_repeat"}]
        m = compute_expanded_metrics(self._make_rows(), validation_results=val)
        self.assertEqual(m["validation_count"], 1)
        self.assertGreater(m["tolerance_pass_rate"], 0.0)

    def test_empty_rows(self):
        from qhpc_cache.expanded_metrics import compute_expanded_metrics
        m = compute_expanded_metrics([])
        self.assertEqual(m["total_requests"], 0)


class TestRunAggregation(unittest.TestCase):

    def _make_mini_run(self, base_dir: Path, seed: int) -> Path:
        rd = base_dir / f"run_seed{seed}"
        rd.mkdir(parents=True)
        manifest = {
            "scale_label": "smoke",
            "deterministic_seed": seed,
            "lane_selection": "lane_a",
            "summary_rows_count": 3,
        }
        (rd / "repeated_workload_manifest.json").write_text(json.dumps(manifest))

        research = rd / "research"
        research.mkdir()
        (research / "cacheability_summary.json").write_text(json.dumps({"cache_recall_on_reusable": 0.3}))
        (research / "utility_summary.json").write_text(json.dumps({"total_utility": 10, "mean_utility": 1.0}))
        (research / "hpc_utilization.json").write_text(json.dumps({"compute_fraction": 0.6}))
        (research / "expanded_metrics.json").write_text(json.dumps({
            "exact_hit_rate": 0.25, "similarity_hit_rate": 0.10,
            "useful_hit_rate": 0.20, "harmful_hit_rate": 0.01,
            "by_family": {
                "exact_repeat": {"exact_hit_rate": 0.5, "similarity_hit_rate": 0.0,
                                 "useful_hit_rate": 0.4, "harmful_hit_rate": 0.0,
                                 "mean_reuse_distance": 3.0},
            },
        }))
        (research / "similarity_validation_summary.json").write_text(json.dumps({"tolerance_pass_rate": 0.9}))
        (research / "research_claims_manifest.json").write_text(json.dumps({
            "claims": [{"claim_id": "C1", "support_status": "supported"}]
        }))
        (research / "research_honesty_manifest.json").write_text(json.dumps({"summary": {"total_flags": 5}}))

        slm = rd / "slm_datasets"
        slm.mkdir()
        (slm / "slm_export_manifest.json").write_text(json.dumps({"files": {"training": str(slm / "t.jsonl")}}))

        return rd

    def test_aggregate_two_runs(self):
        from qhpc_cache.run_aggregation import aggregate_research_runs
        with tempfile.TemporaryDirectory() as td:
            r1 = self._make_mini_run(Path(td), 42)
            r2 = self._make_mini_run(Path(td), 43)
            out = Path(td) / "aggregate"
            result = aggregate_research_runs([r1, r2], out)
            self.assertEqual(result["run_count"], 2)
            self.assertIn("per_family", result)
            self.assertIn("seed_stability", result)
            self.assertTrue((out / "aggregate_research_summary.json").exists())
            self.assertTrue((out / "aggregate_research_summary.md").exists())
            self.assertTrue((out / "per_family_metrics.csv").exists())
            self.assertTrue((out / "claim_support_matrix.csv").exists())


class TestRegimeLabelPropagation(unittest.TestCase):

    def test_generator_adds_regime(self):
        from qhpc_cache.repeated_workload_generator import generate_repeated_workload_requests
        bank = generate_repeated_workload_requests(
            scale_label="smoke", seed=42, lane_selection="lane_a",
        )
        for lane_id, families in bank.items():
            for fam, requests in families.items():
                for req in requests:
                    self.assertIn("workload_regime", req, f"Missing regime on {fam}")
                    self.assertNotEqual(req["workload_regime"], "", f"Empty regime on {fam}")


class TestCanonicalBundleEmission(unittest.TestCase):

    def test_smoke_run_produces_canonical_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            from qhpc_cache.repeated_workload_study import run_repeated_workload_study
            result = run_repeated_workload_study(
                output_dir=td, lane_selection="lane_a",
                scale_label="smoke", seed=42, emit_plots=False,
                budget_minutes=1.0,
            )
            manifest = result["manifest"]
            rd = Path(td) / "research"

            self.assertTrue((rd / "cacheability_summary.json").exists())
            self.assertTrue((rd / "utility_summary.json").exists())
            self.assertTrue((rd / "portfolio_overlap.json").exists())
            self.assertTrue((rd / "hpc_utilization.json").exists())
            self.assertTrue((rd / "research_claims_manifest.json").exists())
            self.assertTrue((rd / "research_honesty_manifest.json").exists())
            self.assertTrue((rd / "expanded_metrics.json").exists())
            self.assertTrue((rd / "similarity_validation_summary.json").exists())

            slm = Path(td) / "slm_datasets"
            self.assertTrue((slm / "reuse_decision_dataset.csv").exists())
            self.assertTrue((slm / "cacheability_labels.csv").exists())
            self.assertTrue((slm / "workload_family_dataset.csv").exists())
            self.assertTrue((slm / "slm_training_examples.jsonl").exists())

    def test_slm_records_have_raw_fields(self):
        with tempfile.TemporaryDirectory() as td:
            from qhpc_cache.repeated_workload_study import run_repeated_workload_study
            run_repeated_workload_study(
                output_dir=td, lane_selection="lane_a",
                scale_label="smoke", seed=42, emit_plots=False,
            )
            jsonl_path = Path(td) / "slm_datasets" / "slm_training_examples.jsonl"
            with open(jsonl_path) as f:
                first = json.loads(f.readline())
                self.assertGreater(first["S0"], 0, "S0 should be populated")
                self.assertGreater(first["K"], 0, "K should be populated")
                self.assertGreater(first["sigma"], 0, "sigma should be populated")
                self.assertIn("workload_regime", first)

    def test_expanded_metrics_in_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            from qhpc_cache.repeated_workload_study import run_repeated_workload_study
            result = run_repeated_workload_study(
                output_dir=td, lane_selection="lane_a",
                scale_label="smoke", seed=42, emit_plots=False,
            )
            expanded = result["manifest"].get("expanded_metrics", {})
            self.assertIn("useful_hit_rate", expanded)
            self.assertIn("harmful_hit_rate", expanded)
            self.assertIn("accepted_similarity_rate", expanded)
            self.assertIn("validation_count", expanded)

    def test_honesty_manifest_in_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            from qhpc_cache.repeated_workload_study import run_repeated_workload_study
            result = run_repeated_workload_study(
                output_dir=td, lane_selection="lane_a",
                scale_label="smoke", seed=42, emit_plots=False,
            )
            honesty = result["manifest"].get("research_honesty", {})
            self.assertIn("json", honesty)
            data = json.loads(Path(honesty["json"]).read_text())
            flag_ids = {f["flag_id"] for f in data.get("flags", [])}
            self.assertIn("cpu_only_execution", flag_ids)
            self.assertIn("similarity_control_validated", flag_ids)


if __name__ == "__main__":
    unittest.main()
