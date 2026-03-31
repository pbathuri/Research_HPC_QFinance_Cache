# Final Research Runbook

## Overview

This runbook describes how to produce defensible, paper-grade cache research evidence using the qhpc_cache system on BigRed200.

## Pre-Flight Checklist

1. **Environment**: Python 3.10+, virtual environment activated
2. **Dependencies**: `pip install -r requirements.txt` (includes numpy, matplotlib)
3. **Engine availability**: Run `PYTHONPATH=src python3 -c "from qhpc_cache.hpc_provenance import detect_available_engines; print(detect_available_engines())"`
4. **Cluster context**: Verify you're on a compute node, not a login node

## Run Profiles

### Smoke Validation (5 min)
```bash
PYTHONPATH=src python3 run_repeated_workload_study.py \
  --profile smoke_cluster_validation \
  --output-root outputs/smoke_validation
```

### Finance Reuse Standard (30 min)
```bash
PYTHONPATH=src python3 run_repeated_workload_study.py \
  --profile finance_reuse_standard \
  --output-root outputs/finance_reuse_standard \
  --budget-minutes 30
```

### Finance Reuse Heavy (2+ hours)
```bash
PYTHONPATH=src python3 run_repeated_workload_study.py \
  --profile finance_reuse_heavy \
  --output-root outputs/finance_reuse_heavy \
  --budget-minutes 120
```

### Similarity Validation Grid (1 hour)
```bash
PYTHONPATH=src python3 run_repeated_workload_study.py \
  --profile similarity_validation_grid \
  --output-root outputs/similarity_validation
```

### Long Budget Full (4+ hours)
```bash
PYTHONPATH=src python3 run_repeated_workload_study.py \
  --profile long_budget_full \
  --output-root outputs/long_budget_full \
  --budget-minutes 240
```

### Seed Sweep Array (Slurm)
```bash
# Generate Slurm script
PYTHONPATH=src python3 run_repeated_workload_study.py \
  --generate-slurm repeated_array_seed_sweep \
  --slurm-account YOUR_ACCOUNT

# Submit
sbatch slurm_repeated_array_seed_sweep.sbatch.sh
```

### Multi-Run Aggregation
```bash
PYTHONPATH=src python3 aggregate_runs.py \
  --glob "outputs/repeated_workload_seed_*" \
  --output-dir outputs/aggregated_evidence
```

## Interpreting Outputs

### Key files to check first:
1. `evidence/cache_evidence_summary.md` - Human-readable evidence overview
2. `hpc_execution_summary.md` - Execution provenance
3. `repeated_workload_rankings_summary.md` - Family comparison

### Evidence quality checklist:
- [ ] `net_benefit_flag` is True for reuse-friendly families
- [ ] `net_benefit_flag` is False for stress controls (expected)
- [ ] `locality_regime` is sensible for each family
- [ ] `budget_utilization_fraction` and `termination_reason` are reported
- [ ] Engine availability is documented with reason codes
- [ ] Exact and similarity hits are decomposed (never merged)

### Red flags:
- Zero hits on `exact_repeat_pricing` lane_a (should have high reuse)
- Positive `net_cache_value_ms` on `stress_churn_pricing` lane_b (cache shouldn't help)
- `physical_execution_context` is `bigred200_login_node` for production results

## Full Pipeline Run

The full research pipeline includes data ingestion, QMC simulation, and reporting:

```bash
PYTHONPATH=src python3 run_full_research_pipeline.py \
  --mode full \
  --budget 120 \
  --requested-backend cpu_local
```

Add `--defer-execution-to-hpc` to generate Slurm artifacts without local execution.

## Test Validation

```bash
cd jk
PYTHONPATH=src python3 -m pytest tests/test_evidence_layer.py -v
PYTHONPATH=src python3 -m pytest tests/test_repeated_workload_study.py -v
PYTHONPATH=src python3 -m pytest tests/ -v --timeout=120
```
