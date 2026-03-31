# Repeated Workload Study (Local Cache-Reuse Evidence)

## Why this phase exists

The full pipeline is valuable for end-to-end realism, but its request stream is often
mostly unique. That makes it weak as a standalone source of exact-match cache-reuse
evidence.

This study adds a deliberate repeated-workload layer with deterministic, structured
families that are designed to expose reuse behavior on local Mac hardware.

## Lane policy

- **Lane A (`lane_a`)**: canonical stable evidence lane  
  engines: `classical_mc`, `quantlib_mc`, `cirq_qmci`
- **Lane B (`lane_b`)**: stress/anomaly lane  
  engines: `classical_mc`, `quantlib_mc`, `cirq_qmci`, `monaco_mc`

Lane A is the headline evidence lane. Lane B is retained to surface stress behavior and
timing anomalies honestly.

## Workload families

Implemented deterministic families:

1. `exact_repeat_pricing`
2. `near_repeat_pricing`
3. `path_ladder_pricing`
4. `portfolio_cluster_condensation`
5. `overlapping_event_window_rebuild`
6. `stress_churn_pricing`

All families are generated from a structured template bank with varied moneyness,
maturity, volatility, and path scales.

## Canonical entrypoint

```bash
PYTHONPATH=src python3 run_repeated_workload_study.py --lane both --scale-label standard
```

Optional family filter:

```bash
PYTHONPATH=src python3 run_repeated_workload_study.py \
  --lane lane_a \
  --include-stress-lane \
  --families exact_repeat_pricing,near_repeat_pricing,path_ladder_pricing \
  --scale-label smoke
```

Backwards-compatible CLI alias:

- `--include-stress-lane` upgrades `--lane lane_a` to `--lane both`.
- Existing canonical `--lane` flag remains unchanged.

## Canonical outputs

Under `outputs/repeated_workload_phase/`:

- `repeated_workload_requests.csv`
- `repeated_workload_results.csv`
- `repeated_workload_summary.csv`
- `repeated_workload_rankings.csv`
- `repeated_workload_rankings_summary.md`
- `repeated_workload_timing_summary.csv`
- `repeated_workload_cache_summary.csv`
- `repeated_workload_family_comparison.csv`
- `repeated_workload_outliers.csv`
- `repeated_workload_manifest.json`
- `repeated_workload_lane_a_manifest.json`
- `repeated_workload_lane_b_manifest.json`
- `repeated_workload_hit_rate_comparison.png`
- `repeated_workload_runtime_comparison.png`
- `repeated_workload_locality_comparison.png`
- `repeated_workload_rankings.png`

## Outlier policy

Outliers are identified from `pricing_compute_time_ms` under explicit row semantics.

- Lane A: pathological timing rows may be excluded from summary metrics, but only with
  explicit logging in `repeated_workload_outliers.csv`.
- Lane B: stress behavior is retained and labeled, not silently dropped.
- Raw and robust timing summaries are both emitted so long-tail rows remain visible.

## Scope honesty

This phase strengthens local empirical reuse evidence. It does **not** claim PMU-level
hardware proof. PMU/x86 hardware-counter validation remains a later HPC phase.
