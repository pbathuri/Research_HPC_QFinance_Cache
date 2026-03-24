"""Polar/3D embedding for cache trace windows.

Deterministic mapping from window summary features into a polar coordinate
system suitable for visual clustering analysis.

Design:
    polar_r     = normalized combination of mean_reuse_distance, miss_rate,
                  and mean_wall_clock_ms
    polar_theta = atan2(periodic_score, burst_score)
    polar_z     = log1p(num_paths_mean)

Cartesian projection:
    x = polar_r * cos(theta)
    y = polar_r * sin(theta)
"""

from __future__ import annotations

import math
from typing import Dict


def _minmax_norm(val: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (val - lo) / (hi - lo)))


def compute_polar(
    mean_reuse_distance: float,
    miss_rate: float,
    mean_wall_clock_ms: float,
    periodic_score: float,
    burst_score: float,
    num_paths_mean: float,
    *,
    reuse_dist_range: tuple[float, float] = (0.0, 200.0),
    wall_clock_range: tuple[float, float] = (0.0, 5000.0),
) -> Dict[str, float]:
    rd_norm = _minmax_norm(mean_reuse_distance, *reuse_dist_range)
    mr_norm = max(0.0, min(1.0, miss_rate))
    wc_norm = _minmax_norm(mean_wall_clock_ms, *wall_clock_range)

    polar_r = round((rd_norm + mr_norm + wc_norm) / 3.0, 6)
    polar_theta = round(math.atan2(periodic_score, burst_score + 1e-12), 6)
    polar_z = round(math.log1p(max(0, num_paths_mean)), 6)

    x = round(polar_r * math.cos(polar_theta), 6)
    y = round(polar_r * math.sin(polar_theta), 6)

    return {
        "polar_r": polar_r,
        "polar_theta": polar_theta,
        "polar_z": polar_z,
        "x": x,
        "y": y,
    }


def build_polar_row(
    window_summary: Dict,
    run_id: str,
) -> Dict:
    return {
        "window_id": window_summary["window_id"],
        "run_id": run_id,
        "phase": window_summary.get("dominant_phase", ""),
        "dominant_engine": window_summary.get("dominant_engine", ""),
        "polar_r": window_summary["polar_r"],
        "polar_theta": window_summary["polar_theta"],
        "polar_z": window_summary["polar_z"],
        "x": window_summary["polar_r"] * math.cos(window_summary["polar_theta"]),
        "y": window_summary["polar_r"] * math.sin(window_summary["polar_theta"]),
        "locality_score": window_summary.get("locality_score", 0),
        "miss_rate": window_summary.get("miss_rate", 0),
        "mean_reuse_distance": window_summary.get("mean_reuse_distance", 0),
        "working_set_size": window_summary.get("working_set_size", 0),
        "cluster_seed_key": window_summary.get("cluster_seed_key", ""),
    }
