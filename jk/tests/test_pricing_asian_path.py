"""Path-mode (Asian) Monte Carlo tests — covers integration contract from Codex audit.

Pins behavior: GBM path includes S(0); Asian payoff averages every point on that path.
Also validates explicit errors for invalid ``num_paths`` / ``num_time_steps``.
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache.pricing import MonteCarloPricer


class TestMonteCarloPricerPathValidation(unittest.TestCase):
    def test_num_paths_zero_raises_value_error_terminal(self):
        pricer = MonteCarloPricer(
            S0=100.0,
            K=100.0,
            r=0.05,
            sigma=0.2,
            T=1.0,
            num_paths=0,
            simulation_mode="terminal",
        )
        with self.assertRaises(ValueError) as context:
            pricer.price_option()
        self.assertIn("num_paths", str(context.exception).lower())

    def test_num_paths_zero_raises_value_error_path(self):
        pricer = MonteCarloPricer(
            S0=100.0,
            K=100.0,
            r=0.05,
            sigma=0.2,
            T=1.0,
            num_paths=0,
            payoff_type="asian_call",
            simulation_mode="path",
            num_time_steps=2,
        )
        with self.assertRaises(ValueError) as context:
            pricer.price_option()
        self.assertIn("num_paths", str(context.exception).lower())

    def test_num_time_steps_zero_path_mode_raises(self):
        pricer = MonteCarloPricer(
            S0=100.0,
            K=100.0,
            r=0.05,
            sigma=0.2,
            T=1.0,
            num_paths=1,
            payoff_type="asian_call",
            simulation_mode="path",
            num_time_steps=0,
        )
        with self.assertRaises(ValueError) as context:
            pricer.price_option()
        self.assertIn("num_time_steps", str(context.exception).lower())

    def test_european_call_in_path_mode_raises(self):
        pricer = MonteCarloPricer(
            S0=100.0,
            K=100.0,
            r=0.05,
            sigma=0.2,
            T=1.0,
            num_paths=1,
            payoff_type="european_call",
            simulation_mode="path",
            num_time_steps=1,
        )
        with self.assertRaises(ValueError) as context:
            pricer.price_option()
        self.assertIn("asian", str(context.exception).lower())


class TestMonteCarloPricerAsianPathIntegration(unittest.TestCase):
    def test_asian_call_path_sigma_zero_matches_closed_form_average(self):
        """Volatility zero: path is deterministic; average includes S(0) per payoffs contract."""
        S0 = 100.0
        strike_price = 100.0
        risk_free_rate = 0.05
        maturity = 1.0
        num_time_steps = 2
        dt = maturity / num_time_steps
        drift_per_step = risk_free_rate * dt
        s1 = S0 * math.exp(drift_per_step)
        s2 = s1 * math.exp(drift_per_step)
        average_spot = (S0 + s1 + s2) / 3.0
        intrinsic = max(average_spot - strike_price, 0.0)
        expected_discounted = math.exp(-risk_free_rate * maturity) * intrinsic

        pricer = MonteCarloPricer(
            S0=S0,
            K=strike_price,
            r=risk_free_rate,
            sigma=0.0,
            T=maturity,
            num_paths=1,
            payoff_type="asian_call",
            simulation_mode="path",
            num_time_steps=num_time_steps,
            random_seed=99,
        )
        result = pricer.price_option()
        self.assertAlmostEqual(result.estimated_price, expected_discounted, places=10)
        self.assertEqual(result.number_of_paths, 1)
        self.assertEqual(result.payoff_name, "asian_call")

    def test_asian_put_path_sigma_zero_matches_closed_form_average(self):
        S0 = 100.0
        strike_price = 105.0
        risk_free_rate = 0.05
        maturity = 1.0
        num_time_steps = 2
        dt = maturity / num_time_steps
        drift_per_step = risk_free_rate * dt
        s1 = S0 * math.exp(drift_per_step)
        s2 = s1 * math.exp(drift_per_step)
        average_spot = (S0 + s1 + s2) / 3.0
        intrinsic = max(strike_price - average_spot, 0.0)
        expected_discounted = math.exp(-risk_free_rate * maturity) * intrinsic

        pricer = MonteCarloPricer(
            S0=S0,
            K=strike_price,
            r=risk_free_rate,
            sigma=0.0,
            T=maturity,
            num_paths=1,
            payoff_type="asian_put",
            simulation_mode="path",
            num_time_steps=num_time_steps,
            random_seed=1,
        )
        result = pricer.price_option()
        self.assertAlmostEqual(result.estimated_price, expected_discounted, places=10)
        self.assertEqual(result.payoff_name, "asian_put")

    def test_antithetic_doubles_effective_paths_for_asian(self):
        pricer = MonteCarloPricer(
            S0=100.0,
            K=100.0,
            r=0.05,
            sigma=0.0,
            T=1.0,
            num_paths=2,
            payoff_type="asian_call",
            simulation_mode="path",
            num_time_steps=2,
            use_antithetic_variates=True,
            random_seed=1,
        )
        result = pricer.price_option()
        self.assertTrue(result.used_antithetic_variates)
        self.assertEqual(result.number_of_paths, 4)


if __name__ == "__main__":
    unittest.main()
