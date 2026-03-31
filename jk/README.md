# qhpc_cache prototype

Compact prototype for:

- classical Monte Carlo option pricing
- exact-match in-memory cache reuse
- heuristic and AI-assisted cache policy stubs
- lightweight experiment runner baselines

This repository currently supports **prototype cache experiments**, not a
production cache controller or hardware-level cache validation.

## Implemented now

- `src/qhpc_cache/pricing.py`
  - GBM Monte Carlo pricing (European, digital, Asian)
  - optional antithetic variates and control variate
  - seeded reproducibility (`random_seed`)
  - lightweight timing instrumentation
- `src/qhpc_cache/cache_store.py`
  - exact-match in-memory cache
  - diagnostics: hits, misses, entries, lookup/put/overwrite counts, rates
- `src/qhpc_cache/cache_policy.py`
  - heuristic and logistic policy stubs
  - AI-assisted stub with explicit fallback modes and diagnostics counters
- `src/qhpc_cache/experiment_runner.py`
  - repeated-pricing summaries
  - policy comparison helper
  - canonical exact-match cache baseline experiment
  - similarity-cache replay experiment with measured error vs no-cache baseline
- `src/qhpc_cache/feature_builder.py`
  - active cache-key feature construction including full pricing inputs

## Experimental / placeholder only

- `placeholders.py`: circuit metadata placeholders
- `fourier_placeholder.py`: research benchmark hooks (not an HPC engine)
- similarity-aware cache logic in active `MonteCarloPricer.price_option`: **not implemented**
- similarity reuse is available as an explicit replay experiment only
- PMU/x86 cache-counter validation: **not implemented**
- BigRed200 execution: **not implemented**
- real quantum backend execution: **not implemented**

## Canonical exact-match cache experiment

See:

- `docs/exact_match_cache_experiment.md`

Run:

```python
from qhpc_cache.experiment_runner import run_canonical_exact_match_cache_experiment

summary = run_canonical_exact_match_cache_experiment(
    num_trials=12,
    random_seed=123,
    output_csv_path="outputs/exact_match_cache_results.csv",
)
```

This compares:

1. no-cache baseline
2. exact cache without policy gate
3. heuristic policy + cache
4. AI-assisted stub policy + cache

Policy fallback usage is explicit in experiment outputs:

- `policy_diagnostics.fallback_used_count`
- `policy_diagnostics.fallback_no_model_count`
- `policy_diagnostics.fallback_inference_error_count`

All canonical experiment outputs now include execution-evidence status fields:

- `execution_status`
- `evidence_valid`
- `excluded_from_summary`
- `exclusion_reason`

Headline summaries are computed from valid evidence only.

Weak/failed branches now emit structured forensic diagnostics (JSON manifest
fields), including triggers such as:

- `zero_cache_hits`
- `zero_similarity_hits`
- `all_misses`
- `empty_timing_benefit_vs_no_cache`
- `excluded_from_valid_evidence`

Forensic payloads include cache stats, top repeated keys, scale/config context,
and exclusion reasons.

## Canonical similarity-cache replay experiment

This is a measurable local experiment (not a hidden fallback path). It replays a
mixed repeated workload family and compares:

1. `no_cache`
2. `exact_cache`
3. `similarity_cache` (threshold-gated near-match reuse)

```python
from qhpc_cache.experiment_runner import run_similarity_cache_replay_experiment

summary = run_similarity_cache_replay_experiment(
    num_requests=60,
    similarity_threshold=0.92,
    random_seed=777,
    output_csv_path="outputs/similarity_cache_replay_results.csv",
    output_manifest_path="outputs/similarity_cache_replay_manifest.json",
    fail_on_low_similarity_quality=True,
    max_mean_abs_error=0.75,
)
```

Returned metrics include:

- `cache_hits`, `similarity_hits`, `cache_misses`
- `mean_abs_error_vs_no_cache`, `p95_abs_error_vs_no_cache`
- `total_runtime_ms`, `average_runtime_per_request_ms`
- `execution_status`, `evidence_valid`, `excluded_from_summary`, `exclusion_reason`

## Long-run local scales and resumability

Major experiment families support explicit scale labels:

- `smoke`: correctness check only
- `standard`: meaningful local evidence
- `heavy`: aggressive local run (long duration expected)

Families with scale support:

- `run_repeated_pricing_experiment(...)`
- `run_canonical_exact_match_cache_experiment(...)`
- `run_cache_policy_comparison_experiment(...)`
- `run_similarity_cache_replay_experiment(...)`

Long runs support incremental progress/checkpoint writing through:

- `progress_jsonl_path`
- `checkpoint_json_path`

Heavy local sweep orchestrator:

```python
from qhpc_cache.experiment_runner import run_local_research_sweep

manifest = run_local_research_sweep(
    output_dir="outputs/long_runs",
    scale_label="heavy",
    resume_from_checkpoint=True,
)
```

Tier-aware execution (default runs Tier 1 + Tier 2):

```python
manifest = run_local_research_sweep(
    output_dir="outputs/long_runs_tier1",
    scale_label="standard",
    tiers_to_run=[1],  # run only correctness-critical core evidence
)
```

Tier definitions and ownership now live in `docs/long_run_local_research.md`.

## Repeated-workload study (reuse-rich local evidence)

Use the canonical repeated-workload phase when you want deliberate reuse-rich local
cache evidence (Lane A stable headline evidence, Lane B stress/anomaly visibility):

```bash
PYTHONPATH=src python3 run_repeated_workload_study.py --lane both --scale-label standard
```

Backward-compatible CLI alias is available for operator scripts:

```bash
PYTHONPATH=src python3 run_repeated_workload_study.py --lane lane_a --include-stress-lane
```

See `docs/repeated_workload_study.md`.

## Install and run

From `jk/`:

```bash
pip install -e .
python3 run_demo.py
```

Run tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Key docs for this prototype phase

- `docs/prototype_stabilization_audit.md`
- `docs/exact_match_cache_experiment.md`
- `docs/similarity_cache_replay_experiment.md`
- `docs/similarity_cache_future_steps.md`
- `docs/long_run_local_research.md`
- `docs/repeated_workload_study.md`

## Scope disclaimer

This prototype is for scientific software baselines and reproducible cache
experiments. It does not claim completed similarity caching, PMU validation, HPC
execution, or quantum advantage.
