# Backend Templates

## Interface Contract

All backends implement `BaseBackend` from `backends/base.py`:

```python
class BaseBackend(ABC):
    def capabilities(self) -> BackendCapabilities: ...
    def validate(self) -> bool: ...
    def build_plan(self, task_type, params, *, dry_run=False) -> ExecutionPlan: ...
    def execute(self, plan: ExecutionPlan) -> Dict[str, Any]: ...
    def dry_run_summary(self, plan: ExecutionPlan) -> str: ...
```

## Current Backends

### cpu_local (IMPLEMENTED)
- Runs all pricing, simulation, and analytics on local CPU.
- Always validates True.
- Used as the default for all current experiments.

### cuda_placeholder (SCAFFOLD)
- Interface complete; `execute()` returns `not_implemented`.
- `validate()` checks for `cupy` availability.
- When implemented: offload GBM path simulation to GPU kernels.
- Estimated speedup: 10-50x for large path counts (> 100K).

### mpi_placeholder (SCAFFOLD)
- Interface complete; `execute()` returns `not_implemented`.
- `validate()` checks for `mpi4py` and multi-rank communicator.
- When implemented: scatter path batches across MPI ranks, gather results.

### slurm_bigred200 (TEMPLATE GENERATION)
- Cannot execute directly; generates `sbatch` script templates.
- Templates include module loads, node/task counts, time limits.
- Submit manually on BigRed200: `sbatch <generated_script.sh>`

## Adding a New Backend

1. Create `backends/my_backend.py` implementing `BaseBackend`.
2. Set `can_execute=True` in capabilities when ready.
3. Register in `validate_local_resources.py` probe list.
4. The orchestrator will select backends via `state.backend_name`.
