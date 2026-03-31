# Research Methodology

## Research Question

How do cacheability, reuse distance, locality structure, similarity-based reuse, and feature condensation behave across realistic quantitative-finance-style workloads, and under what conditions do caching policies produce genuine net computational benefit?

## Methodological Framework

### Reuse as a Decision Problem

Cache reuse is not merely observed; it is a decision with consequences. Every reuse decision is evaluated on:

1. **Latency savings** - compute time avoided
2. **Pricing error** - deviation of cached result from fresh recompute
3. **Risk error** - std_error deviation where applicable
4. **False-reuse penalty** - policy approved reuse that was incorrect
5. **False-miss penalty** - policy rejected reuse that was correct

The utility function is:

```
utility = latency_weight * latency_saved
        - price_error_penalty * |price_deviation|
        - std_error_penalty * |se_deviation|
        - false_reuse_penalty * is_false_reuse
        - false_miss_penalty * is_false_miss
```

Weights are configurable. Default weights penalize false reuse 20x more than false misses, reflecting the asymmetric cost of incorrect pricing in production.

### Ground-Truth Cacheability Labels

Each request receives a structural cacheability label based on metadata:

| Label | Meaning |
|-------|---------|
| `exact_reusable` | Parameter hash repeated; exact reuse valid in principle |
| `similarity_reusable_safe` | Similarity group + feature match; safe reuse |
| `similarity_reusable_unsafe` | Similarity group but feature differs; needs tolerance validation |
| `non_reusable_model_change` | Model changed between requests |
| `non_reusable_market_state_change` | Market state shifted beyond tolerance |
| `non_reusable_policy_forbidden` | Policy explicitly forbids reuse |
| `non_reusable_feature_insufficient` | Feature representation inadequate |
| `recompute_required` | Fresh computation required by design |
| `unique_first_access` | First occurrence, no reuse possible |
| `undetermined` | Insufficient metadata |

These labels separate three distinct causes of low hit rates:
- Unique workloads (no reuse possible)
- Weak cache logic (reuse possible but cache missed)
- Inadequate feature representation (similar items not recognized)

### Policy Tier Comparison

Results are evaluated under a baseline hierarchy:

1. No cache (baseline)
2. Exact cache only
3. Exact + simple heuristic
4. Exact + similarity
5. Exact + similarity + guardrails
6. Exact + similarity + regime-aware guardrails

### Failure Taxonomy

Every failure, skip, or degradation is classified:

| Code | Meaning |
|------|---------|
| `engine_unavailable` | Optional engine not installed |
| `dependency_unavailable` | Required dependency missing |
| `feature_representation_insufficient` | Feature system can't distinguish items |
| `policy_too_strict` | Valid reuse rejected |
| `policy_too_loose` | Invalid reuse accepted |
| `unique_workload` | No structural repetition |
| `unsafe_similarity` | Similarity reuse exceeds error tolerance |
| `data_source_missing` | WRDS/vendor data not connected |
| `proxy_measurement_only` | Metric is estimated, not observed |
| `cluster_env_mismatch` | Cluster environment differs from expected |
| `parallelism_not_exercised` | Single-threaded execution on multi-core |

### Epistemic Status

Every metric and output carries epistemic status:

- **observed**: directly measured from execution
- **derived**: computed from observed quantities
- **proxy**: estimated approximation of unmeasurable quantity
- **simulated**: from synthetic workload, not production
- **skipped**: intentionally omitted
- **unavailable**: attempted but failed
- **unsupported**: not applicable to current configuration

## Market Regime Types

Workloads are generated under seven regime conditions:

| Regime | Volatility | Drift | Correlation | Expected Reuse |
|--------|-----------|-------|-------------|----------------|
| `calm_low_vol` | 0.08-0.18 | Low | High | High |
| `high_vol` | 0.30-0.65 | Moderate | Medium | Moderate |
| `jump` | 0.20-0.80 | High | Low | Low |
| `correlation_cluster` | 0.15-0.30 | Low | Very High | High (similarity) |
| `rebalance_burst` | 0.12-0.28 | Low | High | Very High (exact) |
| `event_driven_shock` | 0.25-0.55 | High | Low | Low |
| `liquidity_stress` | 0.35-0.70 | Very High | Very Low | Near Zero |

## Tolerance Sweep Methodology

Similarity reuse safety is mapped across parameter space:
- Price tolerance: 0.1% to 10%
- Sigma tolerance: 0.5% to 10%
- Maturity tolerance: 0.5% to 10%
- Path-count tolerance: 0% to 100%

Outputs include:
- Safe/unsafe region maps
- Pareto fronts (savings vs. error)
- Sensitivity tables per dimension

## Evidence Interpretation Rules

1. **Zero-hit run**: Not a failure. May indicate unique workloads. Check cacheability label distribution.
2. **High hit rate with high error**: Dangerous. Policy is too loose. Check false_reuse_count.
3. **Low hit rate with high potential**: Cache logic gap. Check `cache_recall_on_reusable`.
4. **Budget underutilization**: Not waste. May indicate workload exhaustion. Check `termination_reason`.
5. **HPC underutilization**: Expected if single-engine, single-threaded. Use `hpc_utilization.json` decomposition.

## Reproducibility

All runs are deterministic given:
- Seed value
- Template bank ID
- Scale label
- Lane selection
- Workload families
- Engine allowlist

Provenance is captured in every manifest.
