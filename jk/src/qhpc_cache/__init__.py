"""qhpc_cache: finance-valid classical Monte Carlo core + labeled quantum/circuit scaffolds."""

from qhpc_cache.analytic_pricing import (
    black_scholes_call_delta,
    black_scholes_call_price,
    black_scholes_gamma,
    black_scholes_put_price,
    black_scholes_vega,
    normal_cdf,
)
from qhpc_cache.cache_policy import (
    AIAssistedCachePolicy,
    BaseCachePolicy,
    HeuristicCachePolicy,
    LogisticCachePolicy,
    LogisticPolicyWeights,
)
from qhpc_cache.cache_store import SimpleCacheStore
from qhpc_cache.experiment_runner import (
    run_cache_policy_comparison_experiment,
    run_monte_carlo_study,
    run_payoff_comparison_experiment,
    run_portfolio_risk_experiment,
    run_quantum_mapping_comparison_experiment,
    run_repeated_pricing_experiment,
)
from qhpc_cache.fourier_placeholder import (
    FourierPricingConfig,
    FourierPricingPlaceholder,
    cos_method_european_call_price,
)
from qhpc_cache.placeholders import (
    CircuitFragmentPlaceholder,
    CircuitMetadataPlaceholder,
)
from qhpc_cache.pricing import MonteCarloPricer, MonteCarloPricingResult
from qhpc_cache.quantum_workflow import QuantumWorkflowBundle, run_quantum_mapping_workflow

__all__ = [
    "AIAssistedCachePolicy",
    "BaseCachePolicy",
    "HeuristicCachePolicy",
    "LogisticCachePolicy",
    "LogisticPolicyWeights",
    "SimpleCacheStore",
    "MonteCarloPricer",
    "MonteCarloPricingResult",
    "normal_cdf",
    "black_scholes_call_price",
    "black_scholes_put_price",
    "black_scholes_call_delta",
    "black_scholes_gamma",
    "black_scholes_vega",
    "FourierPricingPlaceholder",
    "FourierPricingConfig",
    "cos_method_european_call_price",
    "CircuitFragmentPlaceholder",
    "CircuitMetadataPlaceholder",
    "run_repeated_pricing_experiment",
    "run_monte_carlo_study",
    "run_payoff_comparison_experiment",
    "run_portfolio_risk_experiment",
    "run_cache_policy_comparison_experiment",
    "run_quantum_mapping_comparison_experiment",
    "QuantumWorkflowBundle",
    "run_quantum_mapping_workflow",
]
