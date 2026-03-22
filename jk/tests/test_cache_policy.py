"""Tests for cache policy and cache store."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache import AIAssistedCachePolicy, SimpleCacheStore
from qhpc_cache.cache_policy import HeuristicCachePolicy, LogisticCachePolicy


class TestAIAssistedCachePolicy(unittest.TestCase):
    """Basic tests for AIAssistedCachePolicy.decide."""

    def test_decide_returns_bool(self):
        """decide(features) returns a boolean."""
        policy = AIAssistedCachePolicy()
        features = {
            "instrument_type": "call_option",
            "num_paths": 10000,
            "volatility": 0.2,
            "maturity": 1.0,
        }
        result = policy.decide(features)
        self.assertIsInstance(result, bool)


class TestHeuristicCachePolicy(unittest.TestCase):
    """Basic test for HeuristicCachePolicy.decide."""

    def test_decide_reuse_when_within_limits(self):
        """decide returns True when num_paths <= 100000 and volatility < 0.30."""
        policy = HeuristicCachePolicy()
        self.assertTrue(policy.decide({"num_paths": 10000, "volatility": 0.2}))
        self.assertFalse(policy.decide({"num_paths": 200000, "volatility": 0.2}))
        self.assertFalse(policy.decide({"num_paths": 10000, "volatility": 0.5}))

    def test_exact_match_overrides_volatility(self):
        policy = HeuristicCachePolicy()
        features = {"num_paths": 200000, "volatility": 0.5, "exact_match_exists": True}
        self.assertTrue(policy.decide(features))


class TestLogisticCachePolicy(unittest.TestCase):
    def test_decide_returns_bool(self):
        policy = LogisticCachePolicy()
        features = {
            "num_paths": 5000,
            "volatility": 0.2,
            "maturity": 1.0,
            "similarity_score": 0.8,
            "exact_match_exists": True,
        }
        self.assertIsInstance(policy.decide(features), bool)


class TestSimpleCacheStore(unittest.TestCase):
    """Basic tests for SimpleCacheStore store and retrieve."""

    def test_store_and_retrieve(self):
        """put(features, value) then get(features) returns the value."""
        store = SimpleCacheStore()
        features = {"key": "test", "n": 42}
        value = (10.5, 0.01)
        store.put(features, value)
        retrieved = store.get(features)
        self.assertEqual(retrieved, value)


if __name__ == "__main__":
    unittest.main()
