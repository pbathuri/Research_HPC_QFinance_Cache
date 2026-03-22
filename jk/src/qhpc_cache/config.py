"""Centralized configuration for pricing, experiments, and demos."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class PricingConfig:
    """Default single-name option and Monte Carlo parameters (research-scale, not HPC)."""

    S0: float = 100.0
    K: float = 100.0
    r: float = 0.05
    sigma: float = 0.2
    T: float = 1.0
    num_paths: int = 8_000


@dataclass
class PricingBaselineDefaults:
    """Finance-oriented aliases (same numbers as ``PricingConfig`` for teaching)."""

    initial_asset_price: float = 100.0
    strike_price: float = 100.0
    risk_free_rate: float = 0.05
    volatility: float = 0.2
    time_to_maturity: float = 1.0
    number_of_paths: int = 8_000


@dataclass
class ExperimentDefaults:
    """Small-scale experiment knobs (avoid huge trial counts in local runs)."""

    monte_carlo_replications: int = 5
    repeated_pricing_trials: int = 3
    payoff_comparison_paths: int = 4000


@dataclass
class PortfolioDemoDefaults:
    """Scenario list for the educational portfolio risk block."""

    baseline_underlying_price: float = 100.0
    scenario_underlying_prices: List[float] = field(
        default_factory=lambda: [85.0, 95.0, 100.0, 105.0, 115.0]
    )
    number_of_paths_per_line: int = 2000


@dataclass
class DemoRunDefaults:
    """Path counts and seeds for ``run_demo.py`` (keep demo fast and reproducible).

    Single place to tune the canonical demo without editing the script body.
    """

    european_call_paths: int = 6000
    european_call_seed: int = 123
    antithetic_paths: int = 3000
    antithetic_seed: int = 55
    antithetic_pairs_demo_count: int = 3
    antithetic_pairs_demo_seed: int = 7
    digital_call_paths: int = 8000
    digital_call_seed: int = 77
    asian_call_paths: int = 2500
    asian_time_steps: int = 8
    asian_call_seed: int = 88
    portfolio_paths_per_line: int = 2000
    portfolio_random_seed: int = 12
    cache_demo_max_paths: int = 4000
    cache_demo_seed: int = 5
    variance_reduction_paths: int = 3000
    variance_reduction_seed: int = 99


def get_default_config() -> PricingConfig:
    """Return the default pricing configuration."""
    return PricingConfig()


def get_demo_run_defaults() -> DemoRunDefaults:
    """Return defaults for the canonical ``run_demo.py`` walkthrough."""
    return DemoRunDefaults()
