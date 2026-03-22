# Finance baseline architecture

This document describes how the classical layers fit together and how they prepare the repository for later **quantum mapping** and **cache-policy** research.

## Layers (bottom to top)

1. **Market model layer** (`market_models.py`)  
   Risk-neutral GBM for spot (terminal draws and discrete paths). Produces scenarios used everywhere above. Extension point: swap in other diffusions or jump models while keeping payoff interfaces stable.

2. **Payoff layer** (`payoffs.py`)  
   Maps scenarios to undiscounted cashflows. Terminal payoffs (European, digital) vs path payoffs (Asian) are separated in naming and docstrings. Extension point: barriers, lookbacks, or discrete dividends without changing the pricer’s outer loop shape.

3. **Analytic pricing layer** (`analytic_pricing.py`)  
   Closed-form Black–Scholes prices and Greeks for sanity checks, teaching, and control-variate ideas. The **Fourier/COS module** (`fourier_placeholder.py`) is a concrete semi-analytic benchmark against the same BS value—not an empty stub despite the filename.

4. **Monte Carlo pricing layer** (`pricing.py`)  
   Combines models + payoffs + discounting; optional antithetic sampling, control variate on terminal spot for vanillas, optional BS reference price. Emits `MonteCarloPricingResult`. Extension point: **quantum estimation** can target the same payoff expectation; **cache** can store or short-circuit repeated estimates keyed by features.

5. **Variance reduction layer** (`variance_reduction.py`)  
   Reusable statistics: antithetic pairs, standard error from samples, CIs, control-variate adjustment. Extension point: importance sampling or other estimators without pulling in heavy stats stacks.

6. **Risk metrics layer** (`risk_metrics.py`)  
   Sample-based P&L, VaR, CVaR, simple distribution summaries. Extension point: richer copula or multi-factor scenarios later.

7. **Portfolio layer** (`portfolio.py`)  
   Bundles multiple `OptionPosition` lines, runs per-line MC (independent paths), aggregates PV, and can attach scenario-based VaR/CVaR when scenario spots are provided. Extension point: **portfolio-aware cache policies** (e.g. reuse across correlated legs) can use the same request/result shapes.

## Quantum mapping and cache policy (future)

- **Quantum mapping** should consume stable descriptors of the finance problem (payoff name, simulation mode, rough resource counts) and remain independent of whether the price came from classical MC or a quantum estimator. The classical baseline defines the **target expectation** and reporting shape (`MonteCarloPricingResult`).
- **Cache policy** should treat pricing features (see `feature_builder.py`) as hints, not as the definition of correctness; the baseline pricer remains the reference when the cache misses.

## Out of scope for this baseline phase

HPC runtimes, distributed execution, real quantum backends, and advanced ML-driven policies—see `next_phase_scope.md`.

## Hands-on entry point

After `pip install -e .` from `jk/`, run `python3 run_demo.py` for the canonical walkthrough. Demo path counts and seeds are centralized in `config.DemoRunDefaults` (`get_demo_run_defaults()`).
