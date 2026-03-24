"""Abstract backend interface and execution-plan contract.

Every backend (CPU, CUDA, MPI, Slurm) implements the same interface so that
upper-layer code (experiment runner, orchestrator) never hard-codes a specific
execution strategy.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BackendCapabilities:
    """Declarative flag set describing what a backend supports today."""
    name: str
    can_execute: bool = False
    supports_gpu: bool = False
    supports_mpi: bool = False
    supports_batch_scheduler: bool = False
    max_parallel_paths: int = 1
    notes: str = ""


@dataclass
class ExecutionPlan:
    """A serializable plan that any backend can inspect or run."""
    plan_id: str
    backend_name: str
    task_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    estimated_runtime_seconds: float = 0.0
    estimated_memory_bytes: int = 0
    dry_run: bool = False
    artifacts: List[str] = field(default_factory=list)
    notes: str = ""


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
