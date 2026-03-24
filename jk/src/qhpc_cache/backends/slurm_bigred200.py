"""Slurm / BigRed200 backend placeholder: job-template generation for IU cluster.

Generates a ``sbatch`` script template that can be submitted manually.  Does not
submit jobs directly (requires SSH or on-cluster execution).
"""

from __future__ import annotations

import textwrap
from typing import Any, Dict

from qhpc_cache.backends.base import BackendCapabilities, BaseBackend, ExecutionPlan


_SBATCH_TEMPLATE = textwrap.dedent("""\
    #!/bin/bash
    #SBATCH --job-name=qhpc_{task_type}
    #SBATCH --partition=general
    #SBATCH --nodes={nodes}
    #SBATCH --ntasks-per-node={tasks_per_node}
    #SBATCH --time={time_limit}
    #SBATCH --mem={mem_gb}G
    #SBATCH --output=slurm_%j.out

    module load python/3.11
    module load openmpi/4.1

    cd $SLURM_SUBMIT_DIR
    srun python3 -m qhpc_cache.experiment_runner --plan {plan_id}
""")


class SlurmBigRed200Backend(BaseBackend):

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            name="slurm_bigred200",
            can_execute=False,
            supports_mpi=True,
            supports_batch_scheduler=True,
            max_parallel_paths=0,
            notes="Generates sbatch templates for BigRed200; does not submit directly.",
        )

    def validate(self) -> bool:
        return False

    def build_plan(self, task_type: str, params: Dict[str, Any], *, dry_run: bool = False) -> ExecutionPlan:
        num_paths = params.get("num_paths", 1_000_000)
        nodes = params.get("nodes", 2)
        tasks = params.get("tasks_per_node", 32)
        return ExecutionPlan(
            plan_id=f"slurm_{task_type}_{nodes}n",
            backend_name="slurm_bigred200",
            task_type=task_type,
            parameters={**params, "nodes": nodes, "tasks_per_node": tasks},
            estimated_runtime_seconds=max(1.0, num_paths / (nodes * tasks * 500_000)),
            estimated_memory_bytes=num_paths * 64 * nodes,
            dry_run=True,
            notes=f"BigRed200 template: {nodes} nodes x {tasks} tasks/node.",
        )

    def execute(self, plan: ExecutionPlan) -> Dict[str, Any]:
        script = self._render_sbatch(plan)
        return {
            "status": "template_generated",
            "backend": "slurm_bigred200",
            "sbatch_script": script,
            "message": "Submit this script on BigRed200 with: sbatch <script.sh>",
        }

    def dry_run_summary(self, plan: ExecutionPlan) -> str:
        p = plan.parameters
        return (
            f"[slurm_bigred200] task={plan.task_type}  "
            f"paths={p.get('num_paths', '?')}  "
            f"nodes={p.get('nodes', 2)} x tasks={p.get('tasks_per_node', 32)}  "
            f"WOULD generate sbatch script for BigRed200."
        )

    def _render_sbatch(self, plan: ExecutionPlan) -> str:
        p = plan.parameters
        return _SBATCH_TEMPLATE.format(
            task_type=plan.task_type,
            nodes=p.get("nodes", 2),
            tasks_per_node=p.get("tasks_per_node", 32),
            time_limit=p.get("time_limit", "01:00:00"),
            mem_gb=p.get("mem_gb", 64),
            plan_id=plan.plan_id,
        )
