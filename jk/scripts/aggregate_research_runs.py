#!/usr/bin/env python3
"""Aggregate research evidence across multiple local and BigRed200 runs.

Usage:
    python3 scripts/aggregate_research_runs.py outputs/run1 outputs/run2 --output-dir outputs/aggregate
    python3 scripts/aggregate_research_runs.py --glob "outputs/repeated_workload_*" --output-dir outputs/aggregate
"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate research evidence across multiple runs.",
    )
    parser.add_argument("run_dirs", nargs="*", help="Run directories to aggregate.")
    parser.add_argument("--glob", type=str, default="", help="Glob pattern for run dirs.")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs/aggregate",
        help="Output directory for aggregate artifacts.",
    )
    args = parser.parse_args()

    dirs = [Path(d) for d in args.run_dirs]
    if args.glob:
        dirs.extend(Path(p) for p in sorted(glob.glob(args.glob)))

    if not dirs:
        print("No run directories specified. Use positional args or --glob.")
        return 1

    from qhpc_cache.run_aggregation import aggregate_research_runs

    output_dir = Path(args.output_dir)
    result = aggregate_research_runs(dirs, output_dir)

    print(f"Aggregate research summary:")
    print(f"  Runs: {result['run_count']} (local: {result['local_run_count']}, HPC: {result['hpc_run_count']})")
    print(f"  Families: {len(result.get('per_family', {}))}")
    print(f"  Output: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
