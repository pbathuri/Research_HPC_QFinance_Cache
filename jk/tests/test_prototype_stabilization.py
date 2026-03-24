"""Stabilization tests for exact-match cache prototype behavior."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache.cache_policy import AIAssistedCachePolicy, HeuristicCachePolicy
from qhpc_cache.cache_store import SimpleCacheStore
from qhpc_cache.experiment_runner import (
    run_canonical_exact_match_cache_experiment,
    run_repeated_pricing_experiment,
    run_similarity_cache_replay_experiment,
)
from qhpc_cache.pricing import MonteCarloPricer


class TestPrototypeStabilization(unittest.TestCase):
    def test_exact_match_cache_key_uses_contract_inputs(self):
        store = SimpleCacheStore()
        p1 = MonteCarloPricer(
            S0=100.0,
            K=100.0,
            r=0.05,
            sigma=0.2,
            T=1.0,
            num_paths=1000,
            random_seed=7,
            cache_store=store,
        )
        _ = p1.price_option()
        p2 = MonteCarloPricer(
            S0=100.0,
            K=110.0,  # changed strike must create a distinct key
            r=0.05,
            sigma=0.2,
            T=1.0,
            num_paths=1000,
            random_seed=7,
            cache_store=store,
        )
        _ = p2.price_option()
        stats = store.stats()
        self.assertEqual(stats["entries"], 2)
        self.assertEqual(stats["hits"], 0)
        self.assertEqual(stats["misses"], 2)

    def test_exact_match_reuse_validity(self):
        store = SimpleCacheStore()
        pricer = MonteCarloPricer(
            S0=100.0,
            K=100.0,
            r=0.05,
            sigma=0.2,
            T=1.0,
            num_paths=1200,
            random_seed=11,
            cache_store=store,  # no policy gate => exact-match lookup enabled
        )
        first = pricer.price_option()
        second = pricer.price_option()
        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)
        self.assertAlmostEqual(first.estimated_price, second.estimated_price, places=12)
        self.assertEqual(store.stats()["hits"], 1)

    def test_seeded_pricing_reproducibility(self):
        p1 = MonteCarloPricer(
            S0=100.0, K=100.0, r=0.05, sigma=0.2, T=1.0, num_paths=900, random_seed=101
        )
        p2 = MonteCarloPricer(
            S0=100.0, K=100.0, r=0.05, sigma=0.2, T=1.0, num_paths=900, random_seed=101
        )
        p3 = MonteCarloPricer(
            S0=100.0, K=100.0, r=0.05, sigma=0.2, T=1.0, num_paths=900, random_seed=102
        )
        r1 = p1.price_option()
        r2 = p2.price_option()
        r3 = p3.price_option()
        self.assertAlmostEqual(r1.estimated_price, r2.estimated_price, places=12)
        self.assertNotEqual(r1.estimated_price, r3.estimated_price)

    def test_timing_instrumentation_present(self):
        pricer = MonteCarloPricer(
            S0=100.0,
            K=100.0,
            r=0.05,
            sigma=0.2,
            T=1.0,
            num_paths=1500,
            random_seed=2,
        )
        result = pricer.price_option()
        self.assertGreaterEqual(result.total_runtime_ms, 0.0)
        self.assertGreaterEqual(result.cache_lookup_time_ms, 0.0)
        self.assertGreaterEqual(result.simulation_time_ms, 0.0)
        self.assertGreaterEqual(result.payoff_aggregation_time_ms, 0.0)
        self.assertGreaterEqual(result.cache_put_time_ms, 0.0)

    def test_cache_store_extended_diagnostics(self):
        store = SimpleCacheStore()
        hit, _ = store.try_get({"k": 1}, policy_approved_reuse=True)
        self.assertFalse(hit)
        store.put({"k": 1}, {"v": 1})
        store.put({"k": 1}, {"v": 2})  # overwrite
        store.get({"k": 1})
        stats = store.stats()
        self.assertEqual(stats["put_count"], 2)
        self.assertEqual(stats["overwrite_count"], 1)
        self.assertEqual(stats["lookup_count"], 2)
        self.assertEqual(stats["miss_after_policy_approved_count"], 1)
        self.assertIn("hit_rate", stats)
        self.assertIn("miss_rate", stats)
        self.assertIn("unique_lookup_keys", stats)
        self.assertIn("repeated_lookup_keys", stats)
        self.assertGreaterEqual(len(store.top_repeated_keys()), 1)

    def test_ai_policy_fallback_modes(self):
        features = {
            "instrument_type": "european_call",
            "num_paths": 5000,
            "volatility": 0.2,
            "maturity": 1.0,
        }
        self.assertTrue(AIAssistedCachePolicy(model=None, fallback_mode="always_reuse").decide(features))
        self.assertFalse(AIAssistedCachePolicy(model=None, fallback_mode="no_reuse").decide(features))
        heuristic_decision = HeuristicCachePolicy().decide(features)
        self.assertEqual(
            AIAssistedCachePolicy(model=None, fallback_mode="heuristic").decide(features),
            heuristic_decision,
        )

        class BrokenModel:
            def predict_proba(self, arr):
                raise RuntimeError("inference broke")

        policy = AIAssistedCachePolicy(model=BrokenModel(), fallback_mode="no_reuse")
        self.assertFalse(policy.decide(features))
        self.assertNotEqual(policy.last_inference_error, "")
        diagnostics = policy.diagnostics()
        self.assertEqual(diagnostics["fallback_inference_error_count"], 1)
        self.assertEqual(diagnostics["fallback_used_count"], 1)
        self.assertEqual(diagnostics["model_inference_used_count"], 0)
        self.assertEqual(diagnostics["last_decision_source"], "fallback_inference_error")

    def test_ai_policy_invalid_fallback_mode_fails_loudly(self):
        with self.assertRaises(ValueError):
            AIAssistedCachePolicy(model=None, fallback_mode="unsupported_mode")

    def test_canonical_exact_match_experiment_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            out_csv = Path(td) / "exact_match_cache_results.csv"
            progress = Path(td) / "exact_match_progress.jsonl"
            checkpoint = Path(td) / "exact_match_checkpoint.json"
            summary = run_canonical_exact_match_cache_experiment(
                num_trials=4,
                output_csv_path=out_csv,
                random_seed=33,
                scale_label="smoke",
                progress_jsonl_path=progress,
                checkpoint_json_path=checkpoint,
            )
            self.assertEqual(summary["experiment_name"], "canonical_exact_match_cache_experiment")
            self.assertEqual(summary["scale_label"], "smoke")
            self.assertEqual(len(summary["per_condition"]), 4)
            labels = {row["experiment_label"] for row in summary["per_condition"]}
            self.assertEqual(
                labels,
                {
                    "no_cache_baseline",
                    "exact_cache_no_policy_gate",
                    "heuristic_policy_plus_cache",
                    "ai_assisted_stub_policy_plus_cache",
                },
            )
            self.assertTrue(out_csv.exists())
            self.assertTrue(progress.exists())
            self.assertTrue(checkpoint.exists())
            self.assertGreater(out_csv.read_text().count("\n"), 1)
            self.assertIn("valid_evidence_conditions", summary)
            self.assertIn("excluded_conditions", summary)
            self.assertIn("forensic_cases", summary)
            self.assertTrue(summary["summary_computed_from_valid_evidence_only"])
            ai_row = next(
                row
                for row in summary["per_condition"]
                if row["experiment_label"] == "ai_assisted_stub_policy_plus_cache"
            )
            self.assertEqual(ai_row["execution_status"], "executed_degraded")
            self.assertFalse(ai_row["evidence_valid"])
            self.assertTrue(ai_row["excluded_from_summary"])

    def test_repeated_pricing_experiment_has_runtime_fields(self):
        def _factory():
            return MonteCarloPricer(
                S0=100.0,
                K=100.0,
                r=0.05,
                sigma=0.2,
                T=1.0,
                num_paths=800,
                random_seed=17,
                cache_store=SimpleCacheStore(),
            )

        summary = run_repeated_pricing_experiment(_factory, num_trials=3)
        self.assertIn("total_runtime_ms", summary)
        self.assertIn("average_runtime_per_trial_ms", summary)
        self.assertIn("hit_rate", summary)
        self.assertEqual(summary["scale_label"], "standard")
        self.assertEqual(summary["completed_trials"], 3)

    def test_similarity_replay_experiment_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            out_csv = Path(td) / "similarity_cache_replay_results.csv"
            out_manifest = Path(td) / "similarity_cache_replay_manifest.json"
            progress = Path(td) / "similarity_progress.jsonl"
            checkpoint = Path(td) / "similarity_checkpoint.json"
            summary = run_similarity_cache_replay_experiment(
                num_requests=12,
                pricing_kwargs={"num_paths": 600},
                random_seed=41,
                similarity_threshold=0.9,
                scale_label="smoke",
                output_csv_path=out_csv,
                output_manifest_path=out_manifest,
                progress_jsonl_path=progress,
                checkpoint_json_path=checkpoint,
            )
            self.assertEqual(summary["experiment_name"], "similarity_cache_replay_experiment")
            self.assertEqual(summary["scale_label"], "smoke")
            self.assertEqual(summary["num_requests"], 12)
            self.assertEqual(len(summary["strategies"]), 3)
            labels = {row["strategy_label"] for row in summary["strategies"]}
            self.assertEqual(labels, {"no_cache", "exact_cache", "similarity_cache"})
            self.assertIn("valid_evidence_strategies", summary)
            self.assertIn("excluded_strategies", summary)
            self.assertIn("forensic_cases", summary)
            self.assertTrue(summary["summary_computed_from_valid_evidence_only"])
            for row in summary["strategies"]:
                self.assertIn("execution_status", row)
                self.assertIn("evidence_valid", row)
                self.assertIn("excluded_from_summary", row)
                self.assertIn("forensic_case_count", row)
            self.assertTrue(out_csv.exists())
            self.assertTrue(out_manifest.exists())
            self.assertTrue(progress.exists())
            self.assertTrue(checkpoint.exists())

    def test_similarity_replay_can_fail_loudly_on_quality_threshold(self):
        with self.assertRaises(RuntimeError):
            run_similarity_cache_replay_experiment(
                num_requests=10,
                pricing_kwargs={"num_paths": 500},
                random_seed=29,
                similarity_threshold=0.1,
                fail_on_low_similarity_quality=True,
                max_mean_abs_error=1e-12,
            )


if __name__ == "__main__":
    unittest.main()

