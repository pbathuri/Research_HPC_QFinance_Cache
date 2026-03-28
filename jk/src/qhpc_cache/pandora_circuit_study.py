"""Pandora Circuit Cache experiment driver.

Exercises the structural-similarity circuit cache across a mix of repeated,
near-repeat, and novel finance problems.  Works both with and without Cirq
installed by falling back to synthetic metadata.
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from random import Random
from typing import Any, Dict, List, Optional, Tuple

from qhpc_cache.circuit_fingerprint import (
    CircuitFingerprintEncoder,
    fingerprint_from_metadata,
)
from qhpc_cache.pandora_circuit_cache import PandoraCircuitCache

try:
    import cirq  # noqa: F401

    _CIRQ_AVAILABLE = True
except ImportError:
    _CIRQ_AVAILABLE = False


PANDORA_SCALE_PROFILES: Dict[str, Dict[str, int]] = {
    "smoke": {"exact_repeats": 5, "near_repeats": 10, "novel": 5},
    "standard": {"exact_repeats": 30, "near_repeats": 60, "novel": 30},
    "heavy": {"exact_repeats": 100, "near_repeats": 200, "novel": 100},
}


@dataclass
class PandoraStudyConfig:
    scale_label: str = "smoke"
    similarity_threshold: float = 0.85
    n_qubits: int = 6
    output_dir: Path = field(
        default_factory=lambda: Path("outputs/pandora_circuit_study")
    )
    seed: int = 42


def _generate_finance_problems(config: PandoraStudyConfig) -> List[Dict[str, Any]]:
    """Deterministic mix of exact repeats, near-repeats, and novel problems."""
    rng = Random(config.seed)
    profile = PANDORA_SCALE_PROFILES.get(
        config.scale_label, PANDORA_SCALE_PROFILES["smoke"]
    )

    base_problems = [
        {"S0": 100.0, "K": 105.0, "sigma": 0.20, "T": 1.0, "r": 0.05, "num_paths": 4096},
        {"S0": 100.0, "K": 95.0, "sigma": 0.25, "T": 0.5, "r": 0.03, "num_paths": 4096},
        {"S0": 120.0, "K": 115.0, "sigma": 0.30, "T": 2.0, "r": 0.04, "num_paths": 8192},
        {"S0": 80.0, "K": 85.0, "sigma": 0.18, "T": 0.25, "r": 0.06, "num_paths": 2048},
        {"S0": 150.0, "K": 140.0, "sigma": 0.35, "T": 1.5, "r": 0.02, "num_paths": 4096},
    ]

    problems: List[Dict[str, Any]] = []

    n_exact = profile["exact_repeats"]
    for i in range(n_exact):
        p = dict(base_problems[i % len(base_problems)])
        p["problem_type"] = "exact_repeat"
        p["problem_id"] = f"exact_{i:04d}"
        problems.append(p)

    n_near = profile["near_repeats"]
    for i in range(n_near):
        base = dict(base_problems[i % len(base_problems)])
        drift = (rng.random() - 0.5) * 0.02
        base["S0"] = round(base["S0"] * (1.0 + drift), 4)
        base["K"] = round(base["K"] * (1.0 + drift * 0.8), 4)
        base["sigma"] = round(max(0.05, base["sigma"] * (1.0 + drift * 1.5)), 4)
        base["T"] = round(max(0.05, base["T"] * (1.0 + drift * 0.5)), 4)
        base["problem_type"] = "near_repeat"
        base["problem_id"] = f"near_{i:04d}"
        problems.append(base)

    n_novel = profile["novel"]
    for i in range(n_novel):
        p = {
            "S0": round(rng.uniform(50.0, 200.0), 4),
            "K": round(rng.uniform(40.0, 210.0), 4),
            "sigma": round(rng.uniform(0.10, 0.60), 4),
            "T": round(rng.uniform(0.1, 3.0), 4),
            "r": round(rng.uniform(0.01, 0.08), 4),
            "num_paths": rng.choice([1024, 2048, 4096, 8192]),
            "problem_type": "novel",
            "problem_id": f"novel_{i:04d}",
        }
        problems.append(p)

    return problems


def _build_circuit_for_problem(
    problem: Dict[str, Any],
    n_qubits: int,
) -> Tuple[Optional[Any], Dict[str, Any], float]:
    """Build a Cirq circuit or return synthetic metadata when Cirq is unavailable.

    Returns (circuit_or_None, metadata_dict, compilation_time_ms).
    """
    if _CIRQ_AVAILABLE:
        from qhpc_cache.quantum_engines.cirq_engine import CirqEngine

        engine = CirqEngine(n_qubits=n_qubits)
        t0 = time.perf_counter()
        result = engine.price(
            S0=problem["S0"],
            K=problem["K"],
            r=problem["r"],
            sigma=problem["sigma"],
            T=problem["T"],
            num_paths=problem["num_paths"],
            seed=42,
        )
        compilation_ms = (time.perf_counter() - t0) * 1000.0
        return None, result.metadata, compilation_ms

    N = 2**n_qubits
    synth_gate_count = 1 + N + N + 1
    synth_depth = 2 + N
    moneyness = (problem["S0"] - problem["K"]) / max(problem["S0"], 1e-9)
    synth_prob = max(0.0, min(1.0, moneyness * 0.3 + 0.1))
    synth_time_ms = 5.0 + n_qubits * 2.0 + N * 0.1

    metadata = {
        "n_qubits": n_qubits,
        "gate_count": synth_gate_count,
        "circuit_depth": synth_depth,
        "prob_ancilla_one": round(synth_prob, 6),
    }
    return None, metadata, synth_time_ms


def run_pandora_study(config: PandoraStudyConfig) -> Dict[str, Any]:
    """Main experiment: exercise the Pandora circuit cache and collect metrics."""
    config.output_dir.mkdir(parents=True, exist_ok=True)

    problems = _generate_finance_problems(config)
    cache = PandoraCircuitCache(similarity_threshold=config.similarity_threshold)

    per_problem_results: List[Dict[str, Any]] = []

    for idx, problem in enumerate(problems):
        finance_params = {
            k: problem[k] for k in ("S0", "K", "sigma", "T", "r", "num_paths")
        }

        _, metadata, compilation_ms = _build_circuit_for_problem(
            problem, config.n_qubits
        )
        fp = fingerprint_from_metadata(metadata)

        hit_type, entry = cache.lookup(finance_params, fp)

        if hit_type == "miss":
            compiled_repr = json.dumps(metadata)
            cache.store(finance_params, fp, compiled_repr, compilation_ms)

        per_problem_results.append(
            {
                "step": idx,
                "problem_id": problem["problem_id"],
                "problem_type": problem["problem_type"],
                "hit_type": hit_type,
                "S0": problem["S0"],
                "K": problem["K"],
                "sigma": problem["sigma"],
                "T": problem["T"],
                "r": problem["r"],
                "num_paths": problem["num_paths"],
                "compilation_time_ms": round(compilation_ms, 3),
                "qubit_count": fp.qubit_count,
                "depth": fp.depth,
                "reused_from": entry.cache_key[:16] if entry else "",
            }
        )

    m = cache.metrics()
    total = max(m.total_lookups, 1)
    summary = {
        "scale_label": config.scale_label,
        "similarity_threshold": config.similarity_threshold,
        "n_qubits": config.n_qubits,
        "total_problems": len(problems),
        "exact_hits": m.exact_hits,
        "structural_hits": m.structural_hits,
        "misses": m.misses,
        "hit_rate": (m.exact_hits + m.structural_hits) / total,
        "exact_hit_rate": m.exact_hits / total,
        "structural_hit_rate": m.structural_hits / total,
        "total_compilation_time_saved_ms": m.total_compilation_time_saved_ms,
        "total_adaptation_time_ms": m.total_adaptation_time_ms,
        "cache_entries": m.entries,
        "cirq_available": _CIRQ_AVAILABLE,
    }

    _write_study_outputs(per_problem_results, m, cache, config, summary)
    return summary


def _write_study_outputs(
    results: List[Dict[str, Any]],
    metrics: Any,
    cache: PandoraCircuitCache,
    config: PandoraStudyConfig,
    summary: Dict[str, Any],
) -> None:
    out = config.output_dir
    out.mkdir(parents=True, exist_ok=True)

    csv_path = out / "pandora_study_results.csv"
    if results:
        fieldnames = list(results[0].keys())
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

    metrics_path = out / "pandora_cache_metrics.json"
    metrics_data = {
        "exact_hits": metrics.exact_hits,
        "structural_hits": metrics.structural_hits,
        "misses": metrics.misses,
        "total_lookups": metrics.total_lookups,
        "total_compilation_time_saved_ms": metrics.total_compilation_time_saved_ms,
        "total_adaptation_time_ms": metrics.total_adaptation_time_ms,
        "entries": metrics.entries,
        "similarity_threshold": config.similarity_threshold,
    }
    metrics_path.write_text(json.dumps(metrics_data, indent=2))

    savings_path = out / "pandora_compilation_savings.json"
    savings_path.write_text(json.dumps(summary, indent=2))

    cache.export_evidence(out)
