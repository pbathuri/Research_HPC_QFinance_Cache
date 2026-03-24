# Event Workload Signatures

Owner module: `src/qhpc_cache/event_workload_signatures.py`

This layer provides first-pass, structured workload signatures for event-library runs. It is designed for cache-study research on Mac-compatible observability proxies.

## Signature fields

Per `(event_set_id, window_family_label, intraday_slice_label)`:

- `row_count`
- `aligned_permno_count`
- `join_width`
- `identifier_match_quality`
- `repeated_event_window_reconstruction_markers`
- `repeated_join_pattern_markers`
- `reusable_derived_structure_markers`
- `workload_spine_id` (`event_window`)
- `workload_family_label`
- `timing_p50_ms`, `timing_p90_ms`, `timing_p99_ms`, `timing_p999_ms`
- `cache_proxy_reuse_density`
- `cache_proxy_locality_hint`
- `cache_proxy_alignment_penalty`

## Purpose

- Compare event-window workloads across canonical sets and windows.
- Track reconstruction and join-pattern repetition as reuse proxies.
- Produce timing and locality hints suitable for Mac execution.
- Prepare a stable substrate for later HPC/x86 PMU enrichment.

## Canonical API

- `compute_event_workload_signatures(normalized_event_rows)`
- `summarize_timing_distribution(signature_rows)`
- `summarize_cache_proxies(signature_rows)`
- `join_pattern_id_from_row(row)`

## Notes

- These are research proxies, not direct PMU proof.
- PMU/L1/L2/L3/TLB metrics are deferred to later HPC execution layers.
