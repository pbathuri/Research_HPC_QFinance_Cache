"""Compose unified research evidence bundle from all three paths.

Usage:
    python3 run_compose_evidence.py \
        --pandora-dir outputs/pandora_circuit_study \
        --slm-dir outputs/slm_policy_study \
        --mpi-dir outputs/mpi_scaling_study \
        --output-dir outputs/unified_evidence
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from qhpc_cache.unified_research_evidence import compose_unified_bundle


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compose unified research evidence from three paths"
    )
    parser.add_argument(
        "--pandora-dir",
        type=Path,
        default=Path("outputs/pandora_circuit_study"),
    )
    parser.add_argument(
        "--slm-dir",
        type=Path,
        default=Path("outputs/slm_policy_study"),
    )
    parser.add_argument(
        "--mpi-dir",
        type=Path,
        default=Path("outputs/mpi_scaling_study"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/unified_evidence"),
    )
    args = parser.parse_args()

    bundle_path = compose_unified_bundle(
        pandora_output_dir=args.pandora_dir,
        slm_output_dir=args.slm_dir,
        mpi_output_dir=args.mpi_dir,
        bundle_output_dir=args.output_dir,
    )

    bundle = json.loads(bundle_path.read_text())
    print(f"\nUnified evidence bundle: {bundle_path}")
    print(f"Generated: {bundle['generated_utc']}")
    print(f"\nPaths:")
    for p in bundle["paths"]:
        print(f"  {p['path_name']}: {p['status']} ({len(p['artifacts'])} artifacts)")
    print(f"\nClaims:")
    for claim_id, info in bundle["claims_summary"].items():
        print(f"  {claim_id}: {info['status']}")
    print(f"\nNovel contributions: {len(bundle['combined_novel_contributions'])}")
    for c in bundle["combined_novel_contributions"]:
        print(f"  - {c}")


if __name__ == "__main__":
    main()
