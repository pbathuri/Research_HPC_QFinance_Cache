"""MPI distributed backend placeholder: interface complete, execution deferred.

When mpi4py is available and the run is launched under ``mpiexec``, implement
``execute()`` to scatter path batches across ranks and gather results.
"""

from __future__ import annotations

from typing import Any, Dict

from qhpc_cache.backends.base import BackendCapabilities, BaseBackend, ExecutionPlan


class MpiPlaceholderBackend(BaseBackend):

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            name="mpi_placeholder",
            backend_kind="hpc_mpi_future",
            execution_environment="hpc",
            execution_mode_intent="mpi_batch_slurm",
            can_execute=False,
            supports_mpi=True,
            supports_batch_scheduler=True,
            hpc_ready=False,
            mpi_ready=False,
            gpu_ready=False,
            max_parallel_paths=0,
            notes="MPI backend not yet implemented; requires mpi4py and mpiexec launch.",
        )

    def validate(self) -> bool:
        try:
            from mpi4py import MPI  # type: ignore  # noqa: F401
            return MPI.COMM_WORLD.Get_size() > 1
        except ImportError:
            return False

    def build_plan(self, task_type: str, params: Dict[str, Any], *, dry_run: bool = False) -> ExecutionPlan:
        num_paths = params.get("num_paths", 100_000)
        ranks = params.get("mpi_ranks", 4)
        return ExecutionPlan(
            plan_id=f"mpi_{task_type}_{ranks}r",
            backend_name="mpi_placeholder",
            task_type=task_type,
            requested_backend="mpi_placeholder",
            execution_environment_intent="hpc",
            execution_mode_intent="mpi_batch_slurm",
            execution_mode_actual="deferred_to_hpc",
            parameters={**params, "mpi_ranks": ranks},
            estimated_runtime_seconds=max(0.01, num_paths / (ranks * 500_000)),
            estimated_memory_bytes=num_paths * 64,
            dry_run=True,
            notes=f"Placeholder: would scatter {num_paths} paths across {ranks} ranks.",
        )

    def execute(self, plan: ExecutionPlan) -> Dict[str, Any]:
        return {
            "status": "not_implemented",
            "backend": "mpi_placeholder",
            "message": "MPI execution requires mpi4py and mpiexec launch. Use cpu_local.",
        }

    def dry_run_summary(self, plan: ExecutionPlan) -> str:
        ranks = plan.parameters.get("mpi_ranks", 4)
        return (
            f"[mpi_placeholder] task={plan.task_type}  "
            f"paths={plan.parameters.get('num_paths', '?')}  ranks={ranks}  "
            f"WOULD scatter-gather across MPI communicator."
        )
