"""Risk metric smoke tests."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache.risk_metrics import (
    compute_conditional_value_at_risk,
    compute_profit_and_loss_distribution,
    compute_value_at_risk,
    summarize_distribution,
)


class TestRiskMetrics(unittest.TestCase):
    def test_var_non_negative_loss(self):
        pnl = [-5.0, -4.0, -1.0, 0.0, 1.0, 2.0]
        var_loss = compute_value_at_risk(pnl, 0.9)
        self.assertGreaterEqual(var_loss, 0.0)

    def test_cvar_at_least_var(self):
        pnl = [-10.0, -6.0, -2.0, 0.0, 3.0]
        var_loss = compute_value_at_risk(pnl, 0.95)
        cvar_loss = compute_conditional_value_at_risk(pnl, 0.95)
        self.assertGreaterEqual(cvar_loss + 1e-9, var_loss - 1e-9)

    def test_summarize_distribution(self):
        summary = summarize_distribution([1.0, 2.0, 3.0])
        self.assertEqual(summary.sample_count, 3)
        self.assertAlmostEqual(summary.sample_mean, 2.0)

    def test_profit_and_loss_distribution(self):
        initial = 100.0
        scenarios = [90.0, 100.0, 110.0]
        pnl = compute_profit_and_loss_distribution(initial, scenarios)
        self.assertEqual(pnl, [-10.0, 0.0, 10.0])


if __name__ == "__main__":
    unittest.main()
