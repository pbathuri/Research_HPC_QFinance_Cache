# Next-Wave BigRed200 Execution Plan

## Context

Previous BigRed runs demonstrated:
- Pipeline is operational on BigRed200
- Only `classical_mc` is available; other engines are honestly skipped
- Full-pipeline runs complete quickly (~26s) because workload volume is insufficient
- Repeated-workload studies are the strongest evidence path

## Available Scale Profiles

| Profile | Total Requests (est.) | Purpose |
|---------|----------------------|---------|
| `smoke` | ~240 | Quick validation |
| `standard` | ~2,000 | Standard research run |
| `heavy` | ~12,000 | Full evidence generation |
| `long_wave` | ~24,000 | Sustained locality stress |
| `locality_burst` | ~5,000 | Hotset/overlap focused |
| `validation_heavy` | ~4,000 | High validation coverage |

## Recommended Run Matrix

### Phase 1: Validation (same day)
```bash
# Smoke validation
sbatch scripts/bigred_repeated_standard.sh 42
```

### Phase 2: Standard evidence wave
```bash
# Standard with 5-seed sweep
sbatch scripts/bigred_seed_array.sh
```

### Phase 3: Heavy and long-wave
```bash
# Heavy wave
sbatch scripts/bigred_repeated_heavy.sh 42

# Long wave for sustained locality
sbatch scripts/bigred_repeated_long_wave.sh 42
```

### Phase 4: Specialized profiles
```bash
# Locality burst
sbatch scripts/bigred_locality_burst.sh 42

# Validation heavy (high recomputation coverage)
sbatch scripts/bigred_validation_heavy.sh 42
```

### Phase 5: Full pipeline long budget
```bash
sbatch scripts/bigred_full_long_budget.sh 180
```

### Phase 6: Cross-run aggregation (local)
```bash
PYTHONPATH=src python3 scripts/aggregate_research_runs.py \
    outputs/bigred_seed_array_*/seed_* \
    outputs/bigred_rws_heavy_* \
    --output-dir outputs/aggregate_bigred_wave2
```

## What Each Profile Exercises

### `long_wave`
- ~24,000 requests across 11 families
- Sustained hotset recurrence patterns
- Observable working-set growth and contraction
- Phase transitions between calm and stressed regimes
- Ideal for reuse-distance distribution analysis

### `locality_burst`
- Overweights families with strong locality: hotset, overlapping windows, rolling horizon, intraday ladders
- Underweights churn and stress families
- Designed to produce measurable positive cache utility

### `validation_heavy`
- Overweights parameter shock grid and similarity-rich families
- Produces more validation samples for tolerance analysis
- Ideal for similarity acceptance quality assessment

## Expected Runtime

| Profile | Estimated Runtime | Walltime Requested |
|---------|------------------|--------------------|
| standard | 10-30 min | 2 hours |
| heavy | 30-90 min | 4 hours |
| long_wave | 60-180 min | 6 hours |
| locality_burst | 10-30 min | 2 hours |
| validation_heavy | 15-45 min | 3 hours |

## Interpreting Results

After each run, check:
1. `artifact_contract.json` — all artifacts generated or skipped with reason
2. `research/net_utility_summary.json` — was caching net beneficial?
3. `research/speedup_bounds.json` — what are the theoretical and realized bounds?
4. `research/expanded_metrics.json` — which families showed reuse?
5. `research/similarity_validation_summary.json` — validation quality

After aggregation, check:
1. `aggregate_research_summary.json` — cross-run stability
2. `claim_support_matrix.csv` — which claims are safe to make
3. `per_run_overhead.csv` — overhead consistency across runs
