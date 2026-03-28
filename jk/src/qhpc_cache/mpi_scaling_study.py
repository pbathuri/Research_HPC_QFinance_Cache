"""Experiment driver: run distribution strategies and collect scaling evidence.

Generates synthetic finance workloads (self-contained, no heavy deps), runs
each strategy via MPIWorkloadRunner, and writes comparison artifacts.
"""

from __future__ import annotations

import csv
import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from random import Random
from typing import Any, Dict, List

from qhpc_cache.mpi_workload_runner import MPIStudyResult, MPIWorkloadRunner

_WORKLOAD_FAMILIES = [
    "exact_repeat_pricing",
    "near_repeat_pricing",
    "path_ladder_pricing",
    "stress_churn_pricing",
    "intraday_scenario_ladder",
    "cross_sectional_basket",
    "rolling_horizon_refresh",
    "hotset_coldset_mixed",
]

_SCALE_COUNTS = {
    "smoke": 200,
    "standard": 2000,
    "heavy": 10000,
}


@dataclass
class ScalingStudyConfig:
    scale_label: str = "smoke"
    strategies: List[str] = field(
        default_factory=lambda: ["round_robin", "cache_aware", "locality_aware"]
    )
    output_dir: Path = field(default_factory=lambda: Path("outputs/mpi_scaling_study"))
    seed: int = 42


