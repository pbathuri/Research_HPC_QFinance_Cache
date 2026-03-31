"""CUDA backend placeholder: interface is complete, execution deferred to GPU availability.

When CUDA (cupy, numba.cuda, or PyCUDA) becomes available, implement ``execute()``
to offload path simulation to GPU kernels.  The plan builder already estimates
memory and parallelism.
"""

from __future__ import annotations

from typing import Any, Dict

from qhpc_cache.backends.base import BackendCapabilities, BaseBackend, ExecutionPlan


class CudaPlaceholderBackend(BaseBackend):

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            name="cuda_placeholder",
            backend_kind="hpc_gpu_future",
            execution_environment="hpc",
            execution_mode_intent="gpu_batch_slurm",
            can_execute=False,
            supports_gpu=True,
            hpc_ready=False,
            mpi_ready=False,
            gpu_ready=False,
            max_parallel_paths=0,
            notes="CUDA backend not yet implemented; GPU kernel integration pending.",
        )

    def validate(self) -> bool:
        try:
            import cupy  # type: ignore  # noqa: F401
            return True
        except ImportError:
            return False

    def build_plan(self, task_type: str, params: Dict[str, Any], *, dry_run: bool = False) -> ExecutionPlan:
        num_paths = params.get("num_paths", 100_000)
        return ExecutionPlan(
            plan_id=f"cuda_{task_type}",
            backend_name="cuda_placeholder",
            task_type=task_type,
            requested_backend="cuda_placeholder",
            execution_environment_intent="hpc",
            execution_mode_intent="gpu_batch_slurm",
            execution_mode_actual="deferred_to_hpc",
            parameters=params,
            estimated_runtime_seconds=max(0.001, num_paths / 10_000_000),
            estimated_memory_bytes=num_paths * 32,
            dry_run=True,
            notes="Placeholder: actual kernel dispatch not implemented.",
        )

    def execute(self, plan: ExecutionPlan) -> Dict[str, Any]:
        return {
            "status": "not_implemented",
            "backend": "cuda_placeholder",
            "message": "CUDA execution requires GPU kernel implementation. Use cpu_local.",
        }

    def dry_run_summary(self, plan: ExecutionPlan) -> str:
        return (
            f"[cuda_placeholder] task={plan.task_type}  "
            f"paths={plan.parameters.get('num_paths', '?')}  "
            f"WOULD offload to GPU if implemented.  "
            f"Estimated speedup: ~10-50x over CPU for large path counts."
        )
