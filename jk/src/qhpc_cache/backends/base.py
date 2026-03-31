"""Abstract backend interface and execution-plan contract.

Every backend (CPU, CUDA, MPI, Slurm) implements a shared contract so upper
layers can report requested vs executed execution modes honestly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BackendCapabilities:
    """Declarative flag set describing what a backend supports today."""
    name: str
    backend_kind: str = "cpu_local"
    execution_environment: str = "local"
    execution_mode_intent: str = "cpu_single_node"
    can_execute: bool = False
    supports_gpu: bool = False
    supports_mpi: bool = False
    supports_batch_scheduler: bool = False
    hpc_ready: bool = False
    mpi_ready: bool = False
    gpu_ready: bool = False
    max_parallel_paths: int = 1
    notes: str = ""


@dataclass
class SlurmResourceSpec:
    """Minimal Slurm request block used for BigRed200 submission artifacts."""

    job_name: str = "qhpc_job"
    walltime: str = "01:00:00"
    partition: str = "general"
    nodes: int = 1
    ntasks: int = 1
    cpus_per_task: int = 1
    mem: str = "16G"
    output_log: str = "slurm_%j.out"
    error_log: str = "slurm_%j.err"
    account: str = ""
    constraint: str = ""
    qos: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_name": str(self.job_name),
            "walltime": str(self.walltime),
            "partition": str(self.partition),
            "nodes": int(self.nodes),
            "ntasks": int(self.ntasks),
            "cpus_per_task": int(self.cpus_per_task),
            "mem": str(self.mem),
            "output_log": str(self.output_log),
            "error_log": str(self.error_log),
            "account": str(self.account),
            "constraint": str(self.constraint),
            "qos": str(self.qos),
        }


@dataclass
class ExecutionPlan:
    """A serializable plan that any backend can inspect or run."""
    plan_id: str
    backend_name: str
    task_type: str
    requested_backend: str = "cpu_local"
    execution_environment_intent: str = "local"
    execution_mode_intent: str = "cpu_single_node"
    execution_mode_actual: str = "cpu_single_node"
    parameters: Dict[str, Any] = field(default_factory=dict)
    estimated_runtime_seconds: float = 0.0
    estimated_memory_bytes: int = 0
    dry_run: bool = False
    slurm: Optional[SlurmResourceSpec] = None
    artifacts: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "plan_id": str(self.plan_id),
            "backend_name": str(self.backend_name),
            "task_type": str(self.task_type),
            "requested_backend": str(self.requested_backend),
            "execution_environment_intent": str(self.execution_environment_intent),
            "execution_mode_intent": str(self.execution_mode_intent),
            "execution_mode_actual": str(self.execution_mode_actual),
            "parameters": dict(self.parameters),
            "estimated_runtime_seconds": float(self.estimated_runtime_seconds),
            "estimated_memory_bytes": int(self.estimated_memory_bytes),
            "dry_run": bool(self.dry_run),
            "artifacts": list(self.artifacts),
            "notes": str(self.notes),
        }
        if self.slurm is not None:
            payload["slurm"] = self.slurm.to_dict()
        return payload


class BaseBackend(ABC):
    """Interface contract for all execution backends."""

    @abstractmethod
    def capabilities(self) -> BackendCapabilities:
        ...

    @abstractmethod
    def validate(self) -> bool:
        """Return True if this backend is ready for execution."""
        ...

    @abstractmethod
    def build_plan(self, task_type: str, params: Dict[str, Any], *, dry_run: bool = False) -> ExecutionPlan:
        ...

    @abstractmethod
    def execute(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Run the plan and return a result dict with at least 'status' and 'artifacts'."""
        ...

    @abstractmethod
    def dry_run_summary(self, plan: ExecutionPlan) -> str:
        """Human-readable description of what the plan would do."""
        ...
