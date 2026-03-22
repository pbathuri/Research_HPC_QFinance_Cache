"""Variance reduction utilities."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache.variance_reduction import (
    apply_antithetic_variates_to_normals,
    apply_control_variate_adjustment,
    confidence_interval_from_standard_error,
    control_variate_adjustment,
    estimate_standard_error,
    estimate_standard_error_from_mean_variance,
    generate_antithetic_standard_normal_pairs,
)


class TestVarianceReduction(unittest.TestCase):
    def test_antithetic_doubles_length(self):
        base = [0.5, -0.25]
        paired = apply_antithetic_variates_to_normals(base)
        self.assertEqual(len(paired), 4)

    def test_generate_antithetic_pairs_length(self):
        seq = generate_antithetic_standard_normal_pairs(4, random_seed=0)
        self.assertEqual(len(seq), 8)

    def test_control_variate_reduces_variance_on_synthetic(self):
        xs = [float(i - 5) for i in range(10)]
        ys = [xs[i] + 0.1 * (i - 4.5) for i in range(10)]
        discounted = ys
        controls = xs
        mean_y = sum(discounted) / len(discounted)
        var_y = sum((y - mean_y) ** 2 for y in discounted) / (len(discounted) - 1)
        adj_mean, adj_var, beta = control_variate_adjustment(
            discounted, controls, 0.0
        )
        self.assertIsInstance(beta, float)
        self.assertLessEqual(adj_var, var_y + 1e-9)
        adj2 = apply_control_variate_adjustment(discounted, controls, 0.0)
        self.assertAlmostEqual(adj2[0], adj_mean)
        self.assertAlmostEqual(adj2[1], adj_var)

    def test_standard_error_from_statistics_and_samples(self):
        se = estimate_standard_error_from_mean_variance(1.0, 4.0, 100)
        low, high = confidence_interval_from_standard_error(1.0, se)
        self.assertLess(low, high)
        xs = [1.0, 2.0, 3.0, 4.0]
        se2 = estimate_standard_error(xs)
        self.assertGreater(se2, 0.0)


if __name__ == "__main__":
    unittest.main()
