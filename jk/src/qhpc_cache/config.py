"""Centralized configuration for pricing, experiments, and demos."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PricingConfig:
    """Default single-name option and Monte Carlo parameters (research-scale, not HPC)."""

    S0: float = 100.0
    K: float = 100.0
    r: float = 0.05
    sigma: float = 0.2
    T: float = 1.0
    num_paths: int = 8_000
    random_seed: Optional[int] = None


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
    base_random_seed: Optional[int] = 7


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


@dataclass
class VisualizationConfig:
    """Parameters for ``run_research_visualization_demo.py``."""

    symbols: List[str] = field(
        default_factory=lambda: ["SPY", "QQQ", "IWM", "AAPL", "MSFT",
                                 "AMZN", "GOOG", "TSLA", "JPM", "GLD"]
    )
    start_date: str = "2023-01-01"
    end_date: str = "2024-12-31"
    lookback_days: int = 504
    max_symbols_corr: int = 20
    enable_databento: bool = True
    enable_taq: bool = True
    output_root: str = "outputs/research_visualization"
    mc_paths_for_sim_comparison: int = 10_000
    mc_seed: int = 42
    rolling_vol_window: int = 21
    alpha_forward_horizon: int = 5
    alpha_quantile_buckets: int = 5


@dataclass
class QMCSimulationConfig:
    """Parameters for the QMC simulation harness."""

    budget_minutes: float = 20.0
    gan_epochs: int = 30
    gan_num_days: int = 500
    gan_num_assets: int = 100
    portfolio_size: int = 500
    convergence_path_counts: List[int] = field(
        default_factory=lambda: [1_000, 5_000, 10_000, 50_000, 100_000, 500_000]
    )
    convergence_contracts: int = 8
    live_dashboard: bool = True
    output_dir: str = "outputs/qmc_simulation"
    seed: int = 42
    trace_full_mode: bool = False
    enforce_budget: bool = True
    trace_window_size: int = 64
    trace_stride: int = 16
    emit_visuals: bool = True
    max_trace_rows: Optional[int] = None
    max_phase_contracts: Optional[int] = None
    max_phase_convergence_contracts: Optional[int] = None
    max_pricings_total: Optional[int] = None
    engine_allowlist: Optional[List[str]] = None
    trace_output_subdir: str = "trace"
    # similarity
    enable_similarity_matching: bool = True
    similarity_method: str = "hybrid"
    similarity_threshold: float = 0.92
    similarity_max_candidates: int = 32
    similarity_signature_dims: int = 8
    similarity_bucket_bits: int = 12
    # PMU
    enable_pmu: bool = False
    pmu_backend: str = "auto"
    pmu_sample_scope: str = "engine_call"
    pmu_collect_memory: bool = True
    pmu_collect_cycles: bool = True
    pmu_collect_instructions: bool = True
    pmu_collect_cache_refs: bool = True
    pmu_collect_cache_misses: bool = True
    pmu_collect_branches: bool = False
    pmu_collect_page_faults: bool = False


def get_qmc_config() -> "QMCSimulationConfig":
    return QMCSimulationConfig()


def get_visualization_config() -> VisualizationConfig:
    """Return the default visualization configuration."""
    return VisualizationConfig()


def get_default_config() -> PricingConfig:
    """Return the default pricing configuration."""
    return PricingConfig()


def get_demo_run_defaults() -> DemoRunDefaults:
    """Return defaults for the canonical ``run_demo.py`` walkthrough."""
    return DemoRunDefaults()
