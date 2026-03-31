"""qhpc_cache: Quantum Monte Carlo simulation, cache research, and GAN data generation."""

from __future__ import annotations

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
    get_experiment_ladder,
    run_cache_policy_comparison_experiment,
    run_canonical_exact_match_cache_experiment,
    run_monte_carlo_study,
    run_local_research_sweep,
    run_payoff_comparison_experiment,
    run_portfolio_risk_experiment,
    run_quantum_mapping_comparison_experiment,
    run_repeated_pricing_experiment,
    run_seeded_repeated_monte_carlo_family_experiment,
    run_similarity_cache_replay_experiment,
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
    "run_seeded_repeated_monte_carlo_family_experiment",
    "run_canonical_exact_match_cache_experiment",
    "get_experiment_ladder",
    "run_monte_carlo_study",
    "run_local_research_sweep",
    "run_payoff_comparison_experiment",
    "run_portfolio_risk_experiment",
    "run_cache_policy_comparison_experiment",
    "run_similarity_cache_replay_experiment",
    "run_quantum_mapping_comparison_experiment",
    "QuantumWorkflowBundle",
    "run_quantum_mapping_workflow",
    "build_template_bank",
    "generate_repeated_workload_requests",
    "run_repeated_workload_study",
    "list_output_runs",
    "resolve_latest_output_run",
    "load_latest_run_manifest",
    "find_latest_qmc_artifacts",
    "write_latest_run_forensics_summary",
]


def __getattr__(name: str):
    """Lazy-load heavier optional helpers to keep base package import lean."""
    if name in {
        "build_template_bank",
        "generate_repeated_workload_requests",
        "run_repeated_workload_study",
    }:
        from qhpc_cache import repeated_workload_study as _rws

        mapping = {
            "build_template_bank": _rws.build_template_bank,
            "generate_repeated_workload_requests": _rws.generate_repeated_workload_requests,
            "run_repeated_workload_study": _rws.run_repeated_workload_study,
        }
        return mapping[name]
    if name in {
        "find_latest_qmc_artifacts",
        "list_output_runs",
        "load_latest_run_manifest",
        "resolve_latest_output_run",
        "write_latest_run_forensics_summary",
    }:
        from qhpc_cache import run_artifacts as _ra

        mapping = {
            "find_latest_qmc_artifacts": _ra.find_latest_qmc_artifacts,
            "list_output_runs": _ra.list_output_runs,
            "load_latest_run_manifest": _ra.load_latest_run_manifest,
            "resolve_latest_output_run": _ra.resolve_latest_output_run,
            "write_latest_run_forensics_summary": _ra.write_latest_run_forensics_summary,
        }
        return mapping[name]
    raise AttributeError(f"module 'qhpc_cache' has no attribute '{name}'")
