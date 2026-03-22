"""Experiment runner smoke tests."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache.cache_policy import HeuristicCachePolicy, LogisticCachePolicy
from qhpc_cache.experiment_configs import (
    CacheExperimentConfig,
    MonteCarloExperimentConfig,
)
from qhpc_cache.experiment_runner import (
    run_cache_policy_comparison_experiment,
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


if __name__ == "__main__":
    unittest.main()
