"""Black–Scholes analytic checks."""

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache.analytic_pricing import (
    black_scholes_call_price,
    black_scholes_gamma,
    black_scholes_put_price,
    normal_cdf,
)


class TestAnalyticPricing(unittest.TestCase):
    def test_normal_cdf_symmetry(self):
        self.assertAlmostEqual(normal_cdf(0.0), 0.5, places=7)
        self.assertAlmostEqual(normal_cdf(1.0) + normal_cdf(-1.0), 1.0, places=7)

    def test_put_call_parity(self):
        S0, K, r, sigma, T = 100.0, 100.0, 0.05, 0.2, 1.0
        call = black_scholes_call_price(S0, K, r, sigma, T)
        put = black_scholes_put_price(S0, K, r, sigma, T)
        lhs = call - put
        rhs = S0 - K * math.exp(-r * T)
        self.assertAlmostEqual(lhs, rhs, places=6)

    def test_gamma_positive(self):
        g = black_scholes_gamma(100.0, 100.0, 0.05, 0.2, 1.0)
        self.assertGreater(g, 0.0)


if __name__ == "__main__":
    unittest.main()
