"""Comprehensive tests for the final research pass:
- Layer A: new workload families
- Layer B: similarity validation
- Layer C: full-pipeline parity
- Layer D: BigRed wave scaling
- Layer E: SLM export completeness
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ── Layer A: Workload family completion ──────────────────────────────

class TestNewFamilyRegistry(unittest.TestCase):

    def test_all_eleven_families_registered(self):
        from qhpc_cache.repeated_workload_generator import REQUIRED_WORKLOAD_FAMILIES, FAMILY_IDS
        expected = {
            "exact_repeat_pricing", "near_repeat_pricing", "path_ladder_pricing",
            "portfolio_cluster_condensation", "overlapping_event_window_rebuild",
            "stress_churn_pricing",
            "intraday_scenario_ladder", "cross_sectional_basket",
            "rolling_horizon_refresh", "hotset_coldset_mixed", "parameter_shock_grid",
        }
        self.assertEqual(FAMILY_IDS, expected)
        self.assertEqual(len(REQUIRED_WORKLOAD_FAMILIES), 11)

    def test_scale_profiles_cover_all_families(self):
        from qhpc_cache.repeated_workload_generator import SCALE_PROFILES, REQUIRED_WORKLOAD_FAMILIES
        for scale in ("smoke", "standard", "heavy"):
            for fam in REQUIRED_WORKLOAD_FAMILIES:
                self.assertIn(fam, SCALE_PROFILES[scale], f"Missing {fam} in {scale}")
                self.assertGreater(SCALE_PROFILES[scale][fam], 0)

    def test_regime_map_covers_all_families(self):
        from qhpc_cache.repeated_workload_generator import FAMILY_REGIME_MAP, REQUIRED_WORKLOAD_FAMILIES
        for fam in REQUIRED_WORKLOAD_FAMILIES:
            self.assertIn(fam, FAMILY_REGIME_MAP, f"Missing regime for {fam}")


class TestIntradayScenarioLadder(unittest.TestCase):

    def test_generates_correct_count(self):
        from qhpc_cache.repeated_workload_generator import generate_repeated_workload_requests
        bank = generate_repeated_workload_requests(
            scale_label="smoke", seed=42, lane_selection="lane_a",
            workload_families=["intraday_scenario_ladder"],
        )
        rows = bank["lane_a"]["intraday_scenario_ladder"]
        self.assertEqual(len(rows), 20)

    def test_has_similarity_groups(self):
        from qhpc_cache.repeated_workload_generator import generate_repeated_workload_requests
        bank = generate_repeated_workload_requests(
            scale_label="smoke", seed=42, lane_selection="lane_a",
            workload_families=["intraday_scenario_ladder"],
        )
        rows = bank["lane_a"]["intraday_scenario_ladder"]
        groups = {r["similarity_group_id"] for r in rows if r["similarity_group_id"]}
        self.assertGreater(len(groups), 1)

    def test_has_regime_label(self):
        from qhpc_cache.repeated_workload_generator import generate_repeated_workload_requests
        bank = generate_repeated_workload_requests(
            scale_label="smoke", seed=42, lane_selection="lane_a",
            workload_families=["intraday_scenario_ladder"],
        )
        for r in bank["lane_a"]["intraday_scenario_ladder"]:
            self.assertEqual(r["workload_regime"], "volatile")


class TestCrossSectionalBasket(unittest.TestCase):

    def test_generates_with_portfolio_ids(self):
        from qhpc_cache.repeated_workload_generator import generate_repeated_workload_requests
        bank = generate_repeated_workload_requests(
            scale_label="smoke", seed=42, lane_selection="lane_a",
            workload_families=["cross_sectional_basket"],
        )
        rows = bank["lane_a"]["cross_sectional_basket"]
        self.assertEqual(len(rows), 24)
        pids = {r["portfolio_id"] for r in rows if r["portfolio_id"]}
        self.assertGreater(len(pids), 1)


class TestRollingHorizonRefresh(unittest.TestCase):

    def test_generates_with_event_windows(self):
        from qhpc_cache.repeated_workload_generator import generate_repeated_workload_requests
        bank = generate_repeated_workload_requests(
            scale_label="smoke", seed=42, lane_selection="lane_a",
            workload_families=["rolling_horizon_refresh"],
        )
        rows = bank["lane_a"]["rolling_horizon_refresh"]
        self.assertEqual(len(rows), 20)
        windows = {r["event_window_id"] for r in rows if r["event_window_id"]}
        self.assertGreater(len(windows), 1)


class TestHotsetColdsetMixed(unittest.TestCase):

    def test_produces_hot_and_cold_keys(self):
        from qhpc_cache.repeated_workload_generator import generate_repeated_workload_requests
        bank = generate_repeated_workload_requests(
            scale_label="smoke", seed=42, lane_selection="lane_a",
            workload_families=["hotset_coldset_mixed"],
        )
        rows = bank["lane_a"]["hotset_coldset_mixed"]
        self.assertEqual(len(rows), 24)
        clusters = {r["cluster_id"] for r in rows}
        hot = sum(1 for c in clusters if c.startswith("hotset"))
        cold = sum(1 for c in clusters if c.startswith("coldset"))
        self.assertGreater(hot, 0)
        self.assertGreater(cold, 0)


class TestParameterShockGrid(unittest.TestCase):

    def test_generates_grid_structure(self):
        from qhpc_cache.repeated_workload_generator import generate_repeated_workload_requests
        bank = generate_repeated_workload_requests(
            scale_label="smoke", seed=42, lane_selection="lane_a",
            workload_families=["parameter_shock_grid"],
        )
        rows = bank["lane_a"]["parameter_shock_grid"]
        self.assertEqual(len(rows), 25)
        sigmas = {r["sigma"] for r in rows}
        self.assertGreater(len(sigmas), 3)


# ── Layer B: Similarity validation ───────────────────────────────────

class TestSimilarityValidationFields(unittest.TestCase):

    def test_validation_result_has_all_fields(self):
        from qhpc_cache.similarity_validation import SimilarityValidator, ValidationConfig

        class FakeEngine:
            def price(self, **kw):
                class R:
                    price = 10.5
                    std_error = 0.05
                    wall_clock_ms = 1.0
                return R()

        v = SimilarityValidator(ValidationConfig(mode="deterministic"))
        result = v.validate_reuse(
            request={"request_id": "r1", "workload_family": "test",
                     "S0": 100, "K": 100, "r": 0.05, "sigma": 0.2, "T": 1.0,
                     "num_paths": 10000, "random_seed": 42,
                     "feature_hash": "fh", "parameter_hash": "ph",
                     "similarity_group_id": "sg"},
            engine=FakeEngine(),
            reused_result={"price": 10.5, "std_error": 0.05},
            reuse_type="exact", engine_name="fake",
        )
        d = result.to_dict()
        required_fields = [
            "request_id", "workload_family", "engine", "reuse_type",
            "reused_price", "recomputed_price", "absolute_error", "relative_error",
            "tolerance_threshold", "tolerance_pass", "trigger_reason",
            "eligible_for_summary",
        ]
        for f in required_fields:
            self.assertIn(f, d, f"Missing field: {f}")

    def test_no_fake_validation_when_no_candidates(self):
        from qhpc_cache.similarity_validation import SimilarityValidator, ValidationConfig
        v = SimilarityValidator(ValidationConfig(mode="off"))
        self.assertFalse(v.should_validate("any_family"))
        self.assertEqual(len(v.results), 0)
        summary = v.summarize()
        self.assertEqual(summary["validation_count"], 0)
        self.assertEqual(summary["status"], "no_validations_performed")


# ── Layer C: Full-pipeline parity ────────────────────────────────────

class TestFullPipelineParityArtifacts(unittest.TestCase):

    def test_full_pipeline_research_bundle_import(self):
        from qhpc_cache.research_honesty import build_honesty_manifest, write_honesty_manifest
        from qhpc_cache.research_claims import evaluate_claims, write_claims_manifest
        m = build_honesty_manifest(
            engines_available=["classical_mc"],
            engines_skipped={"cirq_qmci": "unavailable"},
            run_label="full_pipeline_test",
        )
        with tempfile.TemporaryDirectory() as td:
            paths = write_honesty_manifest(m, Path(td))
            self.assertTrue(Path(paths["json"]).exists())

            evidence = {"total_pricings": 100, "exact_hit_rate": 0.1, "families_tested": []}
            claims = evaluate_claims(evidence)
            cpaths = write_claims_manifest(claims, Path(td))
            self.assertTrue(Path(td, "research_claims_manifest.json").exists())


# ── Layer D: BigRed wave scaling ─────────────────────────────────────

class TestBigRedScripts(unittest.TestCase):

    def test_scripts_exist(self):
        scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
        expected = [
            "bigred_repeated_standard.sh",
            "bigred_repeated_heavy.sh",
            "bigred_seed_array.sh",
            "bigred_full_pipeline.sh",
        ]
        for name in expected:
            self.assertTrue((scripts_dir / name).exists(), f"Missing {name}")

    def test_heavy_scale_has_larger_counts(self):
        from qhpc_cache.repeated_workload_generator import SCALE_PROFILES
        for fam in SCALE_PROFILES["heavy"]:
            self.assertGreater(
                SCALE_PROFILES["heavy"][fam],
                SCALE_PROFILES["standard"][fam],
                f"{fam} heavy should exceed standard",
            )


# ── Layer E: SLM export completeness ────────────────────────────────

class TestSLMSchemaCompleteness(unittest.TestCase):

    def test_schema_has_validation_fields(self):
        from qhpc_cache.slm_exports import SLM_FEATURE_SCHEMA
        required = [
            "validation_required", "recomputation_executed", "validation_pass",
            "validation_absolute_error", "validation_relative_error",
            "tolerance_profile", "lane_id", "similarity_candidate_available",
            "acceptance_decision", "risk_note",
        ]
        for f in required:
            self.assertIn(f, SLM_FEATURE_SCHEMA, f"Missing SLM field: {f}")

    def test_build_record_includes_validation(self):
        from qhpc_cache.slm_exports import build_slm_record
        row = {
            "request_id": "r1", "workload_family": "test", "engine": "classical_mc",
            "cache_hit": True, "similarity_hit": False, "S0": 100, "K": 100,
            "sigma": 0.2, "T": 1.0, "r": 0.05, "num_paths": 10000,
            "pricing_compute_time_ms": 5.0, "reuse_distance_events": 3.0,
            "parameter_hash": "ph", "feature_hash": "fh", "cluster_id": "c1",
            "similarity_group_id": "sg1", "lane_id": "lane_a",
        }
        val = {
            "validation_required": True,
            "recomputation_executed": True,
            "tolerance_pass": True,
            "absolute_error": 0.001,
            "relative_error": 0.0001,
        }
        rec = build_slm_record(row, validation_info=val)
        self.assertTrue(rec["validation_required"])
        self.assertTrue(rec["recomputation_executed"])
        self.assertTrue(rec["validation_pass"])
        self.assertAlmostEqual(rec["validation_absolute_error"], 0.001)


# ── Cross-run aggregation ────────────────────────────────────────────

class TestCrossRunAggregation(unittest.TestCase):

    def _make_run(self, base: Path, seed: int) -> Path:
        rd = base / f"run_{seed}"
        rd.mkdir(parents=True)
        (rd / "repeated_workload_manifest.json").write_text(json.dumps({
            "scale_label": "smoke", "deterministic_seed": seed,
            "lane_selection": "lane_a", "summary_rows_count": 5,
        }))
        r = rd / "research"
        r.mkdir()
        (r / "cacheability_summary.json").write_text(json.dumps({"cache_recall_on_reusable": 0.3}))
        (r / "utility_summary.json").write_text(json.dumps({"total_utility": 10, "mean_utility": 1.0}))
        (r / "hpc_utilization.json").write_text(json.dumps({"compute_fraction": 0.6}))
        (r / "expanded_metrics.json").write_text(json.dumps({
            "exact_hit_rate": 0.2 + seed * 0.01, "similarity_hit_rate": 0.1,
            "useful_hit_rate": 0.15, "harmful_hit_rate": 0.0,
            "by_family": {"test_fam": {"exact_hit_rate": 0.3, "similarity_hit_rate": 0.1,
                                       "useful_hit_rate": 0.2, "harmful_hit_rate": 0.0,
                                       "mean_reuse_distance": 4.0}},
        }))
        (r / "similarity_validation_summary.json").write_text(json.dumps({"tolerance_pass_rate": 0.9}))
        (r / "research_claims_manifest.json").write_text(json.dumps({"claims": [{"claim_id": "C1", "support_status": "supported"}]}))
        (r / "research_honesty_manifest.json").write_text(json.dumps({"summary": {"total_flags": 5}}))
        s = rd / "slm_datasets"
        s.mkdir()
        (s / "slm_export_manifest.json").write_text(json.dumps({"files": {"t": str(s / "t.jsonl")}}))
        return rd

    def test_aggregation_produces_outputs(self):
        from qhpc_cache.run_aggregation import aggregate_research_runs
        with tempfile.TemporaryDirectory() as td:
            r1 = self._make_run(Path(td), 42)
            r2 = self._make_run(Path(td), 43)
            r3 = self._make_run(Path(td), 44)
            out = Path(td) / "agg"
            result = aggregate_research_runs([r1, r2, r3], out)
            self.assertEqual(result["run_count"], 3)
            self.assertIn("seed_stability", result)
            stability = result["seed_stability"]
            self.assertIn("exact_hit_rate", stability)
            self.assertGreater(stability["exact_hit_rate"]["std"], 0)


# ── Integration: smoke run with all 11 families ─────────────────────

class TestFullSmokeAllFamilies(unittest.TestCase):

    def test_smoke_all_families_produce_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            from qhpc_cache.repeated_workload_study import run_repeated_workload_study
            result = run_repeated_workload_study(
                output_dir=td, lane_selection="lane_a",
                scale_label="smoke", seed=42, emit_plots=False,
                budget_minutes=2.0,
            )
            manifest = result["manifest"]
            self.assertNotIn("research_layer_error", manifest, manifest.get("research_layer_error", ""))
            rd = Path(td) / "research"
            self.assertTrue((rd / "expanded_metrics.json").exists())
            expanded = json.loads((rd / "expanded_metrics.json").read_text())
            families_in_output = set(expanded.get("by_family", {}).keys())
            self.assertIn("intraday_scenario_ladder", families_in_output)
            self.assertIn("hotset_coldset_mixed", families_in_output)
            self.assertIn("parameter_shock_grid", families_in_output)
            self.assertIn("cross_sectional_basket", families_in_output)
            self.assertIn("rolling_horizon_refresh", families_in_output)
            self.assertGreaterEqual(expanded["total_requests"], 200)

    def test_slm_exports_have_validation_fields(self):
        with tempfile.TemporaryDirectory() as td:
            from qhpc_cache.repeated_workload_study import run_repeated_workload_study
            run_repeated_workload_study(
                output_dir=td, lane_selection="lane_a",
                scale_label="smoke", seed=42, emit_plots=False,
            )
            jsonl = Path(td) / "slm_datasets" / "slm_training_examples.jsonl"
            with open(jsonl) as f:
                first = json.loads(f.readline())
            self.assertIn("validation_required", first)
            self.assertIn("recomputation_executed", first)
            self.assertIn("acceptance_decision", first)
            self.assertIn("lane_id", first)
            self.assertIn("risk_note", first)


if __name__ == "__main__":
    unittest.main()
