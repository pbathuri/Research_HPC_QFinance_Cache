# BigRed200 Execution Truthfulness

## Overview

This document establishes what BigRed200 execution does and does not prove about the research system's results. HPC execution provides real timing on production hardware, but claims must be scoped to what was actually measured.

## What BigRed200 Execution Proves

- **CPU timing fidelity**: Pricing compute times on AMD EPYC nodes are representative of production-class hardware, unlike laptop timings.
- **Engine availability**: Whether optional engines (QuantLib, Cirq, Monaco) can be installed and loaded on the cluster.
- **Pipeline integrity**: The full orchestration works end-to-end in a batch compute environment.
- **Reproducibility**: Deterministic seeds produce identical results across runs.

## What BigRed200 Execution Does NOT Prove

- **Distributed scaling**: Unless MPI or multi-node execution is explicitly configured and verified, results reflect single-node, single-process computation.
- **GPU acceleration**: No GPU-accelerated results should be claimed unless a CUDA-capable engine is verified.
- **Production latency**: Network, I/O, and scheduling overhead in real trading systems are not modeled.
- **Memory scaling**: In-memory cache behavior may differ from distributed cache systems.

## Provenance Fields

Every output includes `hpc_execution_summary.json` with:

| Field | Meaning |
|---|---|
| `physical_execution_context` | `local_workstation`, `bigred200_login_node`, `slurm_batch`, `slurm_array_task` |
| `cluster_name` | Cluster identifier (e.g., `bigred200`) |
| `slurm_job_id` | Slurm job ID if running in a batch allocation |
| `slurm_cpus_allocated` | CPUs available to the job |
| `backend_execution_mode` | How the code actually executed |

## Interpreting Execution Contexts

### `local_workstation`
Results are for development/debugging only. Timing is not representative.

### `bigred200_login_node`
WARNING: Login node execution should not be used for research results. It shares resources with other users and has unpredictable timing.

### `slurm_batch`
Valid for research. Single-node batch allocation with dedicated resources.

### `slurm_array_task`
Valid for seed sweeps and ensemble statistics. Each task runs independently.

## Budget Utilization Truthfulness

Runs often complete well before the requested budget. This is reported in `budget_utilization`:
- `workload_exhausted_before_budget`: The workload had fewer requests than the budget could support.
- `budget_exhausted`: The budget was the binding constraint.
- `pricing_cap_reached`: A safety cap on total pricings was reached.

This is not a failure. It is an honest reflection of workload size vs. budget.
