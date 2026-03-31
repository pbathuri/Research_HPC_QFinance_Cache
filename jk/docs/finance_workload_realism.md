# Finance Workload Realism

## Overview

This document explains the relationship between the workload families in this research system and real quantitative-finance compute patterns. The system does not claim to reproduce proprietary bank systems, but its workload families are designed to model the compute regimes that produce the access patterns relevant to cache research.

## Realism Tiers

### `finance_inspired`
Directly models a pattern seen in production quantitative finance. The parameter structure, access order, and reuse characteristics are analogous to real systems.

### `finance_analogous`
Structurally similar to finance patterns but with simplifications. The cache-relevant properties (reuse distance, locality, similarity structure) are preserved.

### `synthetic_control`
Explicitly artificial workload designed to stress-test the system or provide a known-behavior baseline. Not representative of real finance workflows.

## Family-to-Finance Mapping

| Family | Finance Analogy | Key Pattern |
|---|---|---|
| `exact_repeat_pricing` | Intraday re-check, audit replay, cache-warm restart | Identical parameters, identical results |
| `near_repeat_pricing` | Bump-and-revalue Greeks, scenario ladders | Small parameter perturbations, clustered similarity |
| `path_ladder_pricing` | Monte Carlo convergence analysis | Same instrument, increasing path counts |
| `portfolio_cluster_condensation` | Portfolio cluster revaluation, sector groups | Instruments grouped by underlying, small perturbations |
| `overlapping_event_window_rebuild` | Rolling VaR, event-study windows | Temporal overlap producing exact and near-reuse |
| `stress_churn_pricing` | Adversarial/stress control (NOT a real pattern) | High churn, minimal reuse |
| `intraday_scenario_ladder` | Front-office PnL attribution, ordered shock grids | Systematic ordered shocks with adjacent similarity |
| `cross_sectional_basket_repricing` | Index constituent repricing, basket options | Correlated underlyings sharing vol/rate parameters |
| `rolling_horizon_refresh` | EOD/SOD portfolio roll, T+1 settlement | Same book with shifted horizon, small market drift |
| `hotset_coldset_mixed` | Active trading book with concentrated volume | Zipfian access distribution, hot instruments dominate |
| `parameter_shock_grid` | CCAR/DFAST regulatory stress grids | Full factorial parameter sweep, minimal reuse |

## Publication Relevance

For paper-grade results, prioritize:
1. `exact_repeat_pricing` (baseline exact-match validation)
2. `near_repeat_pricing` (core similarity-cache evidence)
3. `portfolio_cluster_condensation` (feature condensation evidence)
4. `overlapping_event_window_rebuild` (temporal reuse evidence)
5. `intraday_scenario_ladder` (ordered similarity evidence)

Use `stress_churn_pricing` as the essential negative control. Include it in every comparison to demonstrate truthful reporting.

## What These Workloads Do NOT Model

- Real market data ingestion from live feeds
- Proprietary pricing model internals (e.g., stochastic local volatility)
- Network latency in distributed pricing grids
- Regulatory data lineage requirements
- Multi-asset class portfolio effects beyond equity options

These limitations should be stated in any publication using this system.
