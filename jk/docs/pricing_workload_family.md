# Option-Pricing Workload Family (Canonical)

Owner module:

- `src/qhpc_cache/pricing_workloads.py`

Reused pricing baselines:

- `src/qhpc_cache/pricing.py`
- `src/qhpc_cache/analytic_pricing.py`
- `src/qhpc_cache/market_models.py`

## Locked model-family order

The benchmark sequence is intentionally fixed:

1. `black_scholes_closed_form`
2. `monte_carlo_european`
3. `heston_monte_carlo`
4. `crr_lattice`

## Modeling assumptions and support

- Black-Scholes:
  - closed-form baseline
  - constant rate/volatility, no dividends
  - European call/put only
  - Greeks: analytic `delta`, `gamma`, `vega`, `theta`
- Monte Carlo European:
  - GBM terminal-payoff simulation
  - European call/put only
  - Greeks: finite-difference
- Heston Monte Carlo:
  - stochastic variance model
  - Euler full-truncation approximation
  - European call/put only
  - Greeks: finite-difference
- CRR lattice:
  - binomial lattice baseline
  - European call/put
  - Greeks: finite-difference

This layer reports workload-structure evidence and does not claim microarchitectural proof.

## Canonical APIs

Model-family pricing:

- `price_black_scholes_contract(...)`
- `price_monte_carlo_european_contract(...)`
- `price_heston_monte_carlo_contract(...)`
- `price_crr_lattice_contract(...)`
- `build_pricing_family_bundle(...)`
- `compare_pricing_model_families(...)`

Contract-batch and Greeks:

- `build_contract_batch(...)`
- `build_contract_batch_family(...)`
- `run_batch_pricing(...)`
- `run_greeks_batch(...)`
- `compare_price_only_vs_price_plus_greeks(...)`
- `summarize_contract_batch_workload(...)`

Comparison and ranking:

- `compare_closed_form_vs_simulation(...)`
- `compare_model_family_timing(...)`
- `compare_contract_batch_workloads(...)`
- `compare_price_only_vs_greeks_workloads(...)`
- `summarize_pricing_recomputation_patterns(...)`
- `summarize_pricing_reuse_proxies(...)`
- `rank_pricing_workloads_for_cache_study_value(...)`

Bundle and export:

- `run_pricing_workload_bundle(...)`
- `export_pricing_workload_bundle(...)`

## Primary outputs (CSV/JSON first)

CSV:

- `pricing_workload_manifest.csv`
- `pricing_model_family_summary.csv`
- `pricing_contract_batch_summary.csv`
- `pricing_greeks_summary.csv`
- `pricing_timing_summary.csv`
- `pricing_reuse_proxy_summary.csv`
- `pricing_workload_rankings.csv`

JSON:

- `pricing_workload_manifest.json`
- `pricing_model_family_manifest.json`
- `pricing_batch_manifest.json`

## Secondary outputs

Markdown:

- `pricing_model_family_summary.md`
- `pricing_contract_batch_summary.md`
- `pricing_workload_rankings_summary.md`

Plots:

- model-family timing comparison
- batch-size comparison
- price-only vs Greeks comparison
- pricing workload ranking
- parameter-grid comparison

## Mac vs HPC discipline

The module includes Mac-oriented scope degradation for contract count and per-contract path count.
When degraded, deferred workloads are explicitly listed as HPC-targeted notes.
No x86 PMU counters are claimed in this phase.

