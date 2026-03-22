"""Variance reduction helpers for Monte Carlo option pricing.

**Why variance reduction matters**: Option prices are expectations of discounted
payoffs. The standard Monte Carlo error shrinks roughly as 1/sqrt(n_paths).
Antithetic variates induce negative correlation between paired paths; control
variates use a correlated quantity with known mean to subtract noise. Both aim
for the **same unbiased (or nearly unbiased) expectation** with smaller
variance per path count—valuable when each path is expensive (e.g. future
quantum or HPC phases).
"""

from __future__ import annotations

import math
import random
from typing import List, Optional, Sequence, Tuple


def generate_antithetic_standard_normal_pairs(
    number_of_pairs: int,
    random_seed: Optional[int] = None,
) -> List[float]:
    """Return ``2 * number_of_pairs`` samples: Z_1, -Z_1, Z_2, -Z_2, ...

    Each pair shares the same magnitude; use with terminal or stepwise GBM
    draws that are linear in Z for classic antithetic variance reduction.
    """
    if number_of_pairs < 1:
        raise ValueError("number_of_pairs must be at least 1.")
    rng = random.Random(random_seed) if random_seed is not None else random.Random()
    out: List[float] = []
    for pair_index in range(number_of_pairs):
        z = rng.gauss(0.0, 1.0)
        out.append(z)
        out.append(-z)
    return out


def apply_antithetic_variates_to_normals(standard_normals: Sequence[float]) -> List[float]:
    """Return Z, -Z pairs for each input draw (length doubles)."""
    paired: List[float] = []
    for draw_index in range(len(standard_normals)):
        z = standard_normals[draw_index]
        paired.append(z)
        paired.append(-z)
    return paired


def estimate_standard_error(sample_values: Sequence[float]) -> float:
    """Standard error of the mean from raw i.i.d. samples (unbiased variance)."""
    sample_size = len(sample_values)
    if sample_size < 2:
        return 0.0
    total = 0.0
    for index in range(sample_size):
        total += sample_values[index]
    sample_mean = total / float(sample_size)
    sum_sq = 0.0
    for index in range(sample_size):
        diff = sample_values[index] - sample_mean
        sum_sq += diff * diff
    sample_variance = sum_sq / float(sample_size - 1)
    return math.sqrt(sample_variance / float(sample_size))


def estimate_standard_error_from_mean_variance(
    sample_mean: float,
    sample_variance: float,
    sample_size: int,
) -> float:
    """Standard error of the mean = sqrt(sample_variance / sample_size)."""
    if sample_size < 1:
        raise ValueError("sample_size must be at least 1.")
    if sample_size == 1:
        return 0.0
    return math.sqrt(max(sample_variance, 0.0) / float(sample_size))


def confidence_interval_from_standard_error(
    sample_mean: float,
    standard_error: float,
    confidence_level: float = 0.95,
) -> Tuple[float, float]:
    """Gaussian interval (teaching default): mean ± z * SE. z=1.96 at 95%."""
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be strictly between 0 and 1.")
    z_table = {
        0.90: 1.645,
        0.95: 1.96,
        0.99: 2.576,
    }
    z = z_table.get(confidence_level)
    if z is None:
        z = 1.96
    margin = z * standard_error
    return sample_mean - margin, sample_mean + margin


def _sample_mean(values: Sequence[float]) -> float:
    count = len(values)
    total = 0.0
    for index in range(count):
        total += values[index]
    return total / float(count)


def _sample_covariance(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError("Sequences must have equal length for covariance.")
    count = len(a)
    if count < 2:
        return 0.0
    mean_a = _sample_mean(a)
    mean_b = _sample_mean(b)
    sum_cross = 0.0
    for index in range(count):
        sum_cross += (a[index] - mean_a) * (b[index] - mean_b)
    return sum_cross / float(count - 1)


def _sample_variance(values: Sequence[float]) -> float:
    count = len(values)
    if count < 2:
        return 0.0
    mean_val = _sample_mean(values)
    sum_sq = 0.0
    for index in range(count):
        diff = values[index] - mean_val
        sum_sq += diff * diff
    return sum_sq / float(count - 1)


def control_variate_adjustment(
    discounted_payoff_samples: Sequence[float],
    control_variate_samples: Sequence[float],
    expected_control_variate: float,
) -> Tuple[float, float, float]:
    """Return (adjusted_mean, adjusted_sample_variance, beta_estimate).

    Y_cv_i = Y_i - beta * (X_i - E[X]) with beta = Cov(Y,X)/Var(X).
    """
    count = len(discounted_payoff_samples)
    if count != len(control_variate_samples):
        raise ValueError("Payoff and control samples must align in length.")
    if count < 2:
        raise ValueError("Need at least two paths for control variate beta.")
    var_x = _sample_variance(control_variate_samples)
    if var_x <= 0.0:
        raise ValueError("Control variate has zero sample variance; pick another control.")
    beta = _sample_covariance(
        discounted_payoff_samples, control_variate_samples
    ) / var_x
    adjusted_series: List[float] = []
    for index in range(count):
        y = discounted_payoff_samples[index]
        x = control_variate_samples[index]
        adjusted_series.append(y - beta * (x - expected_control_variate))
    adjusted_mean = _sample_mean(adjusted_series)
    adjusted_var = _sample_variance(adjusted_series)
    return adjusted_mean, adjusted_var, beta


def apply_control_variate_adjustment(
    raw_discounted_payoffs: Sequence[float],
    control_variate_samples: Sequence[float],
    control_variate_expected_value: float,
) -> Tuple[float, float]:
    """Apply control variate; return (adjusted_mean, adjusted_sample_variance)."""
    mean_adj, var_adj, _beta = control_variate_adjustment(
        raw_discounted_payoffs,
        control_variate_samples,
        control_variate_expected_value,
    )
    return mean_adj, var_adj
