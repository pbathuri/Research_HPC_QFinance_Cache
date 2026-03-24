# Portfolio Risk Workloads (Canonical)

Owner module:

- `src/qhpc_cache/portfolio_risk_workloads.py`

Existing canonical risk modules reused:

- `src/qhpc_cache/historical_risk.py`
- `src/qhpc_cache/risk_metrics.py`
- `src/qhpc_cache/portfolio.py`

## Locked workload layers

Layer A: historical risk over broad universes

- return-based risk calculations
- historical VaR
- historical CVaR
- rolling volatility / drawdown-aware summaries

Layer B: portfolio-slice scenario workflows

- deterministic slice families
- repeated scenario recomputation
- repeated weighting / aggregation structures

## Scenario policy

Interpretable scenario families:

- `baseline_historical`
- `event_conditioned`
- `volatility_stress`
- `rates_shift_aware`
- `broad_market_drawdown`

## Canonical APIs

Historical layer:

- `build_historical_risk_panel(...)`
- `compute_large_universe_historical_var(...)`
- `compute_large_universe_historical_cvar(...)`
- `summarize_large_universe_risk(...)`
- `export_large_universe_risk_outputs(...)`

Slice/scenario layer:

- `build_portfolio_slice(...)`
- `build_portfolio_slice_family(...)`
- `run_portfolio_scenario_recomputation(...)`
- `compute_portfolio_slice_var(...)`
- `compute_portfolio_slice_cvar(...)`
- `summarize_portfolio_slice_risk(...)`
- `export_portfolio_slice_outputs(...)`

Comparison layer:

- `compare_large_universe_vs_portfolio_slice_risk(...)`
- `compare_var_vs_cvar_structures(...)`
- `compare_scenario_families(...)`
- `summarize_risk_recomputation_patterns(...)`
- `summarize_risk_reuse_proxies(...)`
- `rank_risk_workloads_for_cache_study_value(...)`

Bundle:

- `run_portfolio_risk_workload_bundle(...)`
- `export_portfolio_risk_workload_bundle(...)`

## Primary outputs (CSV/JSON first)

CSV:

- `portfolio_risk_workload_manifest.csv`
- `historical_risk_summary.csv`
- `historical_var_cvar_summary.csv`
- `portfolio_slice_summary.csv`
- `portfolio_scenario_summary.csv`
- `portfolio_risk_timing_summary.csv`
- `portfolio_risk_reuse_proxy_summary.csv`
- `portfolio_risk_rankings.csv`

JSON:

- `portfolio_risk_workload_manifest.json`
- `portfolio_slice_manifest.json`
- `portfolio_risk_comparison_manifest.json`

## Secondary outputs

Markdown:

- `portfolio_risk_summary.md`
- `portfolio_scenario_summary.md`
- `portfolio_risk_rankings_summary.md`

Plots:

- VaR / CVaR comparison
- large-universe vs slice comparison
- scenario family comparison
- risk timing comparison
- risk workload rankings
- recomputation / reuse proxy comparison

## Mac vs HPC discipline

This layer is Mac-executable and includes scope degradation hooks with explicit deferred-workload notes.
PMU/x86 metrics remain deferred to later HPC phases.
