"""MPI decomposition specs for HPC readiness (no MPI execution here)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class MpiDecompositionSpec:
    workload_id: str
    split_dimension: str
    total_units: int
    mpi_ranks: int
    reduction_step: str
    output_schema_stable: bool
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workload_id": self.workload_id,
            "split_dimension": self.split_dimension,
            "total_units": int(self.total_units),
            "mpi_ranks": int(self.mpi_ranks),
            "reduction_step": self.reduction_step,
            "output_schema_stable": bool(self.output_schema_stable),
            "notes": self.notes,
        }


def build_mpi_decomposition_specs(
    *,
    mpi_ranks: int = 16,
) -> List[MpiDecompositionSpec]:
    """Return canonical decomposition plans for first HPC-bound workloads."""
    ranks = max(1, int(mpi_ranks))
    return [
        MpiDecompositionSpec(
            workload_id="repeated_workload_study",
            split_dimension="request_index_chunks",
            total_units=0,
            mpi_ranks=ranks,
            reduction_step=(
                "Per-rank result CSVs merged by stable row schema; aggregate cache/timing summaries recomputed centrally."
            ),
            output_schema_stable=True,
            notes="Natural split: lane x family x request index windows.",
        ),
        MpiDecompositionSpec(
            workload_id="qmc_simulation_convergence",
            split_dimension="(contract_index, path_count_index) grid",
            total_units=0,
            mpi_ranks=ranks,
            reduction_step=(
                "Rank-local pricing logs concatenated; convergence summary reduced via weighted means/quantiles."
            ),
            output_schema_stable=True,
            notes="Natural split: convergence ladder points and contracts.",
        ),
        MpiDecompositionSpec(
            workload_id="pricing_workload_family",
            split_dimension="contract_batch_id",
            total_units=0,
            mpi_ranks=ranks,
            reduction_step=(
                "Rank-local model-family outputs merged by model_family, batch_id, contract_id."
            ),
            output_schema_stable=True,
            notes="Natural split: model-family x contract-batch.",
        ),
    ]

