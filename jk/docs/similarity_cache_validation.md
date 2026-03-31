# Similarity Cache Validation

## Overview

Similarity-based caching reuses results from a previously computed similar (but not identical) request. This introduces approximation. This document explains how the system validates whether such reuse is beneficial and honest.

## Exact vs. Similarity Reuse

| Reuse Type | Mechanism | Error | When Valid |
|---|---|---|---|
| Exact | Same parameter hash → cache hit | Zero | Always (by construction) |
| Similarity | Similar parameters → reuse decision | Non-zero | When error is bounded and savings exceed cost |

## How Similarity Is Detected

The system assigns `similarity_group_id` and `feature_hash` to each request:
- `similarity_group_id`: Instruments in the same group share structural similarity (same underlying, similar params)
- `feature_hash`: A quantized hash grouping requests with nearby parameters

A request is flagged as a `similarity_hit` when:
1. It is a cache miss (no exact match)
2. A prior request in the same similarity group has been seen

## Decomposition Artifacts

`similarity_acceptance_summary.csv` reports per-family:
- `exact_hit_count` / `exact_hit_rate`
- `similarity_candidate_count` / `similarity_accepted_count` / `similarity_rejected_count`
- `similarity_hit_rate` / `combined_hit_rate`

These must never be merged into a single hit-rate without decomposition.

## Approximation Quality

For each similarity reuse, the system tracks:
- `approximation_error_abs`: Absolute error between reused and true result
- `approximation_error_rel`: Relative error
- `reuse_savings_ms`: Time saved by reusing

The policy frontier (`cache_policy_value_summary.csv`) shows how different similarity thresholds trade off error vs. savings.

## When Similarity Caching Is Worthwhile

Similarity caching is worthwhile when:
1. **Mean error** is below the application's tolerance (e.g., < 0.01 for pricing)
2. **Max error** is bounded (no catastrophic outliers)
3. **Time saved** substantially exceeds lookup overhead
4. **Net benefit** (`net_cache_value_ms > 0`) is positive for the family

## When Similarity Caching Is NOT Worthwhile

- `stress_churn_pricing`: Parameters are too dispersed for meaningful similarity
- `parameter_shock_grid`: Each grid point is unique by design
- Any family where `approximation_risk` is `high` without independent validation

## Future Work

- Independent recomputation of a control sample to validate approximation error
- Threshold optimization using the policy frontier
- Adaptive similarity thresholds per workload family
