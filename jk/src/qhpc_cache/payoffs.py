"""Option payoffs for Monte Carlo and semi-analytic reference workflows.

Naming convention
----------------
- **Terminal** payoffs depend only on spot at maturity S(T).
- **Path** payoffs depend on the entire sampled path ``asset_price_path``, a
  sequence with ``asset_price_path[0] = S(0)`` and final entry ``S(T)``. Asian
  payoffs use the arithmetic average of **all** sampled points (including S(0)
  unless you pre-slice the path upstream).
"""

from __future__ import annotations

from typing import Sequence


def european_call_payoff(terminal_asset_price: float, strike_price: float) -> float:
    """Terminal payoff max(S(T) - K, 0) for a European call."""
    return max(terminal_asset_price - strike_price, 0.0)


def european_put_payoff(terminal_asset_price: float, strike_price: float) -> float:
    """Terminal payoff max(K - S(T), 0) for a European put."""
    return max(strike_price - terminal_asset_price, 0.0)


def asian_call_payoff(asset_price_path: Sequence[float], strike_price: float) -> float:
    """Path-based payoff max(average(S along path) - K, 0).

    Differs from terminal payoffs: the payoff depends on the **path** (here via
    the arithmetic average), not only S(T).
    """
    if len(asset_price_path) == 0:
        return 0.0
    path_length = len(asset_price_path)
    running_sum = 0.0
    for step_index in range(path_length):
        running_sum += asset_price_path[step_index]
    average_spot = running_sum / path_length
    return max(average_spot - strike_price, 0.0)


def asian_put_payoff(asset_price_path: Sequence[float], strike_price: float) -> float:
    """Path-based payoff max(K - average(S along path), 0)."""
    if len(asset_price_path) == 0:
        return 0.0
    path_length = len(asset_price_path)
    running_sum = 0.0
    for step_index in range(path_length):
        running_sum += asset_price_path[step_index]
    average_spot = running_sum / path_length
    return max(strike_price - average_spot, 0.0)


def digital_call_payoff(
    terminal_asset_price: float,
    strike_price: float,
    payout_amount: float = 1.0,
) -> float:
    """Terminal cash-or-nothing digital: ``payout_amount`` if S(T) > K else 0."""
    return payout_amount if terminal_asset_price > strike_price else 0.0


def digital_put_payoff(
    terminal_asset_price: float,
    strike_price: float,
    payout_amount: float = 1.0,
) -> float:
    """Terminal digital: ``payout_amount`` if S(T) < K else 0."""
    return payout_amount if terminal_asset_price < strike_price else 0.0
