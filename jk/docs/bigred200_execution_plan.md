# BigRed200 Execution Plan (Slurm-First Integration Readiness)

This phase provides a **real submission-artifact path** for BigRed200 without
claiming production cluster execution is already complete.

## What is now concrete

- Slurm-first backend (`slurm_bigred200`) generates:
  - `.sbatch.sh` submission script
  - `.slurm_job_manifest.json`
  - `.workload_to_slurm_mapping.csv`
  - `.backend_readiness.md`
- QMC simulation can run in **deferred-to-HPC mode**:
  - local run writes submission artifacts only
  - no fake compute results are produced
  - summary includes requested vs executed backend provenance
- BigRed200 environment verification:
  - Python **3.12.11** confirmed
  - editable install confirmed (`pip install -e .`)
  - scientific stack confirmed for test runs:
    `numpy`, `pandas`, `matplotlib`, `scipy`, `scikit-learn`, `pytest`
  - active smoke commands confirmed:
    - `python run_full_research_pipeline.py --mode experiment_batch --budget 0.25 --output-root outputs/hpc_smoke`
    - `python run_repeated_workload_study.py --scale-label smoke --lane both --output-root outputs/hpc_repeat_smoke`

## Canonical first BigRed200 candidates

1. Repeated workload study at larger scales (`lane_a` + `lane_b`)
2. QMC convergence ladders with larger path grids
3. Pricing workload family with larger contract-batch expansion
4. Event-library comparison with wider event/window combinations
5. Feature-panel comparison with larger universe/date slices

## Local vs HPC split

- Keep local:
  - operator validation
  - smoke-scale correctness checks
  - schema compatibility checks
- Shift to BigRed200:
  - large path-count ladders
  - large event-window cross-products
  - large contract-grid pricing batches
  - repeated workload heavy-scale replay

## Slurm resource surface (supported now)

- `job_name`
- `walltime`
- `partition`
- `nodes`
- `ntasks`
- `cpus_per_task`
- `mem`
- `output_log`
- `error_log`
- optional: `account`, `constraint`, `qos`

## Current truth boundary

- CPU batch planning via Slurm artifacts: **ready**
- MPI decomposition strategy: **defined**, not cluster-executed in-repo
- CUDA execution path: **not implemented** (candidate-only)
- PMU hardware-counter validation: **deferred to BigRed200/x86 execution**
- Optional quantum engines (`quantlib_mc`, `cirq_qmci`, `monaco_mc`) are marked
  available only when dependencies are present (or when an explicit fallback is
  active for the invoked method); otherwise tests skip, not fail.
- Current cluster-validated active engine is `classical_mc`.
- Archived `old_pipeline_work` WRDS placeholder code is non-canonical and is not
  part of active package tests unless a deliberate compatibility shim is added.
