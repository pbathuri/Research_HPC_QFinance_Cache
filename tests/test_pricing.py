"""Smoke tests for Monte Carlo pricing."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache import MonteCarloPricer


class TestMonteCarloPricer(unittest.TestCase):
    """Basic tests for price_option return value and sign."""

    def test_price_option_returns_two_floats(self):
        """price_option() returns (float, float)."""
        pricer = MonteCarloPricer(
            S0=100.0, K=100.0, r=0.05, sigma=0.2, T=1.0, num_paths=1000
        )
        result = pricer.price_option()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], float)
        self.assertIsInstance(result[1], float)

    def test_price_is_non_negative(self):
        """Option price (first element) is non-negative."""
        pricer = MonteCarloPricer(
            S0=100.0, K=100.0, r=0.05, sigma=0.2, T=1.0, num_paths=1000
        )
        price, _ = pricer.price_option()
        self.assertGreaterEqual(price, 0.0)


if __name__ == "__main__":
    unittest.main()
