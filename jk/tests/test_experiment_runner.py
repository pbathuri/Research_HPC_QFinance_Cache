"""Experiment runner smoke tests."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache.cache_policy import HeuristicCachePolicy, LogisticCachePolicy
from qhpc_cache.experiment_configs import (
    CacheExperimentConfig,
    MonteCarloExperimentConfig,
)
from qhpc_cache.experiment_runner import (
    get_experiment_ladder,
    run_cache_policy_comparison_experiment,
    run_local_research_sweep,
    run_monte_carlo_study,
    run_payoff_comparison_experiment,
)

class TestExperimentRunner(unittest.TestCase):
    def test_monte_carlo_study_keys(self):
        cfg = MonteCarloExperimentConfig(num_replications=2, num_paths=200)
        out = run_monte_carlo_study(cfg)
        self.assertIn("mean_estimate", out)
        self.assertEqual(len(out["replication_estimates"]), 2)

    def test_payoff_comparison_experiment(self):
        out = run_payoff_comparison_experiment(
            ["european_call", "digital_call"],
            number_of_paths=400,
            random_seed=3,
        )
        self.assertEqual(len(out["per_payoff"]), 2)
        self.assertIn("estimated_price", out["per_payoff"][0])

    def test_cache_policy_comparison(self):
        cache_cfg = CacheExperimentConfig(
            num_requests=4,
            base_features={
                "instrument_type": "european_call",
                "num_paths": 1000,
                "volatility": 0.2,
                "maturity": 1.0,
            },
        )
        policies = {
            "heuristic": HeuristicCachePolicy(),
            "logistic": LogisticCachePolicy(),
        }
        result = run_cache_policy_comparison_experiment(cache_cfg, policies)
        self.assertIn("heuristic", result["per_policy"])
        self.assertIn("execution_status", result["per_policy"]["heuristic"])
        self.assertIn("evidence_valid", result["per_policy"]["heuristic"])
        self.assertIn("valid_evidence_policies", result)
        self.assertIn("forensic_cases", result)
        self.assertTrue(result["summary_computed_from_valid_evidence_only"])

    def test_local_research_sweep_smoke_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "long_runs"
            manifest = run_local_research_sweep(
                output_dir=out,
                scale_label="smoke",
                random_seed=55,
                resume_from_checkpoint=True,
            )
            self.assertEqual(manifest["scale_label"], "smoke")
            self.assertEqual(manifest["tiers_selected"], [1, 2])
            self.assertIn("outputs", manifest)
            self.assertIn("exact_match", manifest["outputs"])
            self.assertIn("seeded_repeated_family", manifest["outputs"])
            self.assertIn("policy_comparison", manifest["outputs"])
            self.assertIn("similarity_replay", manifest["outputs"])
            self.assertIn("forensic_outputs", manifest)
            self.assertTrue((out / "local_research_sweep_manifest.json").exists())
            self.assertTrue((out / "local_research_sweep_progress.jsonl").exists())
            self.assertTrue((out / "exact_match_checkpoint.json").exists())
            self.assertTrue((out / "seeded_repeated_family_checkpoint.json").exists())
            self.assertTrue((out / "similarity_replay_checkpoint.json").exists())

    def test_experiment_ladder_order_and_tiers(self):
        ladder = get_experiment_ladder()
        self.assertGreaterEqual(len(ladder), 4)
        tier_sequence = [int(row["tier"]) for row in ladder]
        self.assertEqual(tier_sequence, sorted(tier_sequence))
        self.assertEqual(int(ladder[0]["tier"]), 1)

    def test_local_research_sweep_tier_selection(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "long_runs_tier1"
            manifest = run_local_research_sweep(
                output_dir=out,
                scale_label="smoke",
                random_seed=66,
                resume_from_checkpoint=True,
                tiers_to_run=[1],
            )
            self.assertEqual(manifest["tiers_selected"], [1])
            self.assertIn("seeded_repeated_family", manifest["outputs"])
            self.assertNotIn("similarity_replay", manifest["outputs"])
            excluded_ids = {row["experiment_id"] for row in manifest["excluded_ladder_steps"]}
            self.assertIn("similarity_cache_replay_experiment", excluded_ids)


if __name__ == "__main__":
    unittest.main()