def _param_hash(S0: float, K: float, r: float, sigma: float, T: float, num_paths: int) -> str:
    raw = f"{S0:.6f}|{K:.6f}|{r:.6f}|{sigma:.6f}|{T:.6f}|{num_paths}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _feature_hash(S0: float, K: float, r: float, sigma: float, T: float) -> str:
    raw = f"{S0:.2f}|{K:.2f}|{r:.4f}|{sigma:.4f}|{T:.2f}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _generate_study_workloads(config: ScalingStudyConfig) -> List[Dict]:
    """Build a self-contained workload without importing heavy modules."""
    rng = Random(config.seed)
    total = _SCALE_COUNTS.get(config.scale_label, 200)
    per_family = max(1, total // len(_WORKLOAD_FAMILIES))

    base_params = [
        {"S0": 100.0, "K": 105.0, "r": 0.05, "sigma": 0.20, "T": 1.0},
        {"S0": 100.0, "K": 100.0, "r": 0.05, "sigma": 0.20, "T": 1.0},
        {"S0": 110.0, "K": 105.0, "r": 0.03, "sigma": 0.25, "T": 0.5},
        {"S0": 95.0,  "K": 100.0, "r": 0.04, "sigma": 0.30, "T": 2.0},
        {"S0": 120.0, "K": 115.0, "r": 0.06, "sigma": 0.18, "T": 0.25},
    ]
    lanes = ["lane_a", "lane_b"]
    num_paths = 10_000

    requests: List[Dict] = []
    req_idx = 0

    for family in _WORKLOAD_FAMILIES:
        for _ in range(per_family):
            bp = rng.choice(base_params)

            if family == "exact_repeat_pricing":
                params = dict(bp)
            elif family == "near_repeat_pricing":
                params = dict(bp)
                params["sigma"] = round(bp["sigma"] + rng.uniform(-0.001, 0.001), 6)
            else:
                params = dict(bp)
                params["S0"] = round(bp["S0"] * rng.uniform(0.95, 1.05), 4)
                params["K"] = round(bp["K"] * rng.uniform(0.97, 1.03), 4)

            S0, K, r, sigma, T = (
                params["S0"], params["K"], params["r"],
                params["sigma"], params["T"],
            )
            ph = _param_hash(S0, K, r, sigma, T, num_paths)
            fh = _feature_hash(S0, K, r, sigma, T)

            requests.append({
                "request_id": f"mpi_req_{req_idx:06d}",
                "parameter_hash": ph,
                "feature_hash": fh,
                "workload_family": family,
                "lane_id": rng.choice(lanes),
                "S0": S0,
                "K": K,
                "r": r,
                "sigma": sigma,
                "T": T,
                "num_paths": num_paths,
            })
            req_idx += 1

    rng.shuffle(requests)
    return requests


def run_mpi_scaling_study(config: ScalingStudyConfig) -> Dict[str, Any]:
    """Run all configured strategies and return a comparison summary."""
    config.output_dir.mkdir(parents=True, exist_ok=True)

    workloads = _generate_study_workloads(config)

    strategy_results: Dict[str, MPIStudyResult] = {}
    timings: Dict[str, float] = {}

    for strat_name in config.strategies:
        t0 = time.perf_counter()
        runner = MPIWorkloadRunner(strategy_name=strat_name)
        result = runner.run(workloads)
        elapsed = (time.perf_counter() - t0) * 1000.0
        strategy_results[strat_name] = result
        timings[strat_name] = elapsed

    _write_study_outputs(strategy_results, config)

    summary: Dict[str, Any] = {
        "scale_label": config.scale_label,
        "total_requests": len(workloads),
        "strategies": {},
    }
    for name, res in strategy_results.items():
        summary["strategies"][name] = {
            "world_size": res.world_size,
            "total_wall_ms": round(res.total_wall_ms, 2),
            "speedup_vs_single": res.speedup_vs_single,
            "aggregate_cache_hit_rate": res.aggregate_cache_hit_rate,
            "comm_bytes_total": (
                res.comm_metrics.bytes_scattered + res.comm_metrics.bytes_gathered
            ),
            "runner_wall_ms": round(timings[name], 2),
        }

    summary_path = config.output_dir / "mpi_scaling_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    return summary


def _write_study_outputs(
    strategy_results: Dict[str, MPIStudyResult],
    config: ScalingStudyConfig,
) -> None:
    out = config.output_dir
    out.mkdir(parents=True, exist_ok=True)

    # -- mpi_scaling_results.csv --
    csv_path = out / "mpi_scaling_results.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "strategy", "world_size", "total_wall_ms", "speedup_vs_single",
            "aggregate_cache_hit_rate", "comm_total_ms",
        ])
        for name, res in strategy_results.items():
            w.writerow([
                name,
                res.world_size,
                round(res.total_wall_ms, 2),
                res.speedup_vs_single,
                res.aggregate_cache_hit_rate,
                round(res.comm_metrics.total_comm_time_ms, 2),
            ])

    # -- mpi_communication_comparison.json --
    comm_data: Dict[str, Any] = {}
    for name, res in strategy_results.items():
        cm = res.comm_metrics
        comm_data[name] = {
            "bytes_scattered": cm.bytes_scattered,
            "bytes_gathered": cm.bytes_gathered,
            "scatter_time_ms": round(cm.scatter_time_ms, 2),
            "gather_time_ms": round(cm.gather_time_ms, 2),
            "total_comm_time_ms": round(cm.total_comm_time_ms, 2),
            "n_messages": cm.n_messages,
        }
    (out / "mpi_communication_comparison.json").write_text(
        json.dumps(comm_data, indent=2)
    )

    # -- mpi_scaling_curve.json --
    curve: List[Dict[str, Any]] = []
    for name, res in strategy_results.items():
        curve.append({
            "strategy": name,
            "world_size": res.world_size,
            "wall_time_ms": round(res.total_wall_ms, 2),
            "speedup": res.speedup_vs_single,
        })
    (out / "mpi_scaling_curve.json").write_text(json.dumps(curve, indent=2))

    # -- rank_cache_metrics.csv --
    rank_csv = out / "rank_cache_metrics.csv"
    with rank_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "strategy", "rank", "requests_processed", "cache_hits",
            "cache_misses", "cache_hit_rate", "total_compute_ms", "total_wall_ms",
        ])
        for name, res in strategy_results.items():
            for rr in res.rank_results:
                w.writerow([
                    name,
                    rr.rank,
                    rr.requests_processed,
                    rr.cache_hits,
                    rr.cache_misses,
                    round(rr.cache_hit_rate, 6),
                    round(rr.total_compute_ms, 2),
                    round(rr.total_wall_ms, 2),
                ])
