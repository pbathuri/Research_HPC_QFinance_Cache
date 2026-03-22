# Architecture overview

For the **classical finance baseline** only (GBM → payoffs → analytic → Monte Carlo → variance → risk → portfolio), read **`finance_baseline_architecture.md`** first. This document summarizes the **entire** research scaffold, including Fourier, quantum-shaped types, circuit cache, and experiments.

## Layering (research workflow)

1. **Market + payoffs** — `market_models.py`, `payoffs.py`  
   GBM simulation and explicit payoff formulas (terminal vs path).

2. **Analytic reference** — `analytic_pricing.py`  
   Black–Scholes prices and Greeks (European vanilla, no dividends).

3. **Monte Carlo engine** — `pricing.py`, `variance_reduction.py`  
   `MonteCarloPricer` produces `MonteCarloPricingResult` with optional antithetic sampling, control variate (terminal spot), and analytic comparison.

4. **Risk + portfolio** — `risk_metrics.py`, `portfolio.py`  
   Sample VaR/CVaR and small multi-line books.

5. **Semi-analytic bridge** — `fourier_placeholder.py`  
   Characteristic function of log-spot and COS-style pricing with auditable quadrature for cosine coefficients; matches Black–Scholes for ATM checks.

6. **Quantum-shaped planning** — `quantum_mapping.py`, `quantum_workflow.py`  
   Dataclasses that describe finance problems as estimation/circuit tasks **without** executing quantum code.

7. **Circuit cache + similarity** — `circuit_cache.py`, `circuit_similarity.py`  
   Exact keys over structured requests; weighted, explainable similarity.

8. **Policies + classical cache** — `cache_policy.py`, `cache_policy_features.py`, `cache_store.py`  
   Heuristic, logistic, and AI-placeholder policies; JSON-keyed `SimpleCacheStore` for Monte Carlo result reuse.

9. **Experiments + reporting** — `experiment_configs.py`, `research_scenarios.py`, `experiment_runner.py`, `reporting.py`  
   Typed configs, scenario builders, structured experiment outputs, text/markdown reports.

## Dependency boundary

- **Core** (`src/qhpc_cache`): standard library only.
- **Optional** (`tools/research_agent/`): small doc-index script, not imported by core.
- **Optional** (`tools/codex_dev/`): Codex CLI wrapper (stdlib) and LangChain hook when `pip install -e ".[ai-workflow]"` is used; never imported by core.

## Extension points

- Swap `MonteCarloPricer` payoff dispatch for new instruments.
- Add backend-specific adapters under a future `integrations/` package (not required now).
- Train an external model for `AIAssistedCachePolicy` without changing pricing math.
