# Final Pre-BigRed Hardening Pass — Implementation Summary

## Shortcomings Fixed

### S1: Full-Pipeline Evidence Parity
The full pipeline now emits all 18 canonical research and SLM artifacts, matching the repeated-workload bundle. Where per-request detail is unavailable, artifacts are generated with aggregate data and explicit notes. No artifact is silently omitted.

### S2: Decision Overhead Accounting
New module `overhead_accounting.py` computes per-request overhead decomposition: lookup, similarity search, decision, and validation costs. Net utility is computed at per-request, per-family, and per-run levels. Results flow into research bundles and SLM exports.

### S3: Similarity Validation Control Surface
`ValidationConfig` now supports 6 modes (off, sampled, always, family_conditioned, regime_conditioned, plus legacy aliases). Three tolerance profiles (strict: 1%, moderate: 5%, exploratory: 10%) with per-family defaults. Per-family and per-regime override support. Summary includes false-accept counts and epistemic status.

### S4: Artifact Contract Layer
New module `artifact_contract.py` defines a canonical registry of 18 required artifacts. Each run writes `artifact_contract.json` showing generated/skipped/unavailable status for every artifact. Skipped artifacts emit machine-readable placeholder files with reasons.

### S5: Deeper Cross-Run Aggregation
Aggregation now ingests overhead, speedup bounds, and artifact contract data from each run. New outputs: `per_run_overhead.csv`, claim safety classification (safe/provisional/not_yet_safe), overhead aggregate summaries. Aggregation discovers both repeated-workload and full-pipeline runs.

### S6: Larger BigRed Wave Presets
Three new scale profiles: `long_wave` (~24k requests), `locality_burst` (~5k, hotset-focused), `validation_heavy` (~4k, similarity-focused). New Slurm scripts for all profiles.

### S7: Amdahl/Gustafson Measured Speedup Bounds
New module `speedup_bounds.py` computes Amdahl fixed-size bounds and Gustafson scaled estimates from measured runtime decomposition. Realized gross and net speedup computed. Weak reuse flag set when hit rates < 10%. Outputs: `speedup_bounds.json` and `speedup_bounds.md`.

### S8: SLM Export Quality
SLM schema extended with `decision_overhead_ms`, `gross_runtime_saved_ms`, `net_runtime_saved_ms`, `net_utility_label`. These support downstream classification tasks like "should validate" and "safe to claim reuse."

## Files Created
- `src/qhpc_cache/artifact_contract.py` — Artifact contract layer
- `src/qhpc_cache/overhead_accounting.py` — Overhead + net utility
- `src/qhpc_cache/speedup_bounds.py` — Amdahl/Gustafson analysis
- `scripts/bigred_repeated_long_wave.sh` — Long-wave Slurm script
- `scripts/bigred_validation_heavy.sh` — Validation-heavy Slurm script
- `scripts/bigred_locality_burst.sh` — Locality-burst Slurm script
- `scripts/bigred_full_long_budget.sh` — Full pipeline long-budget script
- `tests/test_hardening_pass.py` — 24 targeted tests
- `docs/artifact_contract_parity.md`
- `docs/net_utility_accounting.md`
- `docs/similarity_validation_modes.md`
- `docs/speedup_interpretation.md`
- `docs/next_wave_bigred_plan.md`
- `docs/hardening_pass_summary.md`

## Files Modified
- `src/qhpc_cache/similarity_validation.py` — Tolerance profiles, modes, false-accept tracking
- `src/qhpc_cache/slm_exports.py` — Overhead fields in schema and export
- `src/qhpc_cache/repeated_workload_study.py` — Overhead, speedup, contract integration
- `src/qhpc_cache/run_aggregation.py` — Overhead/utility/claim-safety aggregation
- `src/qhpc_cache/repeated_workload_generator.py` — New scale profiles
- `run_full_research_pipeline.py` — Full parity research bundle

## What Remains Limited
1. **Full-pipeline per-request granularity**: The full pipeline does not track individual requests through the orchestrator, so per-request overhead and family-level metrics are aggregate-only. The repeated-workload path remains the primary evidence engine.
2. **Similarity candidate generation**: The current cache store uses exact matching only. Similarity candidate generation is a research-grade overlay on signatures/features, not a production lookup system.
3. **Engine availability**: Only `classical_mc` is reliably available. QuantLib, Cirq, and Monaco remain optional and honestly skipped when absent.
4. **Overhead measurement precision**: Overhead is estimated from runtime decomposition rather than instrumented at microsecond precision. This is appropriate for research evidence.

## How to Run

### Local validation
```bash
cd jk
PYTHONPATH=src python3 -m pytest tests/test_hardening_pass.py -v
PYTHONPATH=src python3 -m pytest tests/ -v
```

### Local smoke
```bash
PYTHONPATH=src python3 run_repeated_workload_study.py \
    --lane lane_a --scale-label smoke --seed 42 \
    --output-root /tmp/qhpc_smoke --no-plots --budget-minutes 2
```

### BigRed200 standard
```bash
sbatch scripts/bigred_repeated_standard.sh 42
```

### BigRed200 long wave
```bash
sbatch scripts/bigred_repeated_long_wave.sh 42
```

### Cross-run aggregation
```bash
PYTHONPATH=src python3 scripts/aggregate_research_runs.py \
    outputs/run1 outputs/run2 --output-dir outputs/aggregate
```

## How to Interpret Outputs

1. Check `artifact_contract.json`: `pending == 0` means all artifacts processed
2. Check `research/net_utility_summary.json`: `net_utility_positive` tells you if caching helped
3. Check `research/speedup_bounds.json`: `weak_reuse_flag` tells you if speedup claims are meaningful
4. Check `research/expanded_metrics.json`: `by_family` shows which families benefit
5. Check `research/similarity_validation_summary.json`: `false_accept_count == 0` means approximate reuse is validated

## What Evidence Is Now Stronger
- Overhead is explicitly measured rather than assumed beneficial
- Full pipeline cannot silently omit evidence artifacts
- Cross-run aggregation includes overhead stability analysis
- Claim safety is classified as safe/provisional/not-yet-safe
- Validation control surface enables reproducible experiment design
- Speedup bounds are grounded in measured data, not theoretical upper bounds

## Test Coverage
- 374 tests pass (24 new + 350 existing)
- 2 tests skipped (optional engine availability)
- 0 failures
