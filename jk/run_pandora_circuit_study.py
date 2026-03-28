"""CLI entry point for the Pandora Circuit Cache study."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Pandora-style circuit cache experiment"
    )
    parser.add_argument(
        "--scale-label",
        default="smoke",
        help="Scale profile: smoke, standard, or heavy (default: smoke)",
    )
    parser.add_argument(
        "--output-root",
        default="outputs/pandora_circuit_study",
        help="Output directory (default: outputs/pandora_circuit_study)",
    )
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.85,
        help="Structural similarity threshold (default: 0.85)",
    )
    parser.add_argument(
        "--n-qubits",
        type=int,
        default=6,
        help="Number of qubits for circuit construction (default: 6)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic generation (default: 42)",
    )
    args = parser.parse_args()

    src_dir = str(Path(__file__).resolve().parent / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    from qhpc_cache.pandora_circuit_study import PandoraStudyConfig, run_pandora_study

    config = PandoraStudyConfig(
        scale_label=args.scale_label,
        similarity_threshold=args.similarity_threshold,
        n_qubits=args.n_qubits,
        output_dir=Path(args.output_root),
        seed=args.seed,
    )

    print(
        f"Pandora Circuit Study: scale={config.scale_label}, "
        f"threshold={config.similarity_threshold}, qubits={config.n_qubits}"
    )
    print(f"Output: {config.output_dir}")

    summary = run_pandora_study(config)

    print("\n--- Results ---")
    print(f"Total problems:    {summary['total_problems']}")
    print(f"Exact hits:        {summary['exact_hits']}")
    print(f"Structural hits:   {summary['structural_hits']}")
    print(f"Misses:            {summary['misses']}")
    print(f"Overall hit rate:  {summary['hit_rate']:.3f}")
    print(f"Time saved (ms):   {summary['total_compilation_time_saved_ms']:.1f}")
    print(f"Cirq available:    {summary['cirq_available']}")


if __name__ == "__main__":
    main()
