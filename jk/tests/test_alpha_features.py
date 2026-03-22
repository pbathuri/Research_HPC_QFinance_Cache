"""Tests for alpha_features (pandas)."""

import unittest

import pandas as pd

from qhpc_cache.alpha_features import (
    moving_average_spread_feature,
    price_momentum_feature,
    rolling_z_score_feature,
    simple_mean_reversion_feature,
)
class TestAlphaFeatures(unittest.TestCase):
    def test_price_momentum_non_empty(self):
        frame = pd.DataFrame(
            {
                "symbol": ["A"] * 30,
                "date": pd.date_range("2020-01-01", periods=30),
                "close": range(100, 130),
            }
        )
        out = price_momentum_feature(frame, lookback=5)
        self.assertIn("momentum", out.columns)
        self.assertFalse(out["momentum"].iloc[:5].notna().all())

    def test_ma_spread_column(self):
        frame = pd.DataFrame(
            {
                "symbol": ["B"] * 60,
                "date": pd.date_range("2020-01-01", periods=60),
                "close": [100 + i * 0.1 for i in range(60)],
            }
        )
        out = moving_average_spread_feature(frame, fast_window=5, slow_window=20)
        self.assertIn("ma_spread", out.columns)

    def test_rolling_z_score(self):
        frame = pd.DataFrame(
            {
                "symbol": ["C"] * 40,
                "date": pd.date_range("2020-01-01", periods=40),
                "signal": range(40),
            }
        )
        out = rolling_z_score_feature(
            frame, value_column="signal", window=10, output_column="z"
        )
        self.assertIn("z", out.columns)

    def test_mean_reversion_column(self):
        frame = pd.DataFrame(
            {
                "symbol": ["D"] * 25,
                "date": pd.date_range("2020-01-01", periods=25),
                "close": range(25),
            }
        )
        out = simple_mean_reversion_feature(frame, lookback=3)
        self.assertIn("mean_reversion", out.columns)


if __name__ == "__main__":
    unittest.main()
