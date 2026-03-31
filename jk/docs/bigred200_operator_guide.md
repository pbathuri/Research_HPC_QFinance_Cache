# BigRed200 Operator Guide (Slurm-First)

This guide documents the current **integration-readiness** path from local runs
to BigRed200 submission artifacts.

## 1) Local artifact generation

Run from `jk/`:

```bash
PYTHONPATH=src python3 run_full_research_pipeline.py \
  --mode experiment_batch \
  --requested-backend bigred200_mpi_batch \
  --defer-execution-to-hpc \
  --slurm-job-name qhpc_qmc_mpi \
  --slurm-walltime 02:00:00 \
  --slurm-partition general \
  --slurm-nodes 2 \
  --slurm-ntasks 64 \
  --slurm-cpus-per-task 1 \
  --slurm-mem 128G
```

Result: run-scoped `hpc_submission/` directory with Slurm script + manifest +
mapping CSV.

## 2) Expected directory layout

- `outputs/Output_<timestamp>/`
  - `run_manifest.json`
  - `qmc_simulation/qmc_run_summary.json`
  - `hpc_submission/`
    - `<plan_id>.sbatch.sh`
    - `<plan_id>.slurm_job_manifest.json`
    - `<plan_id>.workload_to_slurm_mapping.csv`
    - `<plan_id>.backend_readiness.md`

## 3) Stage inputs and outputs

- Inputs: existing local data registry and workload configs
- Outputs: submission artifacts only (when deferred mode enabled)
- No synthetic/fake HPC results are produced in deferred mode

### Cluster-validated smoke commands

The following smoke runs are validated on BigRed200 with Python 3.12.11:

```bash
python run_full_research_pipeline.py --mode experiment_batch --budget 0.25 --output-root outputs/hpc_smoke
python run_repeated_workload_study.py --scale-label smoke --lane both --output-root outputs/hpc_repeat_smoke
```

## 4) BigRed200 environment assumptions

- Slurm available (`sbatch`, `srun`)
- Python **3.12.11** module available (verified)
- Editable install works (`pip install -e .`)
- Scientific stack required for cluster tests is installed:
  - `numpy`
  - `pandas`
  - `matplotlib`
  - `scipy`
  - `scikit-learn`
  - `pytest`
- OpenMPI module available for MPI-intent jobs
- Same repository revision staged on cluster

## 5) Optional quantum engine truthfulness policy

- `quantlib_mc`, `cirq_qmci`, and `monaco_mc` are optional engines.
- An engine is counted as available only when its dependency is actually importable
  (or when an explicit fallback path exists and is active for that method).
- If an optional dependency is missing, engine tests skip cleanly rather than
  claiming availability.
- NaN-valued error results are never treated as successful engine runs.
- Current cluster-validated active engine is `classical_mc`.
- Archived `old_pipeline_work` modules (including `wrds_placeholder`) are not part
  of the active canonical package unless a deliberate legacy shim is reintroduced.

## 6) On-cluster submission flow

1. Copy run `hpc_submission/` artifacts to cluster work directory.
1. Verify module names/partition/account against site policy.
1. Submit:

```bash
sbatch <plan_id>.sbatch.sh
```

1. Collect resulting logs and output folders.
1. Sync back to local repository outputs for forensics and paper packaging.

## 7) Unsupported in this phase

- Automatic remote submission from local machine
- In-repo MPI rank launcher execution on BigRed200
- In-repo CUDA kernel execution
- In-repo PMU hardware-counter runs on cluster

## 8) CPU vs MPI vs GPU status

- CPU batch via Slurm artifacts: ready
- MPI decomposition-ready (split/reduce specs documented): ready for execution planning
- GPU path: future-only candidate path
