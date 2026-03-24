"""Rolling window extraction and summary computation for trace telemetry.

Each window covers a contiguous slice of trace events and computes aggregate
cache/locality features used for pattern discovery and polar embedding.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from qhpc_cache.trace_features import (
    compute_burst_score,
    compute_locality_score,
    compute_periodic_score,
    safe_entropy,
)


def _safe_float(val: Any, default: float = float("nan")) -> float:
    """Convert *val* to float, returning *default* for unparseable/missing."""
    if val is None or val == "":
        return default
    try:
        f = float(val)
        return f
    except (ValueError, TypeError):
        return default


def window_id(run_id: str, seq: int) -> str:
    raw = f"{run_id}|w{seq}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def engine_mix(engines: Sequence[str]) -> str:
    counts = Counter(engines)
    parts = sorted(f"{k}:{v}" for k, v in counts.items())
    return ";".join(parts)


def compute_window_summary(
    events: List[Dict[str, Any]],
    wid: str,
    run_id: str,
) -> Dict[str, Any]:
    """Compute aggregate features over a window of trace event dicts."""
    n = len(events)
    if n == 0:
        return {}

    hits = [e.get("cache_hit", False) for e in events]
    exact_hr = sum(1 for h in hits if h) / n
    miss_r = 1.0 - exact_hr

    reuse_dists = [
        _safe_float(e.get("reuse_distance_events"))
        for e in events
    ]
    reuse_dists = [d for d in reuse_dists if math.isfinite(d)]
    rd_arr = np.array(reuse_dists, dtype=float) if reuse_dists else np.array([0.0])

    keys = [e.get("cache_key_short", "") for e in events]
    engines_list = [e.get("engine", "") for e in events]
    contracts = [e.get("contract_id", "") for e in events]

    gaps = [_safe_float(e.get("inter_event_gap_ms"), 0.0) for e in events]
    wall_clocks = [_safe_float(e.get("wall_clock_ms"), 0.0) for e in events]

    prices = [_safe_float(e.get("price")) for e in events]
    prices = [p for p in prices if math.isfinite(p)]
    std_errors = [_safe_float(e.get("std_error")) for e in events]
    std_errors = [s for s in std_errors if math.isfinite(s)]

    hit_flags = [1 if h else 0 for h in hits]

    price_cv = (np.std(prices) / np.mean(prices)) if prices and np.mean(prices) != 0 else 0.0

    from qhpc_cache.trace_polar import compute_polar

    polar = compute_polar(
        mean_reuse_distance=float(rd_arr.mean()),
        miss_rate=miss_r,
        mean_wall_clock_ms=float(np.mean(wall_clocks)) if wall_clocks else 0.0,
        periodic_score=compute_periodic_score(hit_flags),
        burst_score=compute_burst_score(hit_flags),
        num_paths_mean=float(np.mean([_safe_float(e.get("num_paths"), 0) for e in events])),
    )

    phases = [e.get("phase", "") for e in events]
    phase_counts = Counter(phases)
    dominant_phase = phase_counts.most_common(1)[0][0] if phase_counts else ""
    eng_counts = Counter(engines_list)
    dominant_engine = eng_counts.most_common(1)[0][0] if eng_counts else ""

    cluster_seed = hashlib.sha256(
        f"{dominant_engine}|{dominant_phase}|{bucket_miss(miss_r)}|{bucket_locality(compute_locality_score(reuse_dists))}".encode()
    ).hexdigest()[:12]

    sim_hits_list = [e.get("similarity_hit", False) for e in events]
    sim_hr = sum(1 for s in sim_hits_list if s) / n
    sim_scores = [_safe_float(e.get("similarity_score"), 0) for e in events]
    sim_scores_valid = [s for s in sim_scores if s > 0]
    sigs = [e.get("pattern_signature", "") for e in events]
    sig_diversity = len(set(sigs))
    sig_counts = Counter(sigs)
    dom_sig = sig_counts.most_common(1)[0][0] if sig_counts else ""

    loc_score = compute_locality_score(reuse_dists)
    reuse_signal = round(0.5 * exact_hr + 0.3 * sim_hr + 0.2 * loc_score, 6)

    pmu_miss_ratios = [_safe_float(e.get("pmu_cache_misses"), 0) / max(_safe_float(e.get("pmu_cache_references"), 1), 1)
                       for e in events if _safe_float(e.get("pmu_cache_references"), 0) > 0]
    pmu_ipcs = [_safe_float(e.get("pmu_instructions"), 0) / max(_safe_float(e.get("pmu_cycles"), 1), 1)
                for e in events if _safe_float(e.get("pmu_cycles"), 0) > 0]

    return {
        "window_id": wid,
        "run_id": run_id,
        "phase": dominant_phase,
        "engine_mix": engine_mix(engines_list),
        "start_event_id": events[0].get("event_id", ""),
        "end_event_id": events[-1].get("event_id", ""),
        "window_size": n,
        "exact_hit_rate": round(exact_hr, 6),
        "miss_rate": round(miss_r, 6),
        "similarity_hit_rate": round(sim_hr, 6),
        "similarity_event_rate": round(sim_hr, 6),
        "similarity_score_mean": round(float(np.mean(sim_scores_valid)), 6) if sim_scores_valid else 0.0,
        "signature_diversity": sig_diversity,
        "dominant_signature_family": dom_sig[:16] if dom_sig else "",
        "mean_reuse_distance": round(float(rd_arr.mean()), 4),
        "median_reuse_distance": round(float(np.median(rd_arr)), 4),
        "p90_reuse_distance": round(float(np.percentile(rd_arr, 90)), 4) if len(rd_arr) > 1 else 0.0,
        "working_set_size": len(set(keys)),
        "unique_keys_seen": len(set(keys)),
        "engine_entropy": round(safe_entropy(engines_list), 4),
        "contract_entropy": round(safe_entropy(contracts), 4),
        "burst_score": round(compute_burst_score(hit_flags), 6),
        "periodic_score": round(compute_periodic_score(hit_flags), 6),
        "locality_score": round(loc_score, 6),
        "mean_inter_event_gap_ms": round(float(np.mean(gaps)) if gaps else 0, 4),
        "mean_wall_clock_ms": round(float(np.mean(wall_clocks)) if wall_clocks else 0, 4),
        "cumulative_runtime_s": round(_safe_float(events[-1].get("cumulative_elapsed_s"), 0), 4),
        "price_variation_cv": round(price_cv, 6),
        "std_error_mean": round(float(np.mean(std_errors)) if std_errors else 0, 6),
        "moneyness_mean": round(float(np.mean([_safe_float(e.get("moneyness"), 1.0) for e in events])), 4),
        "sigma_mean": round(float(np.mean([_safe_float(e.get("sigma"), 0) for e in events])), 4),
        "T_mean": round(float(np.mean([_safe_float(e.get("T"), 0) for e in events])), 4),
        "num_paths_mean": round(float(np.mean([_safe_float(e.get("num_paths"), 0) for e in events])), 2),
        "reuse_signal_mean": reuse_signal,
        "total_reuse_signal": reuse_signal,
        "pmu_miss_ratio_mean": round(float(np.mean(pmu_miss_ratios)), 6) if pmu_miss_ratios else 0.0,
        "pmu_ipc_mean": round(float(np.mean(pmu_ipcs)), 6) if pmu_ipcs else 0.0,
        "polar_r": polar["polar_r"],
        "polar_theta": polar["polar_theta"],
        "polar_z": polar["polar_z"],
        "cluster_seed_key": cluster_seed,
        "dominant_engine": dominant_engine,
        "dominant_phase": dominant_phase,
        "notes": "",
    }


def bucket_miss(miss_rate: float) -> str:
    if miss_rate < 0.2:
        return "low_miss"
    if miss_rate < 0.5:
        return "med_miss"
    return "high_miss"


def bucket_locality(loc: float) -> str:
    if loc > 0.3:
        return "high_loc"
    if loc > 0.1:
        return "med_loc"
    return "low_loc"
