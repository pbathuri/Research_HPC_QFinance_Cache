"""HPC utilization decomposition and parallelization analysis.

Breaks down wall-clock time into:
- useful compute
- orchestration overhead
- I/O overhead
- serial bottleneck share
- core underutilization estimate
- parallelizable fraction estimate (Amdahl's law)

Designed so HPC runs analytically expose their efficiency (or lack thereof).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class UtilizationBreakdown:
    """Time decomposition for one run."""

    total_wall_clock_ms: float
    total_compute_ms: float
    total_lookup_ms: float
    total_cache_put_ms: float
    total_plot_io_ms: float
    total_serialization_ms: float
    orchestration_overhead_ms: float
    unaccounted_ms: float
    compute_fraction: float
    overhead_fraction: float
    serial_bottleneck_fraction: float
    parallelizable_fraction_estimate: float
    cpus_allocated: int
    effective_parallelism: float
    core_utilization_ratio: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_wall_clock_ms": round(self.total_wall_clock_ms, 2),
            "total_compute_ms": round(self.total_compute_ms, 2),
            "total_lookup_ms": round(self.total_lookup_ms, 2),
            "total_cache_put_ms": round(self.total_cache_put_ms, 2),
            "total_plot_io_ms": round(self.total_plot_io_ms, 2),
            "total_serialization_ms": round(self.total_serialization_ms, 2),
            "orchestration_overhead_ms": round(self.orchestration_overhead_ms, 2),
            "unaccounted_ms": round(self.unaccounted_ms, 2),
            "compute_fraction": round(self.compute_fraction, 6),
            "overhead_fraction": round(self.overhead_fraction, 6),
            "serial_bottleneck_fraction": round(self.serial_bottleneck_fraction, 6),
            "parallelizable_fraction_estimate": round(self.parallelizable_fraction_estimate, 6),
            "cpus_allocated": self.cpus_allocated,
            "effective_parallelism": round(self.effective_parallelism, 4),
            "core_utilization_ratio": round(self.core_utilization_ratio, 6),
        }


def compute_utilization_breakdown(
    result_rows: Sequence[Dict[str, Any]],
    *,
    total_wall_clock_ms: float,
    plot_io_ms: float = 0.0,
    serialization_ms: float = 0.0,
    cpus_allocated: Optional[int] = None,
) -> UtilizationBreakdown:
    """Decompose wall-clock time into compute, overhead, and parallelization metrics."""
    if cpus_allocated is None:
        cpus_allocated = _detect_cpus_allocated()

    total_compute = 0.0
    total_lookup = 0.0
    total_put = 0.0

    for row in result_rows:
        compute_ms = float(row.get("pricing_compute_time_ms", 0.0))
        total_compute += compute_ms

        semantics = str(row.get("row_semantics", ""))
        runtime = float(row.get("total_runtime_ms", 0.0))

        if semantics.startswith("lookup"):
            total_lookup += runtime
        elif semantics.startswith("put"):
            total_put += max(0.0, runtime - compute_ms)

    accounted = total_compute + total_lookup + total_put + plot_io_ms + serialization_ms
    overhead = max(0.0, total_wall_clock_ms - accounted)

    wall = max(total_wall_clock_ms, 1e-6)
    compute_frac = total_compute / wall
    overhead_frac = overhead / wall
    serial_frac = (total_lookup + total_put + serialization_ms) / wall

    parallelizable_frac = max(0.0, 1.0 - serial_frac - overhead_frac)
    effective_par = total_compute / wall if wall > 0 else 0.0
    core_util = effective_par / max(cpus_allocated, 1)

    return UtilizationBreakdown(
        total_wall_clock_ms=total_wall_clock_ms,
        total_compute_ms=total_compute,
        total_lookup_ms=total_lookup,
        total_cache_put_ms=total_put,
        total_plot_io_ms=plot_io_ms,
        total_serialization_ms=serialization_ms,
        orchestration_overhead_ms=overhead,
        unaccounted_ms=max(0.0, wall - accounted - overhead),
        compute_fraction=compute_frac,
        overhead_fraction=overhead_frac,
        serial_bottleneck_fraction=serial_frac,
        parallelizable_fraction_estimate=parallelizable_frac,
        cpus_allocated=cpus_allocated,
        effective_parallelism=effective_par,
        core_utilization_ratio=core_util,
    )


def amdahl_speedup(serial_fraction: float, n_cores: int) -> float:
    """Theoretical max speedup under Amdahl's law."""
    if serial_fraction >= 1.0:
        return 1.0
    return 1.0 / (serial_fraction + (1.0 - serial_fraction) / max(n_cores, 1))


def compute_scaling_projection(
    breakdown: UtilizationBreakdown,
    *,
    core_counts: Optional[Sequence[int]] = None,
) -> List[Dict[str, Any]]:
    """Project speedup at various core counts using current serial fraction."""
    if core_counts is None:
        core_counts = [1, 2, 4, 8, 16, 32, 64, 128]

    sf = breakdown.serial_bottleneck_fraction
    projections: List[Dict[str, Any]] = []

    for nc in core_counts:
        speedup = amdahl_speedup(sf, nc)
        projected_wall = breakdown.total_wall_clock_ms / speedup if speedup > 0 else breakdown.total_wall_clock_ms
        projections.append({
            "cores": nc,
            "theoretical_speedup": round(speedup, 4),
            "projected_wall_clock_ms": round(projected_wall, 2),
            "serial_fraction": round(sf, 6),
        })

    return projections


def _detect_cpus_allocated() -> int:
    """Detect allocated CPU count from Slurm or OS."""
    slurm_cpus = os.environ.get("SLURM_CPUS_ON_NODE")
    if slurm_cpus:
        try:
            return int(slurm_cpus)
        except ValueError:
            pass

    slurm_tasks = os.environ.get("SLURM_NTASKS")
    if slurm_tasks:
        try:
            return int(slurm_tasks)
        except ValueError:
            pass

    try:
        return os.cpu_count() or 1
    except Exception:
        return 1
