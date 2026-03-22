"""Minimal multi-position book for Monte Carlo present value and scenario risk.

Each line is priced with ``MonteCarloPricer`` (independent paths per line). If you
set scenario underlying levels on ``PortfolioPricingRequest``, VaR/CVaR use
**Black–Scholes repricing** at those spots vs the baseline spot (fast and
deterministic)—not the Monte Carlo distribution. That split is intentional for
undergraduate clarity: MC for PV, analytic scenarios for a transparent risk toy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from qhpc_cache.analytic_pricing import black_scholes_call_price, black_scholes_put_price
from qhpc_cache.pricing import MonteCarloPricer, MonteCarloPricingResult
from qhpc_cache.risk_metrics import (
    DistributionSummary,
    compute_conditional_value_at_risk,
    compute_profit_and_loss_distribution,
    compute_value_at_risk,
    summarize_distribution,
)


@dataclass
class OptionPosition:
    """One book line priced with Monte Carlo (payoff_name matches ``MonteCarloPricer``)."""

    position_name: str
    payoff_name: str
    quantity: float
    initial_asset_price: float
    strike_price: float
    risk_free_rate: float
    volatility: float
    time_to_maturity: float


@dataclass
class PortfolioPricingRequest:
    """Bundle of positions to price together."""

    portfolio_name: str = "portfolio"
    positions: List[OptionPosition] = field(default_factory=list)
    number_of_paths: int = 5000
    random_seed: int = 42
    scenario_underlying_prices: Optional[List[float]] = None
    baseline_underlying_price: Optional[float] = None
    risk_confidence_level: float = 0.95


@dataclass
class PortfolioPricingResult:
    """Per-line Monte Carlo results plus book-level present value and optional risk.

    ``total_estimated_value`` is the sum of (quantity × unit Monte Carlo price) across
    lines. When scenario spots are set on the request, ``value_at_risk`` and
    ``conditional_value_at_risk`` come from **analytic** repricing of those lines
    (see module docstring)—not from the Monte Carlo paths.
    """

    portfolio_name: str
    individual_position_results: List[MonteCarloPricingResult]
    total_estimated_value: float
    value_at_risk: Optional[float] = None
    conditional_value_at_risk: Optional[float] = None
    notes: str = ""


def _analytic_price_for_position(
    position: OptionPosition,
    spot_for_valuation: float,
) -> float:
    """Black–Scholes price with unchanged time to maturity (static scenario bump)."""
    if position.payoff_name == "european_call":
        return black_scholes_call_price(
            spot_for_valuation,
            position.strike_price,
            position.risk_free_rate,
            position.volatility,
            position.time_to_maturity,
        )
    if position.payoff_name == "european_put":
        return black_scholes_put_price(
            spot_for_valuation,
            position.strike_price,
            position.risk_free_rate,
            position.volatility,
            position.time_to_maturity,
        )
    raise ValueError(
        "Analytic scenario P&L supports european_call and european_put only."
    )


def _portfolio_analytic_value(
    positions: Sequence[OptionPosition],
    spot: float,
) -> float:
    total = 0.0
    for position_index in range(len(positions)):
        position = positions[position_index]
        unit_price = _analytic_price_for_position(position, spot)
        total += position.quantity * unit_price
    return total


def price_portfolio_positions(
    portfolio_pricing_request: PortfolioPricingRequest,
) -> PortfolioPricingResult:
    """Price each line with its own ``MonteCarloPricer`` (independent paths).

    If ``scenario_underlying_prices`` and ``baseline_underlying_price`` are set,
    fills ``value_at_risk`` and ``conditional_value_at_risk`` using analytic
    repricing (same convention as ``compute_portfolio_profit_and_loss``).
    """
    request = portfolio_pricing_request
    individual_results: List[MonteCarloPricingResult] = []
    total_value = 0.0
    for line_index in range(len(request.positions)):
        position = request.positions[line_index]
        pricer = MonteCarloPricer(
            S0=position.initial_asset_price,
            K=position.strike_price,
            r=position.risk_free_rate,
            sigma=position.volatility,
            T=position.time_to_maturity,
            num_paths=request.number_of_paths,
            payoff_type=position.payoff_name,
            simulation_mode="terminal",
            random_seed=request.random_seed + line_index,
        )
        result = pricer.price_option()
        total_value += position.quantity * result.estimated_price
        individual_results.append(result)

    var_out: Optional[float] = None
    cvar_out: Optional[float] = None
    notes = ""
    if (
        request.scenario_underlying_prices is not None
        and request.baseline_underlying_price is not None
    ):
        pnl = compute_portfolio_profit_and_loss(portfolio_pricing_request)
        var_out = compute_value_at_risk(pnl, request.risk_confidence_level)
        cvar_out = compute_conditional_value_at_risk(
            pnl, request.risk_confidence_level
        )
        notes = (
            "VaR/CVaR from analytic repricing at scenario spots vs baseline spot; "
            "total_estimated_value is Monte Carlo."
        )

    return PortfolioPricingResult(
        portfolio_name=request.portfolio_name,
        individual_position_results=individual_results,
        total_estimated_value=total_value,
        value_at_risk=var_out,
        conditional_value_at_risk=cvar_out,
        notes=notes,
    )


def compute_portfolio_profit_and_loss(
    portfolio_pricing_request: PortfolioPricingRequest,
    confidence_level: float = 0.95,
) -> List[float]:
    """Scenario P&L: analytic portfolio PV at each spot minus PV at baseline.

    Requires ``scenario_underlying_prices`` and ``baseline_underlying_price`` on
    the request. Lines must be ``european_call`` or ``european_put`` (Black–Scholes
    repricing).

    The ``confidence_level`` argument is reserved for symmetry with
    ``summarize_portfolio_risk`` and does not affect the P&L list.
    """
    _ = confidence_level
    request = portfolio_pricing_request
    if request.scenario_underlying_prices is None:
        raise ValueError("scenario_underlying_prices must be set on the request.")
    if request.baseline_underlying_price is None:
        raise ValueError("baseline_underlying_price must be set on the request.")
    baseline_spot = request.baseline_underlying_price
    initial_value = _portfolio_analytic_value(request.positions, baseline_spot)
    scenario_values: List[float] = []
    for scenario_index in range(len(request.scenario_underlying_prices)):
        spot = request.scenario_underlying_prices[scenario_index]
        scenario_values.append(_portfolio_analytic_value(request.positions, spot))
    return compute_profit_and_loss_distribution(initial_value, scenario_values)


@dataclass
class PortfolioRiskSummary:
    """VaR/CVaR plus simple distribution stats on portfolio P&L."""

    value_at_risk: float
    conditional_value_at_risk: float
    distribution_summary: DistributionSummary


def summarize_portfolio_risk(
    portfolio_pricing_request: PortfolioPricingRequest,
    confidence_level: float = 0.95,
) -> PortfolioRiskSummary:
    """Compute VaR, CVaR, and descriptive stats from scenario P&L on the request."""
    pnl = compute_portfolio_profit_and_loss(
        portfolio_pricing_request, confidence_level=confidence_level
    )
    var_loss = compute_value_at_risk(pnl, confidence_level)
    cvar_loss = compute_conditional_value_at_risk(pnl, confidence_level)
    dist = summarize_distribution(pnl)
    return PortfolioRiskSummary(
        value_at_risk=var_loss,
        conditional_value_at_risk=cvar_loss,
        distribution_summary=dist,
    )
