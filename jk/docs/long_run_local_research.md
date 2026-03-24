# Long-Run Local Research Execution (Canonical Owner)

Canonical owner for cache/reuse experiment orchestration:

- module: `src/qhpc_cache/experiment_runner.py`
- primary orchestration entrypoint: `run_local_research_sweep(...)`

Long-run execution should extend this owner module rather than creating parallel
sidecar runners.

## Scale labels

- `smoke`: path correctness only
- `standard`: meaningful local evidence
- `heavy`: aggressive local evidence run (minutes/hours/overnight)

## Families with scale support

- `run_repeated_pricing_experiment(...)`
- `run_canonical_exact_match_cache_experiment(...)`
- `run_seeded_repeated_monte_carlo_family_experiment(...)`
- `run_cache_policy_comparison_experiment(...)`
- `run_similarity_cache_replay_experiment(...)`

## Incremental outputs

Long-run functions can emit:

- progress JSONL (`progress_jsonl_path`)
- checkpoint JSON snapshots (`checkpoint_json_path`)
- incremental CSV snapshots for condition/strategy summaries
- forensic diagnostics for weak/failed/excluded branches (`forensic_cases`)

## Resumability

- Exact-match canonical experiment:
  - resumes at condition level via `resume_from_checkpoint=True`
- Similarity replay:
  - resumes at stage level (`baseline`, `exact`, `similarity`)
  - does not yet resume inside a partially completed stage

## Sweep orchestrator

Use `run_local_research_sweep(...)` to run the canonical ladder-owned families
with a shared scale label and shared incremental artifacts.

```python
from qhpc_cache.experiment_runner import run_local_research_sweep

manifest = run_local_research_sweep(
    output_dir="outputs/long_runs",
    scale_label="heavy",
    resume_from_checkpoint=True,
)
```

Ladder-aware tier selection:

```python
manifest = run_local_research_sweep(
    output_dir="outputs/long_runs_tier1",
    scale_label="standard",
    tiers_to_run=[1],  # default is [1, 2]
)
```

## Experiment ladder (merged canonical view)

### Tier 1 (correctness-critical and core reuse evidence)

1. `canonical_exact_match_cache_experiment`
   - owner: `run_canonical_exact_match_cache_experiment(...)`
2. `seeded_repeated_monte_carlo_family_experiment`
   - owner: `run_seeded_repeated_monte_carlo_family_experiment(...)`
3. `cache_policy_comparison_experiment`
   - owner: `run_cache_policy_comparison_experiment(...)`

### Tier 2 (strong supporting evidence)

1. `similarity_cache_replay_experiment`
   - owner: `run_similarity_cache_replay_experiment(...)`

### Tier 3 (useful extension)

1. `payoff_comparison_experiment`
   - owner: `run_payoff_comparison_experiment(...)`

### Tier 4 (speculative / future / appendix)

1. `quantum_mapping_comparison_experiment`
   - owner: `run_quantum_mapping_comparison_experiment(...)`

Default local sweep runs Tier 1 and Tier 2; higher tiers are optional.
