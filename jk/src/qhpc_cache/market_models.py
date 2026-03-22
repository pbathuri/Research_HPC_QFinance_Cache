"""Geometric Brownian Motion (GBM) simulation for risk-neutral Monte Carlo workflows.

Under standard Black–Scholes assumptions, the risk-neutral spot S(t) follows
dS = r S dt + sigma S dW. Parameters ``risk_free_rate`` and ``volatility`` are
**annualized**; ``time_to_maturity`` is the horizon in years for the simulated
segment.
"""

from __future__ import annotations

import math
import random
from typing import List, Optional, Sequence


def simulate_gbm_terminal_price(
    initial_asset_price: float,
    risk_free_rate: float,
    volatility: float,
    time_to_maturity: float,
    standard_normal_sample: float,
) -> float:
    """One draw of terminal spot S(T) under GBM given a single N(0,1) sample.

    S(T) = S(0) * exp((r - sigma^2/2) T + sigma * sqrt(T) * Z).

    Parameters
    ----------
    initial_asset_price
        S(0), strictly positive.
    risk_free_rate
        Annualized risk-free rate r (continuous compounding, consistent with discounting).
    volatility
        Annualized volatility sigma.
    time_to_maturity
        T in years; non-negative. If zero, returns S(0).
    standard_normal_sample
        One sample Z ~ N(0,1); caller supplies it for variance reduction coupling.
    """
    if initial_asset_price <= 0.0:
        raise ValueError("initial_asset_price must be positive.")
    if time_to_maturity < 0.0:
        raise ValueError("time_to_maturity must be non-negative.")
    if time_to_maturity == 0.0:
        return initial_asset_price
    drift_exponent = (risk_free_rate - 0.5 * volatility * volatility) * time_to_maturity
    diffusion = volatility * math.sqrt(time_to_maturity) * standard_normal_sample
    return initial_asset_price * math.exp(drift_exponent + diffusion)


def simulate_gbm_price_path_using_increments(
    initial_asset_price: float,
    risk_free_rate: float,
    volatility: float,
    time_to_maturity: float,
    number_of_time_steps: int,
    standard_normal_increments: Sequence[float],
) -> List[float]:
    """Simulate a discrete spot path including S(0) and S(T) on an even time grid.

    Path length is ``number_of_time_steps + 1`` with dt = T / number_of_time_steps.
    Each step uses the exact conditional GBM increment on log-price.

    Parameters
    ----------
    number_of_time_steps
        Number of subintervals; must be >= 1 when T > 0.
    standard_normal_increments
        Length ``number_of_time_steps`` of i.i.d. N(0,1) draws for each step.
    """
    if number_of_time_steps < 1:
        raise ValueError("number_of_time_steps must be at least 1 for a path.")
    if len(standard_normal_increments) != number_of_time_steps:
        raise ValueError(
            "standard_normal_increments length must equal number_of_time_steps."
        )
    if time_to_maturity < 0.0:
        raise ValueError("time_to_maturity must be non-negative.")
    if time_to_maturity == 0.0:
        return [initial_asset_price]
    dt = time_to_maturity / number_of_time_steps
    drift_step = (risk_free_rate - 0.5 * volatility * volatility) * dt
    diffusion_scale = volatility * math.sqrt(dt)
    path_prices: List[float] = [initial_asset_price]
    current_price = initial_asset_price
    for step_index in range(number_of_time_steps):
        z = standard_normal_increments[step_index]
        current_price = current_price * math.exp(drift_step + diffusion_scale * z)
        path_prices.append(current_price)
    return path_prices


def simulate_gbm_price_path(
    initial_asset_price: float,
    risk_free_rate: float,
    volatility: float,
    time_to_maturity: float,
    number_of_time_steps: int,
    random_seed: Optional[int] = None,
) -> List[float]:
    """Simulate one GBM path using an internal RNG (reproducible via ``random_seed``)."""
    rng = random.Random(random_seed) if random_seed is not None else random.Random()
    increments = [
        rng.gauss(0.0, 1.0) for step_index in range(number_of_time_steps)
    ]
    return simulate_gbm_price_path_using_increments(
        initial_asset_price,
        risk_free_rate,
        volatility,
        time_to_maturity,
        number_of_time_steps,
        increments,
    )


def generate_terminal_price_scenarios(
    initial_asset_price: float,
    risk_free_rate: float,
    volatility: float,
    time_to_maturity: float,
    number_of_paths: int,
    random_seed: Optional[int] = None,
) -> List[float]:
    """Draw many independent terminal prices S(T) (one per path)."""
    if number_of_paths < 1:
        raise ValueError("number_of_paths must be at least 1.")
    rng = random.Random(random_seed) if random_seed is not None else random.Random()
    terminals: List[float] = []
    for path_index in range(number_of_paths):
        z = rng.gauss(0.0, 1.0)
        terminals.append(
            simulate_gbm_terminal_price(
                initial_asset_price,
                risk_free_rate,
                volatility,
                time_to_maturity,
                z,
            )
        )
    return terminals


def generate_price_path_scenarios(
    initial_asset_price: float,
    risk_free_rate: float,
    volatility: float,
    time_to_maturity: float,
    number_of_paths: int,
    number_of_time_steps: int,
    random_seed: Optional[int] = None,
) -> List[List[float]]:
    """Draw many independent GBM paths (each list includes S(0) through S(T))."""
    if number_of_paths < 1:
        raise ValueError("number_of_paths must be at least 1.")
    rng = random.Random(random_seed) if random_seed is not None else random.Random()
    paths: List[List[float]] = []
    for path_index in range(number_of_paths):
        increments = [
            rng.gauss(0.0, 1.0) for step_index in range(number_of_time_steps)
        ]
        paths.append(
            simulate_gbm_price_path_using_increments(
                initial_asset_price,
                risk_free_rate,
                volatility,
                time_to_maturity,
                number_of_time_steps,
                increments,
            )
        )
    return paths
