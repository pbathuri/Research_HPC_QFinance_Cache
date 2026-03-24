# Event Library Comparison (Canonical)

Owner modules:

- `src/qhpc_cache/event_library_compare.py`
- `src/qhpc_cache/event_library_registry.py`

This layer compares locked event sets A-E under one normalized schema and emits researcher-grade outputs for analysis, interpretation, reproducibility, and inspection.

## Scope

- Operates on the five locked event sets from `event_set_library`.
- Includes a ruleset-generated Set E mixed institutional stress library (~39 events).
- Uses locked multi-day windows by default.
- Supports intraday slice extensions for stress and microstructure inspection.
- Keeps a Mac-compatible execution path with explicit HPC defer notes for oversized workloads.

## Common normalized schema

All event-set comparison runs normalize into one schema with stable fields:

- `event_set_id`
- `event_id`
- `event_label`
- `category_label`
- `window_family_label`
- `intraday_slice_label`
- `permno`
- `symbol`, `symbol_root`
- `window_start`, `window_end`, `event_time_start`, `event_time_end`
- `alignment_match_quality`
- `source_datasets`
- `row_count`, `join_width`
- `normalized_window_id`
- `join_pattern_id`
- `derived_structure_id`
- `stage_timing_ms`

## Canonical APIs

- `build_event_set_manifest(...)`
- `run_event_set_comparison(...)`
- `compare_event_set_sizes(...)`
- `compare_event_category_distribution(...)`
- `compare_alignment_quality(...)`
- `compare_window_family_behavior(...)`
- `export_event_library_comparison(...)`

Registry:

- `register_event_library_comparison(...)`
- `register_event_library_manifest(...)`

## Output package

CSV:

- `event_window_manifest.csv`
- `event_window_alignment_quality.csv`
- `event_library_comparison.csv`
- `workload_signature_summary.csv`
- `timing_distribution_summary.csv`
- `cache_proxy_summary.csv`

JSON:

- `event_set_manifest.json`
- `window_policy_manifest.json`
- `event_library_comparison_manifest.json`

Markdown:

- `event_set_summary.md`
- `event_library_comparison_summary.md`
- `workload_signature_summary.md`

Plots (matplotlib/seaborn if available):

- `plot_event_set_size_comparison.png`
- `plot_category_distribution_comparison.png`
- `plot_window_family_comparison.png`
- `plot_alignment_quality_comparison.png`
- `plot_timing_distribution_comparison.png`
- `plot_workload_signature_comparison.png`

## Example run

```python
from qhpc_cache.event_library_compare import run_event_set_comparison, export_event_library_comparison

result = run_event_set_comparison(raw_event_rows=normalized_aligned_rows)
paths = export_event_library_comparison(
    comparison_result=result,
    output_dir="outputs/event_library_comparison",
)
```
