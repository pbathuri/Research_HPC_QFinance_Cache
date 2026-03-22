# Current state audit — qhpc_cache (jk/)

**Historical research substrate (current phase):** The repo now includes a **data layer** (Databento + local TAQ/kdb hooks + registry), **broad-universe and event-book builders**, **rates placeholders**, **historical returns/risk**, **alpha feature + evaluation modules**, **knowledge cache**, **workflow events + Pixel bridge**, and **setup scripts**. See `docs/phase_master_plan.md` for constraints (24 GB RAM, 50 GB disk, 2 h runtime target) and build order.

Snapshot of what the repository **does today** after the classical finance baseline phase, what remains placeholder, and what is explicitly deferred.

## Repository layout

- **Package**: `src/qhpc_cache/` (editable install: `pip install -e .` from `jk/`).
- **Entry points**: `run_demo.py`; optional tooling under `tools/`.
- **Tests**: `tests/` using **unittest** only.

## What works (implemented baseline)

| Area | Module | Notes |
|------|--------|--------|
| GBM terminal and path simulation | `market_models.py` | Terminal law, paths from seed or explicit normal increments, batch scenarios. |
| Payoffs | `payoffs.py` | European, Asian (path), digital with configurable `payout_amount`. |
| Black–Scholes + Greeks | `analytic_pricing.py` | Prices and standard Greeks for teaching and benchmarks. |
| Monte Carlo pricer | `pricing.py` | Terminal vs path mode, antithetic variates, optional control variate (vanilla), optional BS reference, `MonteCarloPricingResult`. |
| Variance reduction helpers | `variance_reduction.py` | Antithetic pairs, SE from samples, CIs, control-variate adjustment. |
| Risk metrics | `risk_metrics.py` | P&L from scenario portfolio values, sample VaR/CVaR, summaries. |
| Portfolio | `portfolio.py` | Positions, batch MC pricing, optional scenario-based VaR/CVaR on request. |
| Cache + policy | `cache_store.py`, `cache_policy.py`, `feature_builder.py` | Simple feature-keyed store; policies gate reuse; not a research focus this phase. |
| Experiments | `experiment_runner.py` | Repeated pricing, payoff comparison, portfolio risk, cache comparison, quantum mapping bundle helper. |
| Demo | `run_demo.py` | Finite-size runs; classical pricing, risk, modest cache/Fourier/quantum placeholders. |

## Placeholder or teaching stubs (not production finance)

| Module | Notes |
|--------|--------|
| `placeholders.py` | Structural stubs for future circuit fragments / metadata. |
| `quantum_mapping.py`, `quantum_workflow.py` | Descriptor and workflow **placeholders**; no device execution. |
| `circuit_cache.py`, `circuit_similarity.py` | Lightweight similarity / cache experiments; not validated for real quantum workloads. |
| `fourier_placeholder.py` | COS-style bridge for comparison; parameters are illustrative, not a production pricer. |
| `AIAssistedCachePolicy` | Hand-tuned or injectable scorer; not a trained markets model. |

## Mathematically honest but limited (by design)

- **Single-factor GBM**, flat rates, no discrete dividends or early exercise (Americans).
- **VaR/CVaR** are **sample quantile** methods on provided scenarios, not parametric or regulatory internal models.
- **Portfolio MC** uses **independent** paths per line (correlation across names not modeled in simulation).

## Not finance-industry full stack (intentional)

- No market data feeds, calibration, or curve bootstrapping.
- No xVA, funding, or collateral.
- No enterprise risk engines or reporting hierarchies.

## Out of scope for this phase (see `next_phase_scope.md`)

- HPC: CUDA, MPI, OpenMP, Slurm, Big Red 200–style schedulers.
- Real quantum backends and runtime integration.
- RL cache policies, GNNs, large agent frameworks.

## Demo / workflow

- **`run_demo.py`** is the canonical, undergraduate-oriented walkthrough (classical baseline + pointers to extensions). Numeric knobs for the demo live in **`config.DemoRunDefaults`** (`get_demo_run_defaults()`), not scattered as magic numbers.
- **`experiment_configs`** defaults use **thousands** of paths and a few replications so laptop runs stay quick; raise counts for publication-style standard errors.
- **`monte_carlo_cache_baseline.py`** is a legacy single-file European sketch; new work should use `qhpc_cache` and `run_demo.py`.
- Tests: `PYTHONPATH=src python3 -m unittest discover -s tests -v` from `jk/`.

This audit complements `docs/finance_baseline_architecture.md` and `docs/next_phase_scope.md`.
