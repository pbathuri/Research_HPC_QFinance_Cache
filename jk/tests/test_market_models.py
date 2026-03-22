"""Tests for GBM scenario generation."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache.market_models import (
    generate_price_path_scenarios,
    generate_terminal_price_scenarios,
    simulate_gbm_price_path,
    simulate_gbm_terminal_price,
)


class TestMarketModels(unittest.TestCase):
    def test_terminal_reproducible_with_seed(self):
        first = generate_terminal_price_scenarios(
            100.0, 0.05, 0.2, 1.0, 50, random_seed=21
        )
        second = generate_terminal_price_scenarios(
            100.0, 0.05, 0.2, 1.0, 50, random_seed=21
        )
        self.assertEqual(first, second)

    def test_terminal_deterministic_zero_vol_edge(self):
        spot = simulate_gbm_terminal_price(100.0, 0.05, 0.0, 1.0, 1.0)
        self.assertAlmostEqual(spot, 100.0 * __import__("math").exp(0.05), places=10)

    def test_path_length(self):
        paths = generate_price_path_scenarios(
            100.0, 0.05, 0.2, 1.0, 5, 10, random_seed=3
        )
        self.assertEqual(len(paths), 5)
        self.assertEqual(len(paths[0]), 11)

    def test_simulate_gbm_price_path_seed_reproducible(self):
        first = simulate_gbm_price_path(
            100.0, 0.05, 0.2, 1.0, 8, random_seed=2
        )
        second = simulate_gbm_price_path(
            100.0, 0.05, 0.2, 1.0, 8, random_seed=2
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
