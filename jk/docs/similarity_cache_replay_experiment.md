# Similarity Cache Replay Experiment

This experiment is a measurable local replay benchmark, designed for Mac
execution. It does not silently degrade into exact-match behavior.

## Objective

Compare three strategies on the same repeated Monte Carlo workload family:

1. `no_cache`
2. `exact_cache`
3. `similarity_cache` (threshold-gated near-match reuse)

## API

- `run_similarity_cache_replay_experiment(...)`

## Inputs

- `num_requests`
- `pricing_kwargs` (for the baseline contract family)
- `random_seed`
- `scale_label` (`smoke`, `standard`, `heavy`)
- `similarity_threshold`
- `fail_on_low_similarity_quality` (optional hard fail)
- `max_mean_abs_error`
- `progress_jsonl_path`
- `checkpoint_json_path`
- `resume_from_checkpoint`

## Outputs

Per strategy:

- `cache_hits`
- `similarity_hits`
- `cache_misses`
- `mean_abs_error_vs_no_cache`
- `p95_abs_error_vs_no_cache`
- `total_runtime_ms`
- `average_runtime_per_request_ms`

Manifest-level:

- workload family mix counts
- explicit `degraded_paths` list
- explicit `warnings` list
- `valid_evidence_strategies` and `excluded_strategies`
- `forensic_cases` for weak/failed/excluded branches
- per-strategy execution status fields:
  - `execution_status`
  - `evidence_valid`
  - `excluded_from_summary`
  - `exclusion_reason`

Resumability behavior:

- stage-level resume is supported (`baseline`, `exact`, `similarity`)
- intra-stage resume is not yet supported
- checkpoint file tracks completed stages and partial artifacts

## Failure forensics

Zero-signal and weak-evidence triggers automatically emit forensic cases, such
as:

- `zero_similarity_hits`
- `zero_cache_hits`
- `constant_similarity_score_distribution`
- `empty_timing_benefit_vs_no_cache`
- `excluded_from_valid_evidence`

## Fail-loud behavior

If `fail_on_low_similarity_quality=True` and similarity error exceeds
`max_mean_abs_error`, the run raises `RuntimeError` with details. This is
intentional to avoid hidden quality degradation.

## Example

```python
from qhpc_cache.experiment_runner import run_similarity_cache_replay_experiment

summary = run_similarity_cache_replay_experiment(
    num_requests=60,
    pricing_kwargs={"num_paths": 12000},
    random_seed=777,
    similarity_threshold=0.92,
    fail_on_low_similarity_quality=True,
    max_mean_abs_error=0.75,
    output_csv_path="outputs/similarity_cache_replay_results.csv",
    output_manifest_path="outputs/similarity_cache_replay_manifest.json",
)
```
