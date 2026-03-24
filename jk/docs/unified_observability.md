# Unified Observability Across Workload Families (Canonical)

Owner modules:

- `src/qhpc_cache/unified_observability.py`
- `src/qhpc_cache/workload_family_registry.py`

This phase unifies observability for four locked workload families:

1. event workloads
2. feature-panel workloads
3. portfolio-risk workloads
4. pricing workloads

Schema first, ranking/similarity second.

## Common schema

Canonical row fields include:

- `workload_family`
- `workload_variant`
- `workload_spine_id`
- `workload_spine_rank`
- `deterministic_label`
- `source_dataset_labels`
- `n_rows`
- `n_entities`
- `n_dates_or_periods`
- `join_width`
- `feature_dim_before`
- `feature_dim_after`
- `scenario_count`
- `batch_size`
- `parameter_grid_width`
- `timing_p50`
- `timing_p90`
- `timing_p99`
- `timing_p999`
- `reuse_proxy_count`
- `reconstruction_proxy_count`
- `cache_proxy_reuse_density`
- `cache_proxy_locality_hint`
- `cache_proxy_alignment_penalty`
- `execution_environment`
- `mac_executable_now`
- `deferred_to_hpc`
- `notes`

Additional governance fields:

- `source_outputs_used`
- `metric_lineage`
- `unavailable_fields`

If a field is unavailable for a family, it is left blank and listed in
`unavailable_fields` instead of being invented.

## Family adapters

Adapters reuse existing manifests/summaries:

- `adapt_event_workload_to_common_schema(...)`
- `adapt_feature_panel_workload_to_common_schema(...)`
- `adapt_portfolio_risk_workload_to_common_schema(...)`
- `adapt_pricing_workload_to_common_schema(...)`
- `build_unified_workload_observation_table(...)`

## Ranking layer (on top of common schema)

- `rank_workload_families_for_cache_study_value(...)`
- `rank_workload_variants_for_reuse_potential(...)`
- `rank_workload_variants_for_reconstruction_repetition(...)`
- `rank_workload_variants_for_mac_vs_hpc_priority(...)`
- `export_unified_workload_rankings(...)`

## Similarity/comparability layer

- `compare_workload_families_by_shape(...)`
- `compare_workload_families_by_timing(...)`
- `compare_workload_families_by_reuse_proxy(...)`
- `compare_workload_families_by_dimension(...)`
- `summarize_cross_family_similarity(...)`

Similarity output is structured evidence, not a final similarity engine.

## Canonical APIs

Build bundle:

- `run_unified_observability_bundle(...)`

Export artifacts:

- `export_unified_observability_bundle(...)`

Registry helpers:

- `register_unified_workload_observability(...)`
- `register_unified_workload_manifest(...)`

## Primary outputs (CSV/JSON first)

CSV:

- `unified_workload_observations.csv`
- `unified_workload_family_summary.csv`
- `unified_workload_timing_summary.csv`
- `unified_workload_reuse_proxy_summary.csv`
- `unified_workload_rankings.csv`
- `unified_workload_similarity_summary.csv`

JSON:

- `unified_workload_manifest.json`
- `unified_workload_rankings_manifest.json`
- `unified_workload_similarity_manifest.json`

## Secondary outputs

Markdown:

- `unified_workload_summary.md`
- `unified_workload_rankings_summary.md`
- `unified_workload_similarity_summary.md`

Plots:

- cross-family timing comparison
- cross-family dimension comparison
- reuse-proxy comparison
- unified ranking comparison
- cross-family similarity comparison
- Mac-vs-HPC escalation priority

## Mac vs HPC discipline

This layer compares families under one schema using Mac-valid direct metrics,
derived metrics, and proxy metrics. Deferred fields/workloads are explicit.
PMU/x86 counters remain deferred to later HPC phases.

