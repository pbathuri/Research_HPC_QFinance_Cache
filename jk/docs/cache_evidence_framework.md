# Cache Evidence Framework

## Purpose

This document defines what constitutes strong, weak, and null cache evidence in the qhpc_cache research system. It provides interpretation guidance for all evidence artifacts.

## Evidence Hierarchy

### Strong Evidence
- **Exact-match hits** where the same parameter hash is seen multiple times, producing cache hits that save measurable compute time.
- **Net positive cache value** across a workload family: `net_cache_value_ms > 0` with `net_benefit_flag = True`.
- **Validated similarity hits** where approximation error is quantified and bounded.
- **Reuse-distance distribution** showing concentration at small distances (p50 < 20).
- **Working-set growth** that plateaus, indicating finite and manageable cache footprint.

### Moderate Evidence
- **Similarity hits** where approximation error is estimated but not independently validated against recomputed controls.
- **Locality regime** classified as `moderate_temporal_locality` or `bursty_hotset`.
- **Positive cache value** that depends on a specific threshold choice.

### Weak Evidence
- **Low hit rates** with high one-hit-wonder fractions: the workload has limited reuse structure.
- **Budget-limited runs** where workload was too short to produce statistical significance.
- **Engine-limited runs** where only `classical_mc` was available.

### Null / Counter-Evidence
- **Zero-hit runs** for a workload family explicitly designed for reuse (indicates a bug or misconfiguration).
- **Negative net cache value** where lookup overhead exceeds savings.
- **Streaming locality regime** with `one_hit_wonder_fraction > 0.9`.

## Interpreting Zero-Hit Runs

A zero-hit run is not inherently a failure. For `stress_churn_pricing` (synthetic control), zero hits are expected and validate that the cache does not claim false benefit. For `exact_repeat_pricing`, zero hits indicate a problem.

Check:
1. Was the engine available? (check `hpc_execution_summary.json`)
2. Was the scale sufficient? (check `budget_utilization`)
3. Was the workload correctly constructed? (check `repeated_workload_requests.csv`)

## Interpreting Low-Hit, High-Value Runs

Some families (e.g., `path_ladder_pricing`) may show low hit rates but high per-hit value because each saved computation is expensive. Look at `benefit_per_hit` in `cache_policy_value_summary.csv`.

## Interpreting Approximate-Reuse Results

Similarity-based reuse introduces approximation. Always check:
- `similarity_acceptance_summary.csv` for acceptance/rejection decomposition
- Whether `approximation_risk` for the workload family is labeled `moderate` or `high`
- The policy frontier (if available) for threshold sensitivity

## Distinguishing Orchestration Success from Cache Research Success

A pipeline that completes without errors proves **orchestration correctness** but says nothing about **cache research outcomes**. The evidence artifacts (`cache_evidence_summary.json`) are the research output. Pipeline completion is a prerequisite, not a result.

## Artifact Reference

| Artifact | Purpose |
|---|---|
| `cache_evidence_summary.json` | Master evidence record |
| `cache_evidence_summary.md` | Human-readable evidence summary |
| `cache_reuse_distance.csv` | Per-access reuse distance |
| `cache_locality_summary.csv` | Per-family locality metrics |
| `cache_policy_value_summary.csv` | Cache economics by family |
| `working_set_timeline.csv` | Working-set dynamics over time |
| `similarity_acceptance_summary.csv` | Exact/similarity hit decomposition |
| `workload_regime_summary.csv` | Family metadata + observed metrics |
| `hpc_execution_summary.json` | Execution provenance |
| `reuse_distance_histogram.png` | Reuse distance distribution |
| `reuse_distance_cdf.png` | Reuse distance cumulative distribution |
| `working_set_over_time.png` | Working-set growth curve |
| `hotset_concentration.png` | Hotset concentration by family |
| `exact_vs_similarity_hits.png` | Hit-type decomposition |
| `net_cache_value_by_policy.png` | Net economic benefit by family |
| `locality_regime_comparison.png` | Temporal locality by family |
