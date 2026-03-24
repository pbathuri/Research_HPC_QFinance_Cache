# Feature Panel Comparison (Canonical)

Owner module:

- `src/qhpc_cache/feature_panel_compare.py`

Canonical panel owner remains:

- `src/qhpc_cache/feature_panel.py`

This layer compares four locked panel variants across two axes:

- Axis A: event-aware vs non-event-aware
- Axis B: raw vs PCA-condensed

## Locked panel variants

1. `non_event_aware_raw`
2. `non_event_aware_pca_condensed`
3. `event_aware_raw`
4. `event_aware_pca_condensed`

## Canonical builders

- `build_non_event_aware_raw_panel(...)`
- `build_non_event_aware_condensed_panel(...)`
- `build_event_aware_raw_panel(...)`
- `build_event_aware_condensed_panel(...)`
- `build_feature_panel_variant(...)`
- `build_feature_panel_comparison_bundle(...)`

## Comparison APIs

- `compare_event_aware_vs_non_event_aware(...)`
- `compare_raw_vs_condensed(...)`
- `compare_panel_variants(...)`
- `summarize_panel_dimensionality(...)`
- `summarize_panel_reuse_proxies(...)`
- `summarize_panel_timing(...)`
- `rank_panel_variants_for_cache_study_value(...)`

## Primary outputs (CSV/JSON)

CSV:

- `feature_panel_variant_manifest.csv`
- `feature_panel_comparison_summary.csv`
- `feature_panel_condensation_summary.csv`
- `feature_panel_timing_summary.csv`
- `feature_panel_reuse_proxy_summary.csv`
- `feature_panel_dimension_summary.csv`

JSON:

- `feature_panel_variant_manifest.json`
- `feature_panel_comparison_manifest.json`
- `feature_panel_condensation_manifest.json`

## Secondary outputs (markdown/plots)

Markdown:

- `feature_panel_comparison_summary.md`
- `feature_panel_condensation_summary.md`
- `feature_panel_rankings_summary.md`

Plots:

- feature count before/after condensation
- panel variant timing comparison
- event-aware vs non-event-aware comparison
- raw vs condensed comparison
- panel ranking plots
- dimensionality comparison plots

## Condensation policy

- Raw panel is canonical baseline.
- PCA-condensed panel is secondary compressed variant.
- Records:
  - `feature_count_before_condense`
  - `feature_count_after_condense`
  - `condensation_method`
  - `explained_variance_ratio_sum` (if available)
  - `sklearn_used`
  - `condensation_skipped` and reason

## Mac vs HPC note

This layer remains Mac-executable and records deferred scope if input size is too large.
PMU/x86 microarchitectural metrics remain deferred (see `docs/mac_vs_hpc_observability.md`).
