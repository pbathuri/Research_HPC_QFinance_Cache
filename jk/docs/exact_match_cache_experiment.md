# Canonical Exact-Match Cache Experiment

This experiment establishes the baseline before any similarity-aware claims.

## Purpose

Measure reproducible exact-match cache reuse behavior for repeated identical
pricing requests.

This baseline should be run before interpreting any similarity-cache replay
results.

## Baseline conditions

1. `no_cache_baseline`
2. `exact_cache_no_policy_gate`
3. `heuristic_policy_plus_cache`
4. `ai_assisted_stub_policy_plus_cache`

## Reproducibility

- Use fixed `random_seed` for repeatable Monte Carlo paths.
- Keep request parameters identical across trials for exact-match checks.

## Minimal output metrics

- `average_price`
- `average_variance`
- `cache_hits`
- `cache_misses`
- `cache_entries`
- `hit_rate`
- `total_runtime_ms`
- `average_runtime_per_trial_ms`
- `put_count`
- `lookup_count`
- `overwrite_count`
- `policy_diagnostics` (for policy-gated conditions)
- `execution_status`
- `evidence_valid`
- `excluded_from_summary`
- `exclusion_reason`
- `forensic_cases` (for excluded/weak branches)

Final headline comparisons should use `valid_evidence_conditions` only.

## Canonical API

Use:

- `run_canonical_exact_match_cache_experiment(...)`
- `run_cache_policy_comparison_experiment(...)` (policy-level diagnostics)

Scale labels:

- `smoke`: fast correctness
- `standard`: meaningful local evidence
- `heavy`: long-run local evidence collection

Resumability/incremental artifacts:

- `progress_jsonl_path` for periodic progress rows
- `checkpoint_json_path` for resumable condition-level checkpoints
- `resume_from_checkpoint=True` to skip completed conditions

Optional CSV export path:

- `outputs/exact_match_cache_results.csv`

## Example

```python
from qhpc_cache.experiment_runner import run_canonical_exact_match_cache_experiment

summary = run_canonical_exact_match_cache_experiment(
    num_trials=12,
    random_seed=123,
    output_csv_path="outputs/exact_match_cache_results.csv",
)
```
