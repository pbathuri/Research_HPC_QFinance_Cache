#!/usr/bin/env python3
"""CLI entry point for the multi-node MPI scaling study.

Usage (single process):
    PYTHONPATH=src python3 run_mpi_scaling_study.py --scale-label smoke

Usage (MPI):
    mpiexec -n 4 python3 run_mpi_scaling_study.py --scale-label standard --strategy all
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _ensure_pythonpath() -> None:
    src = str(Path(__file__).resolve().parent / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    os.environ.setdefault("PYTHONPATH", src)


def main() -> None:
    _ensure_pythonpath()

    parser = argparse.ArgumentParser(
        description="Run MPI workload distribution scaling study."
    )
    parser.add_argument(
        "--scale-label",
        default="smoke",
        choices=["smoke", "standard", "heavy"],
        help="Workload scale (default: smoke)",
    )
    parser.add_argument(
        "--output-root",
        default="outputs/mpi_scaling_study",
        help="Output directory root (default: outputs/mpi_scaling_study)",
    )
    parser.add_argument(
        "--strategy",
        default="all",
        choices=["round_robin", "cache_aware", "locality_aware", "all"],
        help="Strategy to run (default: all)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed (default: 42)",
    )
    args = parser.parse_args()

    from qhpc_cache.mpi_scaling_study import ScalingStudyConfig, run_mpi_scaling_study

    if args.strategy == "all":
        strategies = ["round_robin", "cache_aware", "locality_aware"]
    else:
        strategies = [args.strategy]

    config = ScalingStudyConfig(
        scale_label=args.scale_label,
        strategies=strategies,
        output_dir=Path(args.output_root),
        seed=args.seed,
    )

    is_rank0 = True
    try:
        from mpi4py import MPI  # type: ignore
        is_rank0 = MPI.COMM_WORLD.Get_rank() == 0
    except ImportError:
        pass

    summary = run_mpi_scaling_study(config)

    if is_rank0:
        print(json.dumps(summary, indent=2))
        print(f"\nOutputs written to: {config.output_dir}")


if __name__ == "__main__":
    main()
