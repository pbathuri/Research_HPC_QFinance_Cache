# Cache Study Analysis (First Evidence Layer)

Owner modules:

- `src/qhpc_cache/cache_study_analysis.py`
- `src/qhpc_cache/cache_study_registry.py`

This phase builds the first serious cache-study analysis layer on top of the event-library substrate.

## Locked stage order

1. **Within-set deep analysis first**
2. **Cross-set comparison second**

The order is intentionally fixed.

## Scope

Operates on locked event sets:

- Set A: COVID crash
- Set B: March 2020 liquidity stress
- Set C: 2022 rate shock
- Set D: 2023 banking stress
- Set E1: broad mixed institutional stress library (~35-40 curated events)

Set E2 (equity-desk style earnings-heavy extension) remains deferred.

## Within-set APIs

- `analyze_event_set_cache_structure(...)`
- `analyze_window_family_within_set(...)`
- `analyze_intraday_slice_within_set(...)`
- `summarize_alignment_quality_within_set(...)`
- `summarize_reconstruction_reuse_within_set(...)`
- `summarize_timing_within_set(...)`
- `summarize_cache_proxies_within_set(...)`

## Cross-set APIs

- `compare_event_sets_cache_structure(...)`
- `compare_event_sets_alignment_quality(...)`
- `compare_event_sets_timing(...)`
- `compare_event_sets_reuse_proxies(...)`
- `rank_event_sets_for_cache_study_value(...)`
- `export_cross_set_cache_summary(...)`

## End-to-end APIs

- `run_cache_study_analysis(...)`
- `export_cache_study_analysis(...)`

## Primary data products (first-class)

CSV:

- `cache_study_within_set_summary.csv`
- `cache_study_cross_set_summary.csv`
- `cache_study_timing_summary.csv`
- `cache_study_reuse_proxy_summary.csv`
- `cache_study_alignment_summary.csv`
- `cache_study_rankings.csv`

JSON:

- `cache_study_within_set_manifest.json`
- `cache_study_cross_set_manifest.json`
- `cache_study_analysis_manifest.json`

## Secondary interpretation outputs

Markdown:

- `cache_study_within_set_summary.md`
- `cache_study_cross_set_summary.md`
- `cache_study_rankings_summary.md`

Plots:

- within-set timing distributions
- cross-set timing comparison
- alignment-quality comparison
- reuse-proxy comparison
- event-set ranking plots
- window-family comparison plots

## Mac-compatible proxies used now

- repeated reconstruction counts
- repeated join-pattern counts
- reusable derived-structure counts/proxies
- timing distributions (`p50`, `p90`, `p99`, `p99.9`)
- row count / join width / dimensionality style summaries
- workload family labels

These are **first-layer proxies** and not PMU/x86 proof.

## Deferred HPC/x86 metrics

Explicitly deferred:

- L1/L2/L3 miss metrics
- prefetch metrics
- TLB metrics
- NUMA / remote-hit metrics
- false-sharing / cache-line-bounce metrics
