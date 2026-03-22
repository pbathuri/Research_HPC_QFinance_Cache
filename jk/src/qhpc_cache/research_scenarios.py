"""Small scenario builders that keep notebooks and demos short."""

from __future__ import annotations

from typing import List, Tuple

from qhpc_cache.experiment_configs import (
    CacheExperimentConfig,
    MonteCarloExperimentConfig,
    PortfolioExperimentConfig,
)
from qhpc_cache.portfolio import OptionPosition, PortfolioPricingRequest
from qhpc_cache.pricing import MonteCarloPricer
from qhpc_cache.quantum_workflow import QuantumWorkflowBundle, run_quantum_mapping_workflow


def build_vanilla_option_scenario(
    label: str = "atm_call",
) -> Tuple[MonteCarloExperimentConfig, MonteCarloPricer]:
    """ATM European call baseline."""
    cfg = MonteCarloExperimentConfig(
        payoff_type="european_call",
        compare_analytic_black_scholes=True,
    )
    pricer = MonteCarloPricer(
        S0=cfg.initial_spot_price,
        K=cfg.strike_price,
        r=cfg.risk_free_rate,
        sigma=cfg.volatility,
        T=cfg.maturity_in_years,
        num_paths=cfg.num_paths,
        payoff_type=cfg.payoff_type,
        compare_analytic_black_scholes=cfg.compare_analytic_black_scholes,
        random_seed=cfg.random_seed,
    )
    return cfg, pricer


def build_portfolio_mix_scenario() -> PortfolioPricingRequest:
    """Two-line book: long call, long put (different strikes)."""
    positions = [
        OptionPosition(
            position_name="call_leg",
            payoff_name="european_call",
            quantity=1.0,
            initial_asset_price=100.0,
            strike_price=105.0,
            risk_free_rate=0.05,
            volatility=0.22,
            time_to_maturity=1.0,
        ),
        OptionPosition(
            position_name="put_leg",
            payoff_name="european_put",
            quantity=2.0,
            initial_asset_price=100.0,
            strike_price=95.0,
            risk_free_rate=0.05,
            volatility=0.22,
            time_to_maturity=1.0,
        ),
    ]
    return PortfolioPricingRequest(
        portfolio_name="research_mix",
        positions=positions,
        number_of_paths=2_500,
    )


def build_cache_stress_scenario() -> CacheExperimentConfig:
    """Several identical synthetic queries to exercise cache hit/miss accounting."""
    return CacheExperimentConfig(
        num_requests=6,
        base_features={
            "instrument_type": "european_call",
            "num_paths": 3_000,
            "volatility": 0.18,
            "maturity": 0.75,
        },
    )


def build_quantum_mapping_scenario() -> QuantumWorkflowBundle:
    """Quantum planning objects for a representative pricer configuration."""
    _, pricer = build_vanilla_option_scenario()
    return run_quantum_mapping_workflow(pricer, request_identifier="scenario-qmci")
