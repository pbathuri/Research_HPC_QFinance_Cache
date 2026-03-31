#!/usr/bin/env python3
"""Run canonical repeated-workload cache study (Lane A/B).

Run from ``jk/``::

    PYTHONPATH=src python3 run_repeated_workload_study.py
    PYTHONPATH=src python3 run_repeated_workload_study.py --profile finance_reuse_standard
    PYTHONPATH=src python3 run_repeated_workload_study.py --lane lane_a --scale-label smoke
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from qhpc_cache.repeated_workload_study import run_repeated_workload_study


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run repeated-workload cache study with deterministic families.",
    )
    parser.add_argument(
        "--lane",
        choices=["both", "lane_a", "lane_b"],
        default="both",
        help="Lane selection (both, lane_a reuse-friendly, lane_b stress/churn).",
    )
    parser.add_argument(
        "--include-stress-lane",
        action="store_true",
        help=(
            "Backward-compatible alias: when used with --lane lane_a, promote to --lane both "
            "so stress lane behavior is included."
        ),
    )
    parser.add_argument(
        "--families",
        type=str,
        default="",
        help=(
            "Comma-separated family IDs. Empty means all: "
            "exact_repeat_pricing, near_repeat_pricing, path_ladder_pricing, "
            "portfolio_cluster_condensation, overlapping_event_window_rebuild, stress_churn_pricing. "
            "Legacy aliases still accepted."
        ),
    )
    parser.add_argument(
        "--output-root",
        type=str,
        default="outputs/repeated_workload_phase",
        help="Output directory for repeated workload artifacts.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=123,
        help="Deterministic seed for workload generation.",
    )
    parser.add_argument(
        "--scale-label",
        choices=["smoke", "standard", "heavy"],
        default="standard",
        help="Execution scale label.",
    )
    parser.add_argument(
        "--outlier-threshold-ms",
        type=float,
        default=60_000.0,
        help="Outlier threshold for pricing_compute_time_ms.",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip plot generation.",
    )
    parser.add_argument(
        "--budget-minutes",
        type=float,
        default=0.0,
        help="Budget in minutes (0 = no budget tracking, used for utilization reporting).",
    )
    parser.add_argument(
        "--requested-backend",
        type=str,
        default="cpu_local",
        help="Backend intent for HPC provenance tracking.",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default="",
        help="Named run profile (overrides other args). Use --list-profiles to see options.",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List available run profiles and exit.",
    )
    parser.add_argument(
        "--generate-slurm",
        type=str,
        default="",
        metavar="PROFILE",
        help="Generate Slurm script for named profile and exit.",
    )
    parser.add_argument(
        "--slurm-email",
        type=str,
        default="",
        help="Email for Slurm notifications.",
    )
    parser.add_argument(
        "--slurm-account",
        type=str,
        default="",
        help="Slurm account/allocation.",
    )
    return parser


def _resolve_lane_selection(args: argparse.Namespace) -> str:
    lane = str(args.lane)
    if bool(getattr(args, "include_stress_lane", False)) and lane == "lane_a":
        return "both"
    return lane


def main() -> int:
    args = _build_parser().parse_args()

    if args.list_profiles:
        from qhpc_cache.run_profiles import list_profiles
        print("Available run profiles:")
        for p in list_profiles():
            print(f"  {p['name']:35s} {p['description']}")
        return 0

    if args.generate_slurm:
        from qhpc_cache.run_profiles import generate_slurm_script
        script = generate_slurm_script(
            args.generate_slurm,
            output_dir=args.output_root,
            email=args.slurm_email,
            account=args.slurm_account,
        )
        out_path = Path(f"slurm_{args.generate_slurm}.sbatch.sh")
        out_path.write_text(script)
        print(f"Slurm script written: {out_path}")
        return 0

    if args.profile:
        from qhpc_cache.run_profiles import get_profile
        profile = get_profile(args.profile)
        families = profile.get("families", [])
        result = run_repeated_workload_study(
            output_dir=Path(args.output_root),
            lane_selection=profile.get("lane_selection", "both"),
            workload_families=families if families else None,
            scale_label=profile.get("scale_label", "standard"),
            seed=int(os.environ.get("SLURM_ARRAY_TASK_ID", "0")) + profile.get("seed", 123),
            outlier_threshold_ms=args.outlier_threshold_ms,
            emit_plots=profile.get("emit_plots", True),
            budget_minutes=profile.get("budget_minutes", 0.0),
            requested_backend=args.requested_backend,
        )
    else:
        families = [f.strip() for f in args.families.split(",") if f.strip()]
        result = run_repeated_workload_study(
            output_dir=Path(args.output_root),
            lane_selection=_resolve_lane_selection(args),
            workload_families=families if families else None,
            scale_label=args.scale_label,
            seed=args.seed,
            outlier_threshold_ms=args.outlier_threshold_ms,
            emit_plots=not bool(args.no_plots),
            budget_minutes=args.budget_minutes,
            requested_backend=args.requested_backend,
        )

    manifest = result["manifest"]
    print("Repeated workload study completed.")
    print(f"  output: {args.output_root}")
    print(f"  lanes: {manifest['selected_lanes']}")
    print(f"  families: {manifest['selected_workload_families']}")
    print(f"  summary rows: {manifest['summary_rows_count']}")
    print(f"  outlier rows: {manifest['outlier_rows_count']}")
    print(f"  manifest: {result['manifest_path']}")
    budget = manifest.get("budget_utilization", {})
    if budget:
        print(f"  budget_utilization: {budget.get('budget_utilization_fraction', 0):.2%}")
        print(f"  termination_reason: {budget.get('termination_reason', 'n/a')}")
    evidence = result.get("evidence_artifacts", {})
    if evidence:
        print(f"  evidence_bundle: {len(evidence)} artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

