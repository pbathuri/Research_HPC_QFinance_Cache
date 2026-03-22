"""Tests for Monte Carlo pricing."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache import MonteCarloPricer
from qhpc_cache.pricing import MonteCarloPricingResult


class TestMonteCarloPricer(unittest.TestCase):
    """Basic tests for price_option return value and sign."""

    def test_price_option_returns_result_dataclass(self):
        """price_option() returns MonteCarloPricingResult."""
        pricer = MonteCarloPricer(
            S0=100.0, K=100.0, r=0.05, sigma=0.2, T=1.0, num_paths=1000
        )
        result = pricer.price_option()
        self.assertIsInstance(result, MonteCarloPricingResult)
        self.assertIsInstance(result.estimated_price, float)
        self.assertIsInstance(result.payoff_variance, float)

    def test_price_is_non_negative_for_call(self):
        """Option price (call) is non-negative."""
        pricer = MonteCarloPricer(
            S0=100.0, K=100.0, r=0.05, sigma=0.2, T=1.0, num_paths=1000
        )
        result = pricer.price_option()
        self.assertGreaterEqual(result.estimated_price, 0.0)

    def test_analytic_reference_when_enabled(self):
        pricer = MonteCarloPricer(
            S0=100.0,
            K=100.0,
            r=0.05,
            sigma=0.2,
            T=1.0,
            num_paths=500,
            compare_analytic_black_scholes=True,
            random_seed=1,
        )
        result = pricer.price_option()
        self.assertIsNotNone(result.analytic_reference_price)


if __name__ == "__main__":
    unittest.main()
