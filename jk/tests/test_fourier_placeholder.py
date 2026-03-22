"""Fourier/COS bridge sanity checks."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache.analytic_pricing import black_scholes_call_price
from qhpc_cache.fourier_placeholder import cos_method_european_call_price


class TestFourierPlaceholder(unittest.TestCase):
    def test_cos_matches_black_scholes_within_tolerance(self):
        S0, K, r, sigma, T = 100.0, 100.0, 0.05, 0.2, 1.0
        bs = black_scholes_call_price(S0, K, r, sigma, T)
        cos_price = cos_method_european_call_price(S0, K, r, sigma, T)
        self.assertLess(abs(bs - cos_price), 5e-3)


if __name__ == "__main__":
    unittest.main()
