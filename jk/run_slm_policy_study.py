#!/usr/bin/env python3
"""CLI entry point for the SLM policy comparison study.

Usage::

    cd jk
    PYTHONPATH=src python3 run_slm_policy_study.py --scale-label smoke
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run SLM-trained vs heuristic vs logistic cache-policy comparison."
    )
    parser.add_argument(
        "--scale-label",
        default="smoke",
        help="Scale profile: smoke | standard | heavy (default: smoke)",
    )
    parser.add_argument(
        "--output-root",
        default="outputs/slm_policy_study",
        help="Root directory for study outputs (default: outputs/slm_policy_study)",
    )
    parser.add_argument(
        "--model-type",
        choices=["gradient_boosting", "logistic_regression", "random_forest"],
        default="gradient_boosting",
        help="ML model type for the SLM policy (default: gradient_boosting)",
    )
    parser.add_argument(
        "--cv-folds",
        type=int,
        default=5,
        help="Number of cross-validation folds (default: 5)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    args = parser.parse_args()

    if "src" not in os.environ.get("PYTHONPATH", ""):
        src_dir = str(Path(__file__).resolve().parent / "src")
        sys.path.insert(0, src_dir)

    from qhpc_cache.slm_policy_study import run_slm_policy_comparison

    output_dir = Path(args.output_root)
    summary = run_slm_policy_comparison(
        output_dir=output_dir,
        scale_label=args.scale_label,
        model_type=args.model_type,
        seed=args.seed,
        cv_folds=args.cv_folds,
    )

    print("\n=== SLM Policy Comparison Summary ===\n")
    for name, metrics in summary["results"].items():
        print(
            f"  {name:20s}  P={metrics['precision']:.3f}  "
            f"R={metrics['recall']:.3f}  F1={metrics['f1']:.3f}  "
            f"saved={metrics['total_latency_saved_ms']:.1f}ms"
        )

    cv = summary["cv_report"]
    print(f"\n  CV mean F1={cv['mean_f1']:.3f} (+/- {cv['std_f1']:.3f})")
    print(f"  CV mean AUC-ROC={cv['mean_auc_roc']:.3f}")
    print(f"\n  Outputs: {summary['output_dir']}")


if __name__ == "__main__":
    main()
