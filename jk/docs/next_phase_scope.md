# Next phase scope (classical finance baseline)

## What this phase implements

- **Market models** (`market_models.py`): GBM terminal draws, paths from RNG or explicit normal increments, batch scenario generators with reproducible seeds.
- **Payoffs** (`payoffs.py`): European, Asian, and digital payoffs with clear terminal vs path distinction; digital notionals via `payout_amount`.
- **Analytic layer** (`analytic_pricing.py`): Black–Scholes prices and standard Greeks (unchanged role; formulas remain the reference).
- **Variance reduction** (`variance_reduction.py`): Antithetic normal pairs, standard error from raw samples, Gaussian confidence intervals, control-variate adjustment with explicit formulas.
- **Monte Carlo pricing** (`pricing.py`): Multiple payoffs, terminal vs path simulation, antithetic variates, optional BS control variate and analytic comparison, structured `MonteCarloPricingResult`, light cache hooks.
- **Risk metrics** (`risk_metrics.py`): P&L from scenario portfolio values, sample VaR/CVaR, distribution summaries.
- **Portfolio** (`portfolio.py`): Small dataclasses and helpers for multi-leg pricing and optional scenario-based risk.
- **Experiments** (`experiment_runner.py`): Repeat pricing, payoff comparison, portfolio risk harnesses returning structured data (not print-only).
- **Config & demo** (`config.py`, `run_demo.py`): Pricing defaults, `DemoRunDefaults` for the canonical demo, and `run_demo.py` as the finite-time walkthrough.
- **Tests**: `unittest` coverage for the above.
- **Docs**: This file, `current_state_audit.md`, `finance_baseline_architecture.md`, README updates.

## What this phase intentionally does not implement

- CUDA, MPI, OpenMP, Slurm, cluster schedulers, distributed MC.
- Real quantum hardware or runtime stacks (Qiskit/Cirq execution on devices).
- RL cache policies, graph neural networks, large agent frameworks.
- Production trading, live data feeds, or regulatory reporting.

## Why this phase comes before quantum mapping and advanced caching

Quantum mapping and cache-policy research need a **trustworthy classical layer**: honest simulation, recognizable risk statistics, and stable experiment entry points. This phase makes that layer explicit and testable so later work can treat “quantum workflow” and “cache decision” as **add-ons** on top of validated finance outputs rather than mixed with an unclear baseline.
