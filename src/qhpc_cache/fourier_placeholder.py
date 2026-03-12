"""Placeholders for future Fourier-based pricing and variance reduction."""

from dataclasses import dataclass
from typing import Tuple


# Future stub: parameters needed for characteristic-function or COS-method pricing.
@dataclass
class FourierPricingPlaceholder:
    """Placeholder for Fourier-based pricing extension (not yet implemented).

    Future work could use the characteristic function of log-price to compute
    option prices via Fourier inversion (e.g. COS method) or to provide an
    analytic control variate for Monte Carlo variance reduction.
    """

    integration_limit: float = 10.0  # truncation for Fourier integral / COS series
    num_cos_terms: int = 128  # series terms if using COS method


def fourier_control_variate_reference(
    S0: float, K: float, r: float, sigma: float, T: float
) -> float:
    """Return a placeholder reference price for future Fourier-based control variate.

    Not implemented: returns 0.0. In future, this could return the analytic
    Black–Scholes call price or a COS-method price so Monte Carlo can use
    (mc_estimate - this + analytic) for variance reduction.
    """
    _ = S0, K, r, sigma, T  # unused until implemented
    return 0.0


def fourier_price_placeholder(
    S0: float, K: float, r: float, sigma: float, T: float
) -> Tuple[float, float]:
    """Placeholder for future Fourier-based option price and optional variance estimate.

    Returns (0.0, 0.0). Future implementation could use characteristic function
    and COS method to return (price, 0.0) for comparison with Monte Carlo.
    """
    _ = S0, K, r, sigma, T
    return (0.0, 0.0)
