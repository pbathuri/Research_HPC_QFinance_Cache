"""Fourier / COS-style semi-analytic pricing for European options under GBM.

The filename uses ``placeholder`` to signal this is **not** a vendor COS library,
but the implementation is **mathematically concrete**: characteristic function of
log-spot, cosine expansion, and quadrature for coefficients, cross-checked
against ``analytic_pricing.black_scholes_call_price``. A production engine would add
Lévy models, adaptive truncation, and coefficient caching.

References (for the student reader, not exhaustive citations in code):
Fang & Oosterlee (COS method); Carr–Madan (Fourier methods). Implementation
details follow the cosine expansion of the payoff in log(S_T) with explicit
numerical integration for the payoff cosine coefficients (easy to audit).
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass
from typing import Tuple

from qhpc_cache.analytic_pricing import black_scholes_call_price


@dataclass
class FourierPricingConfig:
    """Numerical knobs for COS / Fourier experiments."""

    truncation_width_in_sigmas: float = 10.0
    num_cos_terms: int = 128
    quadrature_points_for_payoff_coeffs: int = 512


@dataclass
class FourierPricingPlaceholder:
    """Legacy configuration name kept for older imports and demos."""

    integration_limit: float = 10.0
    num_cos_terms: int = 128

    def to_fourier_config(self) -> FourierPricingConfig:
        """Map legacy ``integration_limit`` to ``truncation_width_in_sigmas``."""
        return FourierPricingConfig(
            truncation_width_in_sigmas=self.integration_limit,
            num_cos_terms=self.num_cos_terms,
        )


def black_scholes_characteristic_function_ln_spot(
    fourier_argument: complex,
    initial_spot_price: float,
    risk_free_rate: float,
    volatility: float,
    maturity_in_years: float,
) -> complex:
    """Characteristic function phi(u) = E[exp(i u ln S_T)] under risk-neutral GBM.

    ln S_T is Gaussian with mean mu and variance sigma^2 T, where
    mu = ln(S0) + (r - 0.5 sigma^2) T.
    """
    if initial_spot_price <= 0.0:
        raise ValueError("initial_spot_price must be positive.")
    if maturity_in_years < 0.0:
        raise ValueError("maturity_in_years must be non-negative.")
    if maturity_in_years == 0.0:
        return cmath.exp(1j * fourier_argument * math.log(initial_spot_price))
    mean_ln_spot = math.log(initial_spot_price) + (
        risk_free_rate - 0.5 * volatility * volatility
    ) * maturity_in_years
    variance_ln_spot = volatility * volatility * maturity_in_years
    return cmath.exp(
        1j * fourier_argument * mean_ln_spot
        - 0.5 * variance_ln_spot * fourier_argument * fourier_argument
    )


def _payoff_cosine_coefficient_trapezoid(
    term_index: int,
    interval_low: float,
    interval_high: float,
    strike_price: float,
    num_quadrature_points: int,
) -> float:
    """V_k = 2/(b-a) * integral max(e^x - K, 0) cos(k pi (x-a)/(b-a)) dx.

    Here x = ln(S_T) (natural log of terminal spot). The payoff is the call
    written on S_T = exp(x).
    """
    length = interval_high - interval_low
    if length <= 0.0:
        raise ValueError("Integration interval must have positive width.")
    omega = term_index * math.pi / length
    accum = 0.0
    for point_index in range(num_quadrature_points + 1):
        if point_index == 0 or point_index == num_quadrature_points:
            weight = 0.5
        else:
            weight = 1.0
        x = interval_low + (point_index / num_quadrature_points) * length
        intrinsic = math.exp(x) - strike_price
        payoff = intrinsic if intrinsic > 0.0 else 0.0
        accum += weight * payoff * math.cos(omega * (x - interval_low))
    integral_approx = accum * (length / num_quadrature_points)
    return (2.0 / length) * integral_approx


def cos_method_european_call_price(
    initial_spot_price: float,
    strike_price: float,
    risk_free_rate: float,
    volatility: float,
    maturity_in_years: float,
    config: FourierPricingConfig | None = None,
) -> float:
    """COS-style semi-analytic European call under GBM (auditable quadrature for V_k)."""
    if config is None:
        config = FourierPricingConfig()
    if maturity_in_years == 0.0:
        return max(initial_spot_price - strike_price, 0.0)
    mean_ln_spot = math.log(initial_spot_price) + (
        risk_free_rate - 0.5 * volatility * volatility
    ) * maturity_in_years
    std_ln_spot = volatility * math.sqrt(maturity_in_years)
    width = config.truncation_width_in_sigmas * std_ln_spot
    interval_low = mean_ln_spot - width
    interval_high = mean_ln_spot + width
    length = interval_high - interval_low

    total = 0.0
    for term_index in range(config.num_cos_terms):
        u = term_index * math.pi / length
        phi = black_scholes_characteristic_function_ln_spot(
            u,
            initial_spot_price,
            risk_free_rate,
            volatility,
            maturity_in_years,
        )
        exp_shift = cmath.exp(-1j * u * interval_low)
        coeff = _payoff_cosine_coefficient_trapezoid(
            term_index,
            interval_low,
            interval_high,
            strike_price,
            config.quadrature_points_for_payoff_coeffs,
        )
        lambda_mult = 0.5 if term_index == 0 else 1.0
        total += lambda_mult * (phi * exp_shift).real * coeff
    return math.exp(-risk_free_rate * maturity_in_years) * total


def fourier_control_variate_reference(
    initial_spot_price: float,
    strike_price: float,
    risk_free_rate: float,
    volatility: float,
    maturity_in_years: float,
) -> float:
    """Analytic Black–Scholes call price for control variate / benchmarking."""
    return black_scholes_call_price(
        initial_spot_price,
        strike_price,
        risk_free_rate,
        volatility,
        maturity_in_years,
    )


def fourier_price_placeholder(
    initial_spot_price: float,
    strike_price: float,
    risk_free_rate: float,
    volatility: float,
    maturity_in_years: float,
) -> Tuple[float, float]:
    """Return ``(cos_price, bs_reference)`` — both are real-valued benchmarks, not stubs."""
    cos_price = cos_method_european_call_price(
        initial_spot_price,
        strike_price,
        risk_free_rate,
        volatility,
        maturity_in_years,
    )
    reference = fourier_control_variate_reference(
        initial_spot_price,
        strike_price,
        risk_free_rate,
        volatility,
        maturity_in_years,
    )
    return cos_price, reference
