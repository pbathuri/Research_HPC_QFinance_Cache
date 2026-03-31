"""Execution backends and minimal backend selection helpers."""

from __future__ import annotations

from typing import Dict

from qhpc_cache.backends.base import BaseBackend
from qhpc_cache.backends.cpu_local import CpuLocalBackend
from qhpc_cache.backends.cuda_placeholder import CudaPlaceholderBackend
from qhpc_cache.backends.mpi_runner_spec import (
    MpiDecompositionSpec,
    build_mpi_decomposition_specs,
)
from qhpc_cache.backends.mpi_placeholder import MpiPlaceholderBackend
from qhpc_cache.backends.slurm_bigred200 import SlurmBigRed200Backend

BACKEND_ALIASES: Dict[str, str] = {
    "cpu_local": "cpu_local",
    "local_cpu": "cpu_local",
    "slurm_bigred200": "slurm_bigred200",
    "bigred200_cpu_batch": "slurm_bigred200",
    "bigred200_mpi_batch": "slurm_bigred200",
    "bigred200_gpu_future": "slurm_bigred200",
    "mpi_placeholder": "mpi_placeholder",
    "cuda_placeholder": "cuda_placeholder",
}

BACKEND_DEFAULT_MODE_INTENT: Dict[str, str] = {
    "cpu_local": "cpu_single_node",
    "slurm_bigred200": "cpu_batch_slurm",
    "bigred200_cpu_batch": "cpu_batch_slurm",
    "bigred200_mpi_batch": "mpi_batch_slurm",
    "bigred200_gpu_future": "gpu_batch_slurm",
    "mpi_placeholder": "mpi_batch_slurm",
    "cuda_placeholder": "gpu_batch_slurm",
}


def normalize_backend_name(name: str) -> str:
    """Resolve user-facing aliases to concrete backend implementation IDs."""
    key = str(name or "cpu_local").strip().lower()
    return BACKEND_ALIASES.get(key, "cpu_local")


def default_mode_intent_for_backend(name: str) -> str:
    key = str(name or "cpu_local").strip().lower()
    return BACKEND_DEFAULT_MODE_INTENT.get(key, "cpu_single_node")


def create_backend(name: str) -> BaseBackend:
    """Instantiate a backend from canonical name or accepted alias."""
    canonical = normalize_backend_name(name)
    if canonical == "cpu_local":
        return CpuLocalBackend()
    if canonical == "slurm_bigred200":
        return SlurmBigRed200Backend()
    if canonical == "mpi_placeholder":
        return MpiPlaceholderBackend()
    if canonical == "cuda_placeholder":
        return CudaPlaceholderBackend()
    return CpuLocalBackend()


__all__ = [
    "BaseBackend",
    "CpuLocalBackend",
    "CudaPlaceholderBackend",
    "MpiPlaceholderBackend",
    "MpiDecompositionSpec",
    "SlurmBigRed200Backend",
    "build_mpi_decomposition_specs",
    "create_backend",
    "normalize_backend_name",
    "default_mode_intent_for_backend",
]
