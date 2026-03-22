"""Black–Scholes–Merton analytic pricing and Greeks (European vanilla on a non-dividend stock).

All formulas assume the underlying follows GBM under the risk-neutral measure,
no dividends, constant volatility and rate, and European exercise. Greeks are
**per one unit** of spot (not scaled by contract quantity).
"""

from __future__ import annotations

import math
from typing import Tuple


def normal_cdf(x: float) -> float:
    """Standard normal cumulative distribution Phi(x), using math.erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _d1_d2(
    initial_spot_price: float,
    strike_price: float,
    risk_free_rate: float,
    volatility: float,
    maturity_in_years: float,
) -> Tuple[float, float]:
    if initial_spot_price <= 0.0 or strike_price <= 0.0:
        raise ValueError("Spot and strike must be positive for Black–Scholes.")
    if maturity_in_years < 0.0:
        raise ValueError("maturity_in_years must be non-negative.")
    if maturity_in_years == 0.0:
        # Not used directly at T=0 in price formulas; callers should short-circuit.
        raise ValueError("Use intrinsic value at maturity zero instead of d1/d2.")
    if volatility <= 0.0:
        raise ValueError("volatility must be positive.")
    vol_sqrt_t = volatility * math.sqrt(maturity_in_years)
    d1 = (
        math.log(initial_spot_price / strike_price)
        + (risk_free_rate + 0.5 * volatility * volatility) * maturity_in_years
    ) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    return d1, d2


def black_scholes_call_price(
    initial_spot_price: float,
    strike_price: float,
    risk_free_rate: float,
    volatility: float,
    maturity_in_years: float,
) -> float:
    """Black–Scholes European call price (undiscounted payoff expectation under Q)."""
    if maturity_in_years == 0.0:
        return max(initial_spot_price - strike_price, 0.0)
    d1, d2 = _d1_d2(
        initial_spot_price, strike_price, risk_free_rate, volatility, maturity_in_years
    )
    discount = math.exp(-risk_free_rate * maturity_in_years)
    return initial_spot_price * normal_cdf(d1) - strike_price * discount * normal_cdf(d2)


def black_scholes_put_price(
    initial_spot_price: float,
    strike_price: float,
    risk_free_rate: float,
    volatility: float,
    maturity_in_years: float,
) -> float:
    """European put via put–call parity or direct formula."""
    if maturity_in_years == 0.0:
        return max(strike_price - initial_spot_price, 0.0)
    d1, d2 = _d1_d2(
        initial_spot_price, strike_price, risk_free_rate, volatility, maturity_in_years
    )
    discount = math.exp(-risk_free_rate * maturity_in_years)
    return (
        strike_price * discount * normal_cdf(-d2)
        - initial_spot_price * normal_cdf(-d1)
    )


def black_scholes_call_delta(
    initial_spot_price: float,
    strike_price: float,
    risk_free_rate: float,
    volatility: float,
    maturity_in_years: float,
) -> float:
    """Delta = dV/dS for a call: Phi(d1)."""
    if maturity_in_years == 0.0:
        return 1.0 if initial_spot_price > strike_price else 0.0
    d1, d2 = _d1_d2(
        initial_spot_price, strike_price, risk_free_rate, volatility, maturity_in_years
    )
    return normal_cdf(d1)


def black_scholes_put_delta(
    initial_spot_price: float,
    strike_price: float,
    risk_free_rate: float,
    volatility: float,
    maturity_in_years: float,
) -> float:
    """Delta for a put: Phi(d1) - 1."""
    if maturity_in_years == 0.0:
        return -1.0 if initial_spot_price < strike_price else 0.0
    return black_scholes_call_delta(
        initial_spot_price,
        strike_price,
        risk_free_rate,
        volatility,
        maturity_in_years,
    ) - 1.0


def black_scholes_gamma(
    initial_spot_price: float,
    strike_price: float,
    risk_free_rate: float,
    volatility: float,
    maturity_in_years: float,
) -> float:
    """Gamma is the same for calls and puts under Black–Scholes."""
    if maturity_in_years == 0.0:
        return 0.0
    d1, d2 = _d1_d2(
        initial_spot_price, strike_price, risk_free_rate, volatility, maturity_in_years
    )
    denominator = (
        initial_spot_price * volatility * math.sqrt(maturity_in_years)
    )
    return math.exp(-0.5 * d1 * d1) / (math.sqrt(2.0 * math.pi) * denominator)


def black_scholes_vega(
    initial_spot_price: float,
    strike_price: float,
    risk_free_rate: float,
    volatility: float,
    maturity_in_years: float,
) -> float:
    """Vega per 1.0 change in sigma (not per 1% vol point)."""
    if maturity_in_years == 0.0:
        return 0.0
    d1, d2 = _d1_d2(
        initial_spot_price, strike_price, risk_free_rate, volatility, maturity_in_years
    )
    return initial_spot_price * math.sqrt(maturity_in_years) * math.exp(
        -0.5 * d1 * d1
    ) / math.sqrt(2.0 * math.pi)


def black_scholes_theta_call(
    initial_spot_price: float,
    strike_price: float,
    risk_free_rate: float,
    volatility: float,
    maturity_in_years: float,
) -> float:
    """Theta = dV/dt (per year, calendar time)."""
    if maturity_in_years == 0.0:
        return 0.0
    d1, d2 = _d1_d2(
        initial_spot_price, strike_price, risk_free_rate, volatility, maturity_in_years
    )
    term1 = -(
        initial_spot_price
        * math.exp(-0.5 * d1 * d1)
        * volatility
        / (2.0 * math.sqrt(2.0 * math.pi * maturity_in_years))
    )
    term2 = -risk_free_rate * strike_price * math.exp(
        -risk_free_rate * maturity_in_years
    ) * normal_cdf(d2)
    return term1 + term2


def black_scholes_theta_put(
    initial_spot_price: float,
    strike_price: float,
    risk_free_rate: float,
    volatility: float,
    maturity_in_years: float,
) -> float:
    """Theta for put (per year)."""
    if maturity_in_years == 0.0:
        return 0.0
    d1, d2 = _d1_d2(
        initial_spot_price, strike_price, risk_free_rate, volatility, maturity_in_years
    )
    term1 = -(
        initial_spot_price
        * math.exp(-0.5 * d1 * d1)
        * volatility
        / (2.0 * math.sqrt(2.0 * math.pi * maturity_in_years))
    )
    term2 = risk_free_rate * strike_price * math.exp(
        -risk_free_rate * maturity_in_years
    ) * normal_cdf(-d2)
    return term1 + term2


def black_scholes_rho_call(
    initial_spot_price: float,
    strike_price: float,
    risk_free_rate: float,
    volatility: float,
    maturity_in_years: float,
) -> float:
    """Rho per 1.0 change in r (continuous rate)."""
    if maturity_in_years == 0.0:
        return 0.0
    d1, d2 = _d1_d2(
        initial_spot_price, strike_price, risk_free_rate, volatility, maturity_in_years
    )
    return (
        strike_price
        * maturity_in_years
        * math.exp(-risk_free_rate * maturity_in_years)
        * normal_cdf(d2)
    )


def black_scholes_rho_put(
    initial_spot_price: float,
    strike_price: float,
    risk_free_rate: float,
    volatility: float,
    maturity_in_years: float,
) -> float:
    """Rho for put."""
    if maturity_in_years == 0.0:
        return 0.0
    d1, d2 = _d1_d2(
        initial_spot_price, strike_price, risk_free_rate, volatility, maturity_in_years
    )
    return (
        -strike_price
        * maturity_in_years
        * math.exp(-risk_free_rate * maturity_in_years)
        * normal_cdf(-d2)
    )
