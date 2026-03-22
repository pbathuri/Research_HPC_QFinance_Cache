"""Portfolio helpers."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache.portfolio import (
    OptionPosition,
    PortfolioPricingRequest,
    compute_portfolio_profit_and_loss,
    price_portfolio_positions,
    summarize_portfolio_risk,
)


class TestPortfolio(unittest.TestCase):
    def test_price_portfolio_single_line(self):
        positions = [
            OptionPosition(
                position_name="c1",
                payoff_name="european_call",
                quantity=1.0,
                initial_asset_price=100.0,
                strike_price=100.0,
                risk_free_rate=0.05,
                volatility=0.2,
                time_to_maturity=1.0,
            )
        ]
        request = PortfolioPricingRequest(
            portfolio_name="one_call",
            positions=positions,
            number_of_paths=500,
            random_seed=0,
        )
        result = price_portfolio_positions(request)
        self.assertGreater(result.total_estimated_value, 0.0)

    def test_pnl_length_matches_scenarios(self):
        positions = [
            OptionPosition(
                position_name="c1",
                payoff_name="european_call",
                quantity=1.0,
                initial_asset_price=100.0,
                strike_price=100.0,
                risk_free_rate=0.05,
                volatility=0.2,
                time_to_maturity=1.0,
            )
        ]
        spots = [90.0, 100.0, 110.0]
        request = PortfolioPricingRequest(
            portfolio_name="pnl_test",
            positions=positions,
            scenario_underlying_prices=spots,
            baseline_underlying_price=100.0,
        )
        pnl = compute_portfolio_profit_and_loss(request)
        self.assertEqual(len(pnl), len(spots))
        risk = summarize_portfolio_risk(request, confidence_level=0.95)
        self.assertGreaterEqual(risk.value_at_risk, 0.0)


if __name__ == "__main__":
    unittest.main()
