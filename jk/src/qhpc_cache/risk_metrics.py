"""Sample-based risk metrics (VaR and CVaR) from P&L scenarios.

Value at Risk (VaR) at confidence level alpha is the loss threshold such that
the probability of a worse loss is at most (1 - alpha). We implement the
**sample quantile** version: sort P&L (profit positive, loss negative) and read
off the appropriate percentile.

Conditional VaR (CVaR, expected shortfall) averages outcomes in the left tail
worse than VaR. For a discrete sample this is the mean of P&L values that are
less than or equal to the VaR threshold (loss side).

**Sign convention**: P&L is portfolio value change; negative P&L is a loss.
Returned VaR and CVaR are **positive numbers** expressing loss magnitude.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence


def compute_profit_and_loss_distribution(
    initial_portfolio_value: float,
    scenario_portfolio_values: Sequence[float],
) -> List[float]:
    """P&L for each scenario: scenario portfolio value minus initial value.

    Use this when you already have total portfolio mark-to-market values under
    each scenario. For per-underlying repricing workflows, build those scenario
    totals first, then pass them here.
    """
    pnl_list: List[float] = []
    for scenario_index in range(len(scenario_portfolio_values)):
        scenario_value = scenario_portfolio_values[scenario_index]
        pnl_list.append(scenario_value - initial_portfolio_value)
    return pnl_list


def compute_value_at_risk(
    profit_and_loss_values: Sequence[float],
    confidence_level: float = 0.95,
) -> float:
    """VaR as a **positive number** reporting potential loss magnitude.

    Convention: losses are negative P&L. Returned VaR is the loss amount
    (positive) such that losses worse than -VaR occur with probability at most
    (1 - confidence_level).

    Example: confidence_level=0.95 returns the 5th percentile loss magnitude.
    """
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must lie strictly between 0 and 1.")
    count = len(profit_and_loss_values)
    if count == 0:
        raise ValueError("Need at least one P&L sample.")
    sorted_pnl = sorted(profit_and_loss_values)
    tail_probability = 1.0 - confidence_level
    index = int(math.floor(tail_probability * count))
    index = max(0, min(index, count - 1))
    quantile_pnl = sorted_pnl[index]
    if quantile_pnl >= 0.0:
        return 0.0
    return -quantile_pnl


def compute_conditional_value_at_risk(
    profit_and_loss_values: Sequence[float],
    confidence_level: float = 0.95,
) -> float:
    """Expected shortfall on the loss side: mean of P&L <= VaR threshold."""
    var_loss = compute_value_at_risk(profit_and_loss_values, confidence_level)
    threshold = -var_loss
    tail_values: List[float] = []
    for sample_index in range(len(profit_and_loss_values)):
        value = profit_and_loss_values[sample_index]
        if value <= threshold:
            tail_values.append(value)
    if len(tail_values) == 0:
        return var_loss
    mean_tail = sum(tail_values) / float(len(tail_values))
    if mean_tail >= 0.0:
        return 0.0
    return -mean_tail


@dataclass
class DistributionSummary:
    """Simple descriptive stats for reporting."""

    sample_count: int
    sample_mean: float
    sample_std: float
    minimum: float
    maximum: float


def summarize_distribution(sample_values: Sequence[float]) -> DistributionSummary:
    """Univariate summary (population std with n denominator)."""
    count = len(sample_values)
    if count == 0:
        raise ValueError("sample_values must be non-empty.")
    total = 0.0
    for index in range(count):
        total += sample_values[index]
    mean_val = total / float(count)
    sum_sq = 0.0
    minimum = sample_values[0]
    maximum = sample_values[0]
    for index in range(count):
        value = sample_values[index]
        if value < minimum:
            minimum = value
        if value > maximum:
            maximum = value
        diff = value - mean_val
        sum_sq += diff * diff
    std = math.sqrt(sum_sq / float(count))
    return DistributionSummary(
        sample_count=count,
        sample_mean=mean_val,
        sample_std=std,
        minimum=minimum,
        maximum=maximum,
    )
