"""Batch experiment helpers — return structured dicts (no printing).

Suitable for notebooks and small research scripts. Path counts come from the
passed configs; keep them modest for interactive use.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable, Dict, List, Optional, Sequence

from qhpc_cache.cache_policy import BaseCachePolicy
from qhpc_cache.cache_store import SimpleCacheStore
from qhpc_cache.experiment_configs import (
    CacheExperimentConfig,
    MonteCarloExperimentConfig,
    PortfolioExperimentConfig,
)
from qhpc_cache.portfolio import (
    OptionPosition,
    PortfolioPricingRequest,
    compute_portfolio_profit_and_loss,
    price_portfolio_positions,
    summarize_portfolio_risk,
)
from qhpc_cache.pricing import MonteCarloPricer
from qhpc_cache.quantum_workflow import QuantumWorkflowBundle, run_quantum_mapping_workflow


def run_repeated_pricing_experiment(
    pricer_factory: Callable[[], MonteCarloPricer],
    num_trials: int,
) -> Dict[str, Any]:
    """Run ``price_option`` repeatedly; return means and cache statistics."""
    pricer = pricer_factory()
    prices: List[float] = []
    variances: List[float] = []
    for trial_index in range(num_trials):
        result = pricer.price_option()
        prices.append(result.estimated_price)
        variances.append(result.payoff_variance)
    average_price = sum(prices) / float(num_trials)
    average_variance = sum(variances) / float(num_trials)
    if pricer.cache_store is not None:
        cache_stats = pricer.cache_store.stats()
        cache_hits = cache_stats["hits"]
        cache_misses = cache_stats["misses"]
        cache_entries = cache_stats["entries"]
    else:
        cache_hits = cache_misses = cache_entries = 0
    return {
        "num_trials": num_trials,
        "average_price": average_price,
        "average_variance": average_variance,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "cache_entries": cache_entries,
    }


def run_payoff_comparison_experiment(
    payoff_names: Sequence[str],
    initial_spot_price: float = 100.0,
    strike_price: float = 100.0,
    risk_free_rate: float = 0.05,
    volatility: float = 0.2,
    time_to_maturity: float = 1.0,
    number_of_paths: int = 4000,
    random_seed: Optional[int] = 101,
) -> Dict[str, Any]:
    """Price several payoff types with shared market parameters; return structured rows."""
    per_payoff: List[Dict[str, Any]] = []
    for index in range(len(payoff_names)):
        name = payoff_names[index]
        simulation_mode = "path" if name in ("asian_call", "asian_put") else "terminal"
        seed = (
            None if random_seed is None else int(random_seed) + index
        )
        pricer = MonteCarloPricer(
            S0=initial_spot_price,
            K=strike_price,
            r=risk_free_rate,
            sigma=volatility,
            T=time_to_maturity,
            num_paths=number_of_paths,
            payoff_type=name,
            simulation_mode=simulation_mode,
            num_time_steps=12,
            compare_analytic_black_scholes=name
            in ("european_call", "european_put"),
            random_seed=seed,
        )
        result = pricer.price_option()
        per_payoff.append(
            {
                "payoff_name": result.payoff_name,
                "estimated_price": result.estimated_price,
                "standard_error": result.standard_error,
                "analytic_reference_price": result.analytic_reference_price,
                "used_path_simulation": result.used_path_simulation,
            }
        )
    return {
        "per_payoff": per_payoff,
        "number_of_paths": number_of_paths,
        "initial_spot_price": initial_spot_price,
        "strike_price": strike_price,
    }


def run_monte_carlo_study(
    config: MonteCarloExperimentConfig,
) -> Dict[str, Any]:
    """Repeated independent batches with controlled seed offsets."""
    estimates: List[float] = []
    analytic_refs: List[Optional[float]] = []
    for rep_index in range(config.num_replications):
        seed = (
            None if config.random_seed is None else config.random_seed + rep_index
        )
        pricer = MonteCarloPricer(
            S0=config.initial_spot_price,
            K=config.strike_price,
            r=config.risk_free_rate,
            sigma=config.volatility,
            T=config.maturity_in_years,
            num_paths=config.num_paths,
            payoff_type=config.payoff_type,
            simulation_mode=config.simulation_mode,
            use_antithetic_variates=config.use_antithetic_variates,
            use_black_scholes_control_variate=config.use_black_scholes_control_variate,
            compare_analytic_black_scholes=config.compare_analytic_black_scholes,
            random_seed=seed,
        )
        result = pricer.price_option()
        estimates.append(result.estimated_price)
        analytic_refs.append(result.analytic_reference_price)
    mean_estimate = sum(estimates) / float(len(estimates))
    return {
        "mean_estimate": mean_estimate,
        "replication_estimates": estimates,
        "analytic_reference_per_run": analytic_refs,
        "config": asdict(config),
    }


def run_portfolio_risk_experiment(
    config: PortfolioExperimentConfig,
    positions: List[OptionPosition],
    portfolio_name: str = "experiment_portfolio",
) -> Dict[str, Any]:
    """Price book and compute VaR/CVaR on analytic scenario P&L."""
    request = PortfolioPricingRequest(
        portfolio_name=portfolio_name,
        positions=positions,
        number_of_paths=config.num_paths_per_position,
        random_seed=config.random_seed,
        scenario_underlying_prices=list(config.scenario_spots),
        baseline_underlying_price=config.baseline_spot,
        risk_confidence_level=config.confidence_level,
    )
    pricing_result = price_portfolio_positions(request)
    pnl = compute_portfolio_profit_and_loss(request)
    risk = summarize_portfolio_risk(
        request, confidence_level=config.confidence_level
    )
    return {
        "portfolio_name": pricing_result.portfolio_name,
        "total_estimated_value": pricing_result.total_estimated_value,
        "value_at_risk": risk.value_at_risk,
        "conditional_value_at_risk": risk.conditional_value_at_risk,
        "pnl_samples": pnl,
        "config": asdict(config),
    }


def run_cache_policy_comparison_experiment(
    cache_config: CacheExperimentConfig,
    policies: Dict[str, BaseCachePolicy],
) -> Dict[str, Any]:
    """Simulate repeated cache lookups mirroring the pricer's decide+has pattern."""
    results: Dict[str, Any] = {}
    for policy_name, policy in policies.items():
        store = SimpleCacheStore()
        hits = 0
        features = dict(cache_config.base_features)
        for request_index in range(cache_config.num_requests):
            if policy.decide(features) and store.has(features):
                store.get(features)
                hits += 1
            else:
                store.put(features, {"mean": 1.0, "variance": 0.01})
        results[policy_name] = {
            "cache_hits": hits,
            "stats": store.stats(),
            "policy_label": policy_name,
        }
    return {"per_policy": results, "config": asdict(cache_config)}


def run_quantum_mapping_comparison_experiment(
    pricers: List[MonteCarloPricer],
) -> Dict[str, Any]:
    """Build mapping bundles for several pricers (e.g. different payoffs)."""
    bundles: List[QuantumWorkflowBundle] = []
    for pricer_index in range(len(pricers)):
        bundle = run_quantum_mapping_workflow(
            pricers[pricer_index],
            request_identifier=f"compare-{pricer_index}",
        )
        bundles.append(bundle)
    return {
        "bundles": bundles,
        "finance_keys": [bundle.finance_problem for bundle in bundles],
    }
