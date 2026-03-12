"""Centralized configuration for pricing and demo parameters."""

from dataclasses import dataclass


@dataclass
class PricingConfig:
    """Option and Monte Carlo parameters for the pricer."""

    S0: float = 100.0
    K: float = 100.0
    r: float = 0.05
    sigma: float = 0.2
    T: float = 1.0
    num_paths: int = 10000


def get_default_config() -> PricingConfig:
    """Return the default pricing configuration."""
    return PricingConfig()
