"""Cache policy feature builders."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache.cache_policy_features import (
    build_cache_decision_features,
    explain_cache_features,
)


class TestCachePolicyFeatures(unittest.TestCase):
    def test_build_contains_expected_keys(self):
        features = build_cache_decision_features(
            payoff_family="european_call",
            maturity_in_years=0.5,
            volatility=0.25,
            expected_depth=80,
            expected_qubits=10,
            predicted_reuse_count=2,
            estimated_compile_cost=0.5,
            portfolio_cluster_label="desk_a",
            similarity_score=0.7,
            exact_match_exists=False,
            num_paths=2000,
        )
        self.assertEqual(features["payoff_family"], "european_call")
        self.assertIn("maturity_bucket", features)

    def test_explain_non_empty(self):
        features = build_cache_decision_features(
            payoff_family="european_put",
            maturity_in_years=2.0,
            volatility=0.3,
            expected_depth=50,
            expected_qubits=8,
            predicted_reuse_count=0,
            estimated_compile_cost=1.0,
            portfolio_cluster_label="x",
            similarity_score=0.1,
            exact_match_exists=True,
            num_paths=1000,
        )
        text = explain_cache_features(features)
        self.assertIn("payoff_family", text)


if __name__ == "__main__":
    unittest.main()
