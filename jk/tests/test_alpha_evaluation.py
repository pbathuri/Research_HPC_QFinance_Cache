"""Tests for alpha_evaluation (pandas)."""

import unittest

import pandas as pd

from qhpc_cache.alpha_evaluation import (
    compare_feature_stability,
    compute_forward_returns,
    evaluate_feature_information_coefficient,
    summarize_feature_predictiveness,
)


class TestAlphaEvaluation(unittest.TestCase):
    def test_forward_returns_shape(self):
        wide = pd.DataFrame(
            [[0.01, -0.02], [0.0, 0.03], [0.02, 0.01]],
            index=pd.date_range("2020-01-01", periods=3),
            columns=["A", "B"],
        )
        fwd = compute_forward_returns(wide, horizon=2)
        self.assertEqual(fwd.shape, wide.shape)

    def test_ic_summary(self):
        wide_f = pd.DataFrame(
            [[1.0, 2.0], [1.1, 1.9], [1.2, 2.1]],
            index=pd.date_range("2020-01-01", periods=3),
            columns=["A", "B"],
        )
        wide_r = pd.DataFrame(
            [[0.01, 0.02], [0.02, 0.01], [0.0, 0.03]],
            index=wide_f.index,
            columns=["A", "B"],
        )
        ic = evaluate_feature_information_coefficient(wide_f, wide_r)
        summary = summarize_feature_predictiveness(ic)
        self.assertIn("mean_ic", summary)
        stab = compare_feature_stability(ic)
        self.assertIn("first_half_mean", stab)


if __name__ == "__main__":
    unittest.main()
