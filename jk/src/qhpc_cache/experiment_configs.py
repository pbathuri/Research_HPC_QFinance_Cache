"""Typed experiment configuration objects for reproducible research runs.

Defaults favor **laptop-friendly** runtimes (a few thousand paths). Increase
``num_paths`` and ``num_replications`` when you need tighter standard errors
for publication-style tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MonteCarloExperimentConfig:
    """Single-instrument Monte Carlo study (batch replications, optional seeds)."""

    initial_spot_price: float = 100.0
    strike_price: float = 100.0
    risk_free_rate: float = 0.05
    volatility: float = 0.2
    maturity_in_years: float = 1.0
    num_paths: int = 5_000
    payoff_type: str = "european_call"
    simulation_mode: str = "terminal"
    use_antithetic_variates: bool = False
    use_black_scholes_control_variate: bool = False
    compare_analytic_black_scholes: bool = True
    random_seed: Optional[int] = 7
    num_replications: int = 3


@dataclass
class PortfolioExperimentConfig:
    """Portfolio pricing + scenario P&L / VaR experiment."""

    position_labels: List[str] = field(
        default_factory=lambda: ["line_a", "line_b"]
    )
    num_paths_per_position: int = 2_500
    random_seed: int = 11
    scenario_spots: List[float] = field(
        default_factory=lambda: [80.0, 90.0, 100.0, 110.0, 120.0]
    )
    baseline_spot: float = 100.0
    confidence_level: float = 0.95


@dataclass
class CacheExperimentConfig:
    """Compare cache policies under repeated identical synthetic requests."""

    num_requests: int = 5
    base_features: dict = field(default_factory=dict)
