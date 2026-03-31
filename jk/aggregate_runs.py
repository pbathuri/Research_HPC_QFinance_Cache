#!/usr/bin/env python3
"""Aggregate multiple BigRed200 run outputs into one comparative evidence pack.

Usage::

    PYTHONPATH=src python3 aggregate_runs.py outputs/run_seed_0 outputs/run_seed_1 ...
    PYTHONPATH=src python3 aggregate_runs.py --glob "outputs/repeated_workload_seed_*"
"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate multiple run outputs.")
    parser.add_argument("run_dirs", nargs="*", help="Run directories to aggregate.")
    parser.add_argument("--glob", type=str, default="", help="Glob pattern for run dirs.")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs/aggregated_evidence",
        help="Output directory for aggregated comparison.",
    )
    args = parser.parse_args()

    dirs = list(args.run_dirs)
    if args.glob:
        dirs.extend(sorted(glob.glob(args.glob)))
    if not dirs:
        print("No run directories specified. Use positional args or --glob.")
        return 1

    from qhpc_cache.run_profiles import aggregate_runs

    result = aggregate_runs(dirs, args.output_dir)
    print(f"Aggregated {result['run_count']} runs.")
    print(f"  comparison_json: {result['comparison_json']}")
    print(f"  comparison_md:   {result['comparison_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
