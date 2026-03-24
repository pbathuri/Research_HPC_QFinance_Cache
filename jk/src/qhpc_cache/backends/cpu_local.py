"""CPU-local backend: the default execution path for all current workloads."""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Dict

from qhpc_cache.backends.base import BackendCapabilities, BaseBackend, ExecutionPlan


class CpuLocalBackend(BaseBackend):
    """Runs pricing / simulation / analytics on the local CPU with stdlib + numpy."""

    def capabilities(self) -> BackendCapabilities:
        cores = os.cpu_count() or 1
        return BackendCapabilities(
            name="cpu_local",
            can_execute=True,
            max_parallel_paths=cores,
            notes=f"{cores} logical cores available",
        )

    def validate(self) -> bool:
        return True

    def build_plan(self, task_type: str, params: Dict[str, Any], *, dry_run: bool = False) -> ExecutionPlan:
        param_hash = hashlib.sha256(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()[:12]
        num_paths = params.get("num_paths", 10_000)
        est_time = max(0.01, num_paths / 500_000)
        est_mem = num_paths * 64
        return ExecutionPlan(
            plan_id=f"cpu_{param_hash}",
            backend_name="cpu_local",
            task_type=task_type,
            parameters=params,
            estimated_runtime_seconds=round(est_time, 3),
            estimated_memory_bytes=est_mem,
            dry_run=dry_run,
        )

    def execute(self, plan: ExecutionPlan) -> Dict[str, Any]:
        if plan.dry_run:
            return {"status": "dry_run", "summary": self.dry_run_summary(plan), "artifacts": []}
        start = time.perf_counter()
        result: Dict[str, Any] = {
            "status": "ok",
            "backend": "cpu_local",
            "plan_id": plan.plan_id,
            "wall_clock_seconds": 0.0,
            "artifacts": plan.artifacts,
        }
        result["wall_clock_seconds"] = round(time.perf_counter() - start, 4)
        return result

    def dry_run_summary(self, plan: ExecutionPlan) -> str:
        cap = self.capabilities()
        return (
            f"[cpu_local] task={plan.task_type}  paths={plan.parameters.get('num_paths', '?')}  "
            f"est_time={plan.estimated_runtime_seconds:.2f}s  est_mem={plan.estimated_memory_bytes // 1024}KB  "
            f"cores={cap.max_parallel_paths}"
        )
