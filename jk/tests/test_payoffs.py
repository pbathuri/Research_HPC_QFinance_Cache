"""Tests for payoff functions."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache import payoffs


class TestPayoffs(unittest.TestCase):
    def test_european_call(self):
        self.assertEqual(payoffs.european_call_payoff(110.0, 100.0), 10.0)
        self.assertEqual(payoffs.european_call_payoff(90.0, 100.0), 0.0)

    def test_asian_call_average_includes_all_points(self):
        path = [100.0, 110.0, 120.0]
        avg = (100.0 + 110.0 + 120.0) / 3.0
        self.assertAlmostEqual(
            payoffs.asian_call_payoff(path, 100.0), max(avg - 100.0, 0.0)
        )

    def test_digital_payout_amount(self):
        self.assertEqual(
            payoffs.digital_call_payoff(105.0, 100.0, payout_amount=2.5), 2.5
        )
        self.assertEqual(
            payoffs.digital_put_payoff(95.0, 100.0, payout_amount=3.0), 3.0
        )


if __name__ == "__main__":
    unittest.main()
