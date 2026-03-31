"""Canonical repeated-workload study for cache-research evidence."""

from __future__ import annotations

import csv
import json
import math
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np

from qhpc_cache.cache_store import SimpleCacheStore
from qhpc_cache.repeated_workload_generator import (
    FAMILY_ALIASES,
    FAMILY_IDS,
    LANE_A_ID,
    LANE_B_ID,
    LANE_SELECTIONS,
    REQUIRED_WORKLOAD_FAMILIES,
    TEMPLATE_BANK_ID_DEFAULT,
    build_template_bank as _generator_build_template_bank,
    generate_repeated_workload_requests as _generator_generate_requests,
)

try:
    import seaborn as sns

    _HAS_SEABORN = True
except Exception:
    _HAS_SEABORN = False


LANE_ENGINE_POLICY: Dict[str, Dict[str, Any]] = {
    LANE_A_ID: {
        "lane_label": "reuse-friendly repeated workload lane",
        "requested_engines": ["classical_mc", "quantlib_mc", "cirq_qmci"],
        "stable_lane_flag": True,
        "stress_lane_flag": False,
        "canonical_lane": True,
    },
    LANE_B_ID: {
        "lane_label": "stress/churn-heavy workload lane",
        "requested_engines": ["classical_mc", "quantlib_mc", "cirq_qmci", "monaco_mc"],
        "stable_lane_flag": False,
        "stress_lane_flag": True,
        "canonical_lane": False,
    },
}


@dataclass
class StudyRow:
    lane_id: str
    workload_family: str
    engine: str
    request_id: str
    request_key: str
    parameter_hash: str
    feature_hash: str
    cluster_id: str
    exact_repeat_group_id: str
    similarity_group_id: str
    event_window_id: str
    cache_hit: bool
    similarity_hit: bool
    row_semantics: str
    pricing_compute_time_ms: float
    total_runtime_ms: float
    reuse_distance_events: float
    robust_included: bool
    is_outlier: bool
    exclusion_reason: str
    compute_avoided_proxy: float
    time_saved_proxy: float
    cached_price: float = 0.0
    cached_std_error: float = 0.0


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _validate_scale_label(scale_label: str) -> str:
    label = str(scale_label).strip().lower()
    if label not in {"smoke", "standard", "heavy"}:
        raise ValueError(f"Invalid scale_label {scale_label!r}. Expected one of ['heavy', 'smoke', 'standard'].")
    return label


def _normalize_lane_selection(lane_selection: str) -> List[str]:
    lane = str(lane_selection).strip().lower()
    if lane not in LANE_SELECTIONS:
        raise ValueError(
            f"Invalid lane_selection {lane_selection!r}. Expected one of {sorted(LANE_SELECTIONS)}."
        )
    if lane == "both":
        return [LANE_A_ID, LANE_B_ID]
    return [lane]


def _normalize_family_selection(families: Optional[Sequence[str]]) -> List[str]:
    if not families:
        return list(REQUIRED_WORKLOAD_FAMILIES)
    out: List[str] = []
    for value in families:
        text = str(value).strip()
        if not text:
            continue
        canonical = FAMILY_ALIASES.get(text, text)
        if canonical not in FAMILY_IDS:
            raise ValueError(f"Invalid workload family values: {text!r}")
        if canonical not in out:
            out.append(canonical)
    return out


def _quantile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(float(v) for v in values)
    idx = int(round(max(0.0, min(1.0, q)) * float(len(sorted_values) - 1)))
    return float(sorted_values[idx])


def _mean(values: Iterable[float]) -> float:
    vals = [float(v) for v in values]
    if not vals:
        return 0.0
    return float(sum(vals) / float(len(vals)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_div(numer: float, denom: float) -> float:
    if abs(float(denom)) < 1e-12:
        return 0.0
    return float(float(numer) / float(denom))


def _rows_to_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fieldnames})


def _load_available_engines() -> Dict[str, Any]:
    from qhpc_cache.qmc_simulation import _load_engines  # type: ignore

    return _load_engines()


def build_template_bank(*, template_bank_id: str = TEMPLATE_BANK_ID_DEFAULT) -> List[Dict[str, Any]]:
    """Compatibility wrapper exported through qhpc_cache.__init__."""
    return _generator_build_template_bank(template_bank_id=template_bank_id)


def generate_repeated_workload_requests(
    *,
    scale_label: str = "standard",
    seed: int = 123,
    lane_selection: str = "both",
    template_bank_id: str = TEMPLATE_BANK_ID_DEFAULT,
    workload_families: Optional[Sequence[str]] = None,
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """Compatibility wrapper exported through qhpc_cache.__init__."""
    return _generator_generate_requests(
        scale_label=scale_label,
        seed=int(seed),
        lane_selection=lane_selection,
        template_bank_id=template_bank_id,
        workload_families=workload_families,
    )


def _request_to_cache_features(request: Dict[str, Any], engine_name: str) -> Dict[str, Any]:
    return {
        "engine": str(engine_name),
        "instrument_type": str(request["payoff_type"]),
        "S0": float(request["S0"]),
        "K": float(request["K"]),
        "r": float(request["r"]),
        "sigma": float(request["sigma"]),
        "T": float(request["T"]),
        "num_paths": int(request["num_paths"]),
        "simulation_mode": str(request.get("simulation_mode", "terminal")),
        "num_time_steps": int(request.get("num_time_steps", 12)),
        "random_seed": int(request["random_seed"]),
    }


def _run_single_request(
    *,
    request: Dict[str, Any],
    engine_name: str,
    engine: Any,
    store: SimpleCacheStore,
    event_index: int,
    last_seen_by_key: Dict[str, int],
    seen_similarity_groups: Dict[str, int],
    seen_feature_hashes: Dict[str, int],
    stable_lane: bool,
    outlier_threshold_ms: float,
    lane_id: str,
) -> Tuple[StudyRow, Optional[Dict[str, Any]]]:
    lookup_start = time.perf_counter()
    features = _request_to_cache_features(request, engine_name)
    request_key = store.make_key(features)
    hit, cached = store.try_get(features, engine_name=engine_name)
    lookup_elapsed_ms = (time.perf_counter() - lookup_start) * 1000.0

    exclusion_reason = ""
    outlier_payload: Optional[Dict[str, Any]] = None
    is_outlier = False
    robust_included = True
    similarity_group_id = str(request.get("similarity_group_id", ""))
    feature_hash = str(request.get("feature_hash", ""))

    prior_similarity_seen = seen_similarity_groups.get(similarity_group_id, 0) if similarity_group_id else 0
    prior_feature_seen = seen_feature_hashes.get(feature_hash, 0) if feature_hash else 0
    similarity_hit = False

    cached_price = 0.0
    cached_std_error = 0.0
    if hit:
        pricing_compute_time_ms = 0.0
        total_runtime_ms = float(lookup_elapsed_ms)
        row_semantics = "lookup_single_attempt"
        cached_compute_ms = _safe_float(cached.get("compute_time_ms"), 0.0) if isinstance(cached, dict) else 0.0
        compute_avoided_proxy = max(0.0, float(cached_compute_ms))
        time_saved_proxy = max(0.0, float(cached_compute_ms) - float(total_runtime_ms))
        if isinstance(cached, dict):
            cached_price = float(cached.get("price", 0.0))
            cached_std_error = float(cached.get("std_error", 0.0))
    else:
        if (prior_similarity_seen > 0) or (prior_feature_seen > 0):
            similarity_hit = True
        engine_start = time.perf_counter()
        result = engine.price(
            S0=float(request["S0"]),
            K=float(request["K"]),
            r=float(request["r"]),
            sigma=float(request["sigma"]),
            T=float(request["T"]),
            num_paths=int(request["num_paths"]),
            seed=int(request["random_seed"]),
        )
        fallback_elapsed_ms = (time.perf_counter() - engine_start) * 1000.0
        pricing_compute_time_ms = float(
            result.wall_clock_ms if float(getattr(result, "wall_clock_ms", 0.0)) > 0.0 else fallback_elapsed_ms
        )
        total_runtime_ms = float(pricing_compute_time_ms)
        row_semantics = "put_single_compute_result"
        compute_avoided_proxy = 0.0
        time_saved_proxy = 0.0
        if math.isfinite(float(result.price)) and math.isfinite(float(result.std_error)):
            store.put(
                features,
                {
                    "price": float(result.price),
                    "std_error": float(result.std_error),
                    "metadata": dict(getattr(result, "metadata", {})),
                    "compute_time_ms": float(pricing_compute_time_ms),
                },
                engine_name=engine_name,
                compute_time_ms=pricing_compute_time_ms,
                stage_elapsed_ms=0.0,
                row_semantics="put_single_compute_result",
            )
        if pricing_compute_time_ms >= float(outlier_threshold_ms):
            is_outlier = True
            if stable_lane:
                robust_included = False
                exclusion_reason = "excluded_pathological_timing_row"
                exclusion_decision = "excluded_from_robust"
            else:
                exclusion_decision = "retained_stress_lane"
            outlier_payload = {
                "lane_id": lane_id,
                "engine": engine_name,
                "workload_family": str(request["workload_family"]),
                "request_id": str(request["request_id"]),
                "contract_id": str(request["contract_id"]),
                "pricing_compute_time_ms": float(pricing_compute_time_ms),
                "row_semantics": row_semantics,
                "exclusion_decision": exclusion_decision,
                "reason": (
                    "pricing_compute_time_ms_above_threshold"
                    if exclusion_decision == "retained_stress_lane"
                    else exclusion_reason
                ),
            }

    if request_key in last_seen_by_key:
        reuse_distance = float(event_index - last_seen_by_key[request_key] - 1)
    else:
        reuse_distance = float("nan")
    last_seen_by_key[request_key] = event_index
    if similarity_group_id:
        seen_similarity_groups[similarity_group_id] = seen_similarity_groups.get(similarity_group_id, 0) + 1
    if feature_hash:
        seen_feature_hashes[feature_hash] = seen_feature_hashes.get(feature_hash, 0) + 1

    row = StudyRow(
        lane_id=str(lane_id),
        workload_family=str(request["workload_family"]),
        engine=str(engine_name),
        request_id=str(request["request_id"]),
        request_key=str(request_key),
        parameter_hash=str(request.get("parameter_hash", "")),
        feature_hash=str(feature_hash),
        cluster_id=str(request.get("cluster_id", "")),
        exact_repeat_group_id=str(request.get("exact_repeat_group_id", "")),
        similarity_group_id=str(similarity_group_id),
        event_window_id=str(request.get("event_window_id", "")),
        cache_hit=bool(hit),
        similarity_hit=bool(similarity_hit),
        row_semantics=row_semantics,
        pricing_compute_time_ms=float(pricing_compute_time_ms),
        total_runtime_ms=float(total_runtime_ms),
        reuse_distance_events=float(reuse_distance),
        robust_included=bool(robust_included),
        is_outlier=bool(is_outlier),
        exclusion_reason=str(exclusion_reason),
        compute_avoided_proxy=float(compute_avoided_proxy),
        time_saved_proxy=float(time_saved_proxy),
        cached_price=float(cached_price),
        cached_std_error=float(cached_std_error),
    )
    return row, outlier_payload


def _calculate_metrics(rows: List[StudyRow], *, include_outliers: bool) -> Dict[str, Any]:
    selected = rows if include_outliers else [r for r in rows if bool(r.robust_included)]
    request_count = int(len(selected))
    unique_request_keys = len(set(r.request_key for r in selected))
    repeated_request_keys = max(0, request_count - unique_request_keys)
    hits = sum(1 for r in selected if bool(r.cache_hit))
    similarity_hits = sum(1 for r in selected if bool(r.similarity_hit))
    misses = sum(1 for r in selected if not bool(r.cache_hit))
    runtimes = [float(r.total_runtime_ms) for r in selected]
    reuse_distances = [
        float(r.reuse_distance_events)
        for r in selected
        if not math.isnan(float(r.reuse_distance_events))
    ]
    mean_reuse_distance = _mean(reuse_distances)
    locality_score = 0.0 if mean_reuse_distance <= 0.0 else float(1.0 / (1.0 + mean_reuse_distance))
    outlier_count = sum(1 for r in rows if bool(r.is_outlier))
    outlier_rate = _safe_div(float(outlier_count), float(len(rows)))
    total_runtime_ms = float(sum(runtimes))
    compute_avoided_proxy = float(sum(float(r.compute_avoided_proxy) for r in selected))
    time_saved_proxy = float(sum(float(r.time_saved_proxy) for r in selected))

    return {
        "request_count": request_count,
        "unique_request_keys": int(unique_request_keys),
        "repeated_request_keys": int(repeated_request_keys),
        "exact_hit_rate": _safe_div(float(hits), float(request_count)),
        "similarity_hit_rate": _safe_div(float(similarity_hits), float(request_count)),
        "miss_rate": _safe_div(float(misses), float(request_count)),
        "mean_reuse_distance": float(mean_reuse_distance),
        "locality_score": float(locality_score),
        "approximate_working_set_size": int(unique_request_keys),
        "total_runtime_ms": float(total_runtime_ms),
        "average_runtime_ms": _mean(runtimes),
        "p50_runtime_ms": _quantile(runtimes, 0.50),
        "p90_runtime_ms": _quantile(runtimes, 0.90),
        "p99_runtime_ms": _quantile(runtimes, 0.99),
        "compute_avoided_proxy": float(compute_avoided_proxy),
        "time_saved_proxy": float(time_saved_proxy),
        "outlier_count": int(outlier_count),
        "outlier_rate": float(outlier_rate),
        "evidence_valid": bool(request_count > 0),
    }


def _build_summary_row(
    *,
    lane_id: str,
    lane_meta: Dict[str, Any],
    family: str,
    seed: int,
    template_bank_id: str,
    raw_metrics: Dict[str, Any],
    robust_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "workload_family": family,
        "lane_id": lane_id,
        "stable_lane_flag": bool(lane_meta["stable_lane_flag"]),
        "stress_lane_flag": bool(lane_meta["stress_lane_flag"]),
        "deterministic_seed": int(seed),
        "template_bank_id": template_bank_id,
        "request_count": int(raw_metrics["request_count"]),
        "unique_request_keys": int(raw_metrics["unique_request_keys"]),
        "repeated_request_keys": int(raw_metrics["repeated_request_keys"]),
        "exact_hit_rate": float(raw_metrics["exact_hit_rate"]),
        "similarity_hit_rate": float(raw_metrics["similarity_hit_rate"]),
        "miss_rate": float(raw_metrics["miss_rate"]),
        "mean_reuse_distance": float(raw_metrics["mean_reuse_distance"]),
        "locality_score": float(raw_metrics["locality_score"]),
        "approximate_working_set_size": int(raw_metrics["approximate_working_set_size"]),
        "total_runtime_ms": float(robust_metrics["total_runtime_ms"]),
        "average_runtime_ms": float(robust_metrics["average_runtime_ms"]),
        "p50_runtime_ms": float(robust_metrics["p50_runtime_ms"]),
        "p90_runtime_ms": float(robust_metrics["p90_runtime_ms"]),
        "p99_runtime_ms": float(robust_metrics["p99_runtime_ms"]),
        "compute_avoided_proxy": float(raw_metrics["compute_avoided_proxy"]),
        "time_saved_proxy": float(raw_metrics["time_saved_proxy"]),
        "outlier_count": int(raw_metrics["outlier_count"]),
        "outlier_rate": float(raw_metrics["outlier_rate"]),
        "raw_total_runtime_ms": float(raw_metrics["total_runtime_ms"]),
        "raw_average_runtime_ms": float(raw_metrics["average_runtime_ms"]),
        "raw_p50_runtime_ms": float(raw_metrics["p50_runtime_ms"]),
        "raw_p90_runtime_ms": float(raw_metrics["p90_runtime_ms"]),
        "raw_p99_runtime_ms": float(raw_metrics["p99_runtime_ms"]),
        "robust_request_count": int(robust_metrics["request_count"]),
        "evidence_valid": bool(raw_metrics["evidence_valid"]),
    }


def _sort_and_rank(rows: List[Dict[str, Any]], score_key: str, rank_key: str, *, reverse: bool = True) -> None:
    ordered = sorted(rows, key=lambda r: float(r.get(score_key, 0.0)), reverse=reverse)
    for idx, row in enumerate(ordered, start=1):
        row[rank_key] = idx


def _build_rankings(summary_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not summary_rows:
        return []

    raw_p99_vals = [float(r["raw_p99_runtime_ms"]) for r in summary_rows]
    robust_p99_vals = [float(r["p99_runtime_ms"]) for r in summary_rows]
    raw_p99_min = min(raw_p99_vals)
    raw_p99_span = max(max(raw_p99_vals) - raw_p99_min, 1e-9)
    robust_p99_min = min(robust_p99_vals)
    robust_p99_span = max(max(robust_p99_vals) - robust_p99_min, 1e-9)

    ranking_rows: List[Dict[str, Any]] = []
    for row in summary_rows:
        unique_ratio = _safe_div(float(row["unique_request_keys"]), float(max(1, row["request_count"])))
        raw_p99_norm = (float(row["raw_p99_runtime_ms"]) - raw_p99_min) / raw_p99_span
        robust_p99_norm = (float(row["p99_runtime_ms"]) - robust_p99_min) / robust_p99_span
        cache_with = (
            0.40 * float(row["exact_hit_rate"])
            + 0.25 * float(row["locality_score"])
            + 0.20 * float(row["similarity_hit_rate"])
            + 0.15 * float(1.0 - raw_p99_norm)
        )
        cache_without = (
            0.40 * float(row["exact_hit_rate"])
            + 0.25 * float(row["locality_score"])
            + 0.20 * float(row["similarity_hit_rate"])
            + 0.15 * float(1.0 - robust_p99_norm)
        )
        stress_with = (
            0.35 * float(row["miss_rate"])
            + 0.25 * float(row["outlier_rate"])
            + 0.20 * float(unique_ratio)
            + 0.20 * float(raw_p99_norm)
        )
        stress_without = (
            0.35 * float(row["miss_rate"])
            + 0.25 * float(row["outlier_rate"])
            + 0.20 * float(unique_ratio)
            + 0.20 * float(robust_p99_norm)
        )
        similarity_support = (
            0.50 * float(row["similarity_hit_rate"])
            + 0.30 * float(row["locality_score"])
            + 0.20 * float(1.0 - unique_ratio)
        )
        hpc_with = 0.45 * stress_with + 0.35 * raw_p99_norm + 0.20 * float(row["outlier_rate"])
        hpc_without = 0.45 * stress_without + 0.35 * robust_p99_norm + 0.20 * float(row["outlier_rate"])
        ranking_rows.append(
            {
                "lane_id": row["lane_id"],
                "workload_family": row["workload_family"],
                "cache_friendliness_score_with_outliers": round(cache_with, 6),
                "cache_friendliness_score_without_outliers": round(cache_without, 6),
                "stress_heaviness_score_with_outliers": round(stress_with, 6),
                "stress_heaviness_score_without_outliers": round(stress_without, 6),
                "similarity_support_score": round(similarity_support, 6),
                "hpc_escalation_score_with_outliers": round(hpc_with, 6),
                "hpc_escalation_score_without_outliers": round(hpc_without, 6),
                "exact_hit_rate": row["exact_hit_rate"],
                "similarity_hit_rate": row["similarity_hit_rate"],
                "miss_rate": row["miss_rate"],
                "locality_score": row["locality_score"],
                "outlier_count": row["outlier_count"],
                "outlier_rate": row["outlier_rate"],
            }
        )

    _sort_and_rank(
        ranking_rows,
        "cache_friendliness_score_with_outliers",
        "cache_friendliness_rank_with_outliers",
        reverse=True,
    )
    _sort_and_rank(
        ranking_rows,
        "cache_friendliness_score_without_outliers",
        "cache_friendliness_rank_without_outliers",
        reverse=True,
    )
    _sort_and_rank(
        ranking_rows,
        "stress_heaviness_score_with_outliers",
        "stress_heaviness_rank_with_outliers",
        reverse=True,
    )
    _sort_and_rank(
        ranking_rows,
        "stress_heaviness_score_without_outliers",
        "stress_heaviness_rank_without_outliers",
        reverse=True,
    )
    _sort_and_rank(ranking_rows, "similarity_support_score", "similarity_support_rank", reverse=True)
    _sort_and_rank(
        ranking_rows,
        "hpc_escalation_score_with_outliers",
        "hpc_escalation_rank_with_outliers",
        reverse=True,
    )
    _sort_and_rank(
        ranking_rows,
        "hpc_escalation_score_without_outliers",
        "hpc_escalation_rank_without_outliers",
        reverse=True,
    )
    ranking_rows.sort(key=lambda r: (int(r["cache_friendliness_rank_without_outliers"]), str(r["lane_id"])))
    return ranking_rows


def _build_timing_summary(summary_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in summary_rows:
        base = {
            "lane_id": row["lane_id"],
            "workload_family": row["workload_family"],
            "outlier_count": row["outlier_count"],
            "outlier_rate": row["outlier_rate"],
        }
        out.append(
            {
                **base,
                "timing_mode": "raw",
                "request_count": row["request_count"],
                "total_runtime_ms": row["raw_total_runtime_ms"],
                "average_runtime_ms": row["raw_average_runtime_ms"],
                "p50_runtime_ms": row["raw_p50_runtime_ms"],
                "p90_runtime_ms": row["raw_p90_runtime_ms"],
                "p99_runtime_ms": row["raw_p99_runtime_ms"],
            }
        )
        out.append(
            {
                **base,
                "timing_mode": "robust",
                "request_count": row["robust_request_count"],
                "total_runtime_ms": row["total_runtime_ms"],
                "average_runtime_ms": row["average_runtime_ms"],
                "p50_runtime_ms": row["p50_runtime_ms"],
                "p90_runtime_ms": row["p90_runtime_ms"],
                "p99_runtime_ms": row["p99_runtime_ms"],
            }
        )
    return out


def _build_cache_summary(summary_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in summary_rows:
        out.append(
            {
                "lane_id": row["lane_id"],
                "workload_family": row["workload_family"],
                "request_count": row["request_count"],
                "unique_request_keys": row["unique_request_keys"],
                "repeated_request_keys": row["repeated_request_keys"],
                "exact_hit_rate": row["exact_hit_rate"],
                "similarity_hit_rate": row["similarity_hit_rate"],
                "miss_rate": row["miss_rate"],
                "mean_reuse_distance": row["mean_reuse_distance"],
                "locality_score": row["locality_score"],
                "approximate_working_set_size": row["approximate_working_set_size"],
                "compute_avoided_proxy": row["compute_avoided_proxy"],
                "time_saved_proxy": row["time_saved_proxy"],
            }
        )
    return out


def _build_family_comparison(summary_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_family_lane: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in summary_rows:
        by_family_lane[(str(row["workload_family"]), str(row["lane_id"]))] = row

    out: List[Dict[str, Any]] = []
    for family in REQUIRED_WORKLOAD_FAMILIES:
        row_a = by_family_lane.get((family, LANE_A_ID), {})
        row_b = by_family_lane.get((family, LANE_B_ID), {})
        out.append(
            {
                "workload_family": family,
                "lane_a_exact_hit_rate": row_a.get("exact_hit_rate", 0.0),
                "lane_b_exact_hit_rate": row_b.get("exact_hit_rate", 0.0),
                "lane_exact_hit_rate_delta_a_minus_b": _safe_float(row_a.get("exact_hit_rate", 0.0))
                - _safe_float(row_b.get("exact_hit_rate", 0.0)),
                "lane_a_similarity_hit_rate": row_a.get("similarity_hit_rate", 0.0),
                "lane_b_similarity_hit_rate": row_b.get("similarity_hit_rate", 0.0),
                "lane_similarity_hit_rate_delta_a_minus_b": _safe_float(row_a.get("similarity_hit_rate", 0.0))
                - _safe_float(row_b.get("similarity_hit_rate", 0.0)),
                "lane_a_average_runtime_ms": row_a.get("average_runtime_ms", 0.0),
                "lane_b_average_runtime_ms": row_b.get("average_runtime_ms", 0.0),
                "lane_runtime_delta_a_minus_b": _safe_float(row_a.get("average_runtime_ms", 0.0))
                - _safe_float(row_b.get("average_runtime_ms", 0.0)),
                "lane_a_locality_score": row_a.get("locality_score", 0.0),
                "lane_b_locality_score": row_b.get("locality_score", 0.0),
                "lane_locality_delta_a_minus_b": _safe_float(row_a.get("locality_score", 0.0))
                - _safe_float(row_b.get("locality_score", 0.0)),
                "lane_a_outlier_count": row_a.get("outlier_count", 0),
                "lane_b_outlier_count": row_b.get("outlier_count", 0),
            }
        )
    return out


def _build_lane_manifest(
    *,
    lane_id: str,
    lane_meta: Dict[str, Any],
    selected_families: List[str],
    active_engines: List[str],
    missing_engines: List[str],
    summary_rows: List[Dict[str, Any]],
    outlier_rows: List[Dict[str, Any]],
    seed: int,
    template_bank_id: str,
    scale_label: str,
) -> Dict[str, Any]:
    lane_evidence_valid = bool(summary_rows)
    lane_exclusion_reason = ""
    if lane_meta["stable_lane_flag"] and missing_engines:
        lane_evidence_valid = False
        lane_exclusion_reason = f"missing_requested_stable_engines:{','.join(missing_engines)}"
    if not any(bool(r.get("evidence_valid", False)) for r in summary_rows):
        lane_evidence_valid = False
        if not lane_exclusion_reason:
            lane_exclusion_reason = "no_valid_family_rows"
    return {
        "lane_id": lane_id,
        "lane_label": lane_meta["lane_label"],
        "stable_lane_flag": bool(lane_meta["stable_lane_flag"]),
        "stress_lane_flag": bool(lane_meta["stress_lane_flag"]),
        "canonical_lane": bool(lane_meta["canonical_lane"]),
        "requested_engines": list(lane_meta["requested_engines"]),
        "active_engines": list(active_engines),
        "missing_engines": list(missing_engines),
        "selected_workload_families": list(selected_families),
        "scale_label": scale_label,
        "deterministic_seed": int(seed),
        "template_bank_id": template_bank_id,
        "summary_rows": summary_rows,
        "outlier_rows_count": int(len(outlier_rows)),
        "evidence_valid": bool(lane_evidence_valid),
        "exclusion_reason": lane_exclusion_reason,
        "generated_at_utc": _utc_now_iso(),
    }


def _plot_hit_rate(summary_rows: List[Dict[str, Any]], output_path: Path) -> None:
    if _HAS_SEABORN:
        sns.set_theme(style="whitegrid")
    labels = [f"{r['lane_id']}::{r['workload_family']}" for r in summary_rows]
    exact_vals = [float(r["exact_hit_rate"]) for r in summary_rows]
    sim_vals = [float(r["similarity_hit_rate"]) for r in summary_rows]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(max(9, len(labels) * 0.7), 4.8))
    ax.bar(x - 0.18, exact_vals, width=0.36, label="exact_hit_rate", color="#2E86AB")
    ax.bar(x + 0.18, sim_vals, width=0.36, label="similarity_hit_rate", color="#00A878")
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Hit rate")
    ax.set_title("Repeated workload hit-rate comparison")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.legend()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def _plot_runtime(summary_rows: List[Dict[str, Any]], output_path: Path) -> None:
    labels = [f"{r['lane_id']}::{r['workload_family']}" for r in summary_rows]
    raw_p90 = [float(r["raw_p90_runtime_ms"]) for r in summary_rows]
    robust_p90 = [float(r["p90_runtime_ms"]) for r in summary_rows]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(max(9, len(labels) * 0.7), 4.8))
    ax.bar(x - 0.18, raw_p90, width=0.36, label="raw p90", color="#A23B72")
    ax.bar(x + 0.18, robust_p90, width=0.36, label="robust p90", color="#6C757D")
    ax.set_ylabel("Runtime (ms)")
    ax.set_title("Repeated workload runtime comparison (raw vs robust)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.legend()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def _plot_locality(summary_rows: List[Dict[str, Any]], output_path: Path) -> None:
    labels = [f"{r['lane_id']}::{r['workload_family']}" for r in summary_rows]
    locality = [float(r["locality_score"]) for r in summary_rows]
    fig, ax = plt.subplots(figsize=(max(9, len(labels) * 0.7), 4.8))
    ax.bar(range(len(labels)), locality, color="#F26419")
    ax.set_ylabel("Locality score")
    ax.set_ylim(0.0, 1.0)
    ax.set_title("Repeated workload locality comparison")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def _plot_rankings(ranking_rows: List[Dict[str, Any]], output_path: Path) -> None:
    x = [float(r["stress_heaviness_score_with_outliers"]) for r in ranking_rows]
    y = [float(r["cache_friendliness_score_without_outliers"]) for r in ranking_rows]
    labels = [f"{r['lane_id']}::{r['workload_family']}" for r in ranking_rows]
    colors = ["#A23B72" if r["lane_id"] == LANE_B_ID else "#2E86AB" for r in ranking_rows]
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    ax.scatter(x, y, c=colors, alpha=0.9)
    for idx, label in enumerate(labels):
        ax.annotate(label, (x[idx], y[idx]), fontsize=7, alpha=0.85)
    ax.set_xlabel("Stress heaviness score (with outliers)")
    ax.set_ylabel("Cache friendliness score (without outliers)")
    ax.set_title("Repeated workload rankings map")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def _top_label(rows: List[Dict[str, Any]], score_key: str) -> str:
    if not rows:
        return "n/a"
    top = sorted(rows, key=lambda r: float(r.get(score_key, 0.0)), reverse=True)[0]
    return f"{top['lane_id']}::{top['workload_family']}"


def _render_rankings_summary(
    *,
    manifest: Dict[str, Any],
    ranking_rows: List[Dict[str, Any]],
    summary_rows: List[Dict[str, Any],
    ],
    outlier_rows: List[Dict[str, Any]],
) -> str:
    monaco_outliers = sum(
        1 for row in outlier_rows if str(row.get("engine", "")) == "monaco_mc"
    )
    lines = [
        "# Repeated Workload Rankings Summary",
        "",
        f"- generated_at_utc: `{manifest['generated_at_utc']}`",
        f"- selected_lanes: `{manifest['selected_lanes']}`",
        f"- selected_workload_families: `{manifest['selected_workload_families']}`",
        f"- outlier_threshold_ms: `{manifest['outlier_threshold_ms']}`",
        "",
        "## Headline rankings",
        "",
        f"- Most cache-friendly (with outliers): `{_top_label(ranking_rows, 'cache_friendliness_score_with_outliers')}`",
        f"- Most cache-friendly (without outliers): `{_top_label(ranking_rows, 'cache_friendliness_score_without_outliers')}`",
        f"- Most stress-heavy (with outliers): `{_top_label(ranking_rows, 'stress_heaviness_score_with_outliers')}`",
        f"- Most stress-heavy (without outliers): `{_top_label(ranking_rows, 'stress_heaviness_score_without_outliers')}`",
        f"- Best similarity-caching support: `{_top_label(ranking_rows, 'similarity_support_score')}`",
        f"- Highest HPC/PMU escalation priority: `{_top_label(ranking_rows, 'hpc_escalation_score_with_outliers')}`",
        "",
        "## Outlier visibility",
        "",
        f"- Total outlier rows above threshold: `{len(outlier_rows)}`",
        f"- Monaco outlier rows retained and visible: `{monaco_outliers}`",
        "",
        "## Lane comparison snapshot",
        "",
        "| lane_id | mean_exact_hit_rate | mean_similarity_hit_rate | mean_locality_score | mean_runtime_ms |",
        "|---|---:|---:|---:|---:|",
    ]
    lane_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in summary_rows:
        lane_groups[str(row["lane_id"])].append(row)
    for lane_id in sorted(lane_groups.keys()):
        rows = lane_groups[lane_id]
        lines.append(
            "| "
            + f"{lane_id} | "
            + f"{_mean(float(r['exact_hit_rate']) for r in rows):.4f} | "
            + f"{_mean(float(r['similarity_hit_rate']) for r in rows):.4f} | "
            + f"{_mean(float(r['locality_score']) for r in rows):.4f} | "
            + f"{_mean(float(r['average_runtime_ms']) for r in rows):.3f} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def run_repeated_workload_study(
    *,
    output_dir: str | Path = "outputs/repeated_workload_phase",
    lane_selection: str = "both",
    workload_families: Optional[Sequence[str]] = None,
    scale_label: str = "standard",
    seed: int = 123,
    template_bank_id: str = TEMPLATE_BANK_ID_DEFAULT,
    outlier_threshold_ms: float = 60_000.0,
    emit_plots: bool = True,
    engine_allowlist_override: Optional[Sequence[str]] = None,
    budget_minutes: float = 0.0,
    requested_backend: str = "cpu_local",
) -> Dict[str, Any]:
    """Run repeated-workload cache study and write research artifacts."""
    _study_t0 = time.perf_counter()
    resolved_scale = _validate_scale_label(scale_label)
    selected_lanes = _normalize_lane_selection(lane_selection)
    selected_families = _normalize_family_selection(workload_families)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    request_bank = _generator_generate_requests(
        scale_label=resolved_scale,
        seed=int(seed),
        lane_selection=lane_selection,
        template_bank_id=template_bank_id,
        workload_families=selected_families,
    )

    engines = _load_available_engines()
    if engine_allowlist_override:
        allow = {str(e) for e in engine_allowlist_override}
        engines = {k: v for k, v in engines.items() if k in allow}

    all_request_rows: List[Dict[str, Any]] = []
    all_result_rows: List[Dict[str, Any]] = []
    summary_rows: List[Dict[str, Any]] = []
    outlier_rows: List[Dict[str, Any]] = []
    lane_manifests: Dict[str, Dict[str, Any]] = {}

    for lane_id in selected_lanes:
        lane_meta = LANE_ENGINE_POLICY[lane_id]
        requested = list(lane_meta["requested_engines"])
        active = [e for e in requested if e in engines]
        missing = [e for e in requested if e not in engines]
        family_summaries: List[Dict[str, Any]] = []
        family_outliers: List[Dict[str, Any]] = []

        for family in selected_families:
            requests = list(request_bank[lane_id][family])
            family_rows: List[StudyRow] = []

            for req in requests:
                all_request_rows.append(
                    {
                        "lane_id": lane_id,
                        "workload_family": family,
                        "request_id": req["request_id"],
                        "cluster_id": req.get("cluster_id", ""),
                        "exact_repeat_group_id": req.get("exact_repeat_group_id", ""),
                        "similarity_group_id": req.get("similarity_group_id", ""),
                        "parameter_hash": req.get("parameter_hash", ""),
                        "feature_hash": req.get("feature_hash", ""),
                        "event_window_id": req.get("event_window_id", ""),
                        "event_window_start": req.get("event_window_start", -1),
                        "event_window_end": req.get("event_window_end", -1),
                        "portfolio_id": req.get("portfolio_id", ""),
                        "contract_id": req["contract_id"],
                        "template_id": req["template_id"],
                        "S0": req["S0"],
                        "K": req["K"],
                        "r": req["r"],
                        "sigma": req["sigma"],
                        "T": req["T"],
                        "num_paths": req["num_paths"],
                        "payoff_type": req["payoff_type"],
                        "simulation_mode": req["simulation_mode"],
                        "deterministic_seed": req["deterministic_seed"],
                        "template_bank_id": template_bank_id,
                        "workload_regime": req.get("workload_regime", ""),
                        "random_seed": req.get("random_seed", req["deterministic_seed"]),
                    }
                )

            for engine_name in active:
                engine = engines[engine_name]
                store = SimpleCacheStore(enable_logging=True)
                last_seen: Dict[str, int] = {}
                seen_similarity_groups: Dict[str, int] = {}
                seen_feature_hashes: Dict[str, int] = {}
                for idx, req in enumerate(requests):
                    row, outlier = _run_single_request(
                        request=req,
                        engine_name=engine_name,
                        engine=engine,
                        store=store,
                        event_index=idx,
                        last_seen_by_key=last_seen,
                        seen_similarity_groups=seen_similarity_groups,
                        seen_feature_hashes=seen_feature_hashes,
                        stable_lane=bool(lane_meta["stable_lane_flag"]),
                        outlier_threshold_ms=float(outlier_threshold_ms),
                        lane_id=lane_id,
                    )
                    family_rows.append(row)
                    all_result_rows.append(
                        {
                            "lane_id": row.lane_id,
                            "workload_family": row.workload_family,
                            "engine": row.engine,
                            "request_id": row.request_id,
                            "request_key_hash": row.request_key[:32],
                            "parameter_hash": row.parameter_hash,
                            "feature_hash": row.feature_hash,
                            "cluster_id": row.cluster_id,
                            "exact_repeat_group_id": row.exact_repeat_group_id,
                            "similarity_group_id": row.similarity_group_id,
                            "event_window_id": row.event_window_id,
                            "cache_hit": row.cache_hit,
                            "similarity_hit": row.similarity_hit,
                            "row_semantics": row.row_semantics,
                            "pricing_compute_time_ms": round(row.pricing_compute_time_ms, 6),
                            "total_runtime_ms": round(row.total_runtime_ms, 6),
                            "reuse_distance_events": row.reuse_distance_events,
                            "robust_included": row.robust_included,
                            "is_outlier": row.is_outlier,
                            "exclusion_reason": row.exclusion_reason,
                            "compute_avoided_proxy": row.compute_avoided_proxy,
                            "time_saved_proxy": row.time_saved_proxy,
                            "S0": float(req["S0"]),
                            "K": float(req["K"]),
                            "r": float(req["r"]),
                            "sigma": float(req["sigma"]),
                            "T": float(req["T"]),
                            "num_paths": int(req["num_paths"]),
                            "workload_regime": str(req.get("workload_regime", "")),
                            "cached_price": row.cached_price,
                            "cached_std_error": row.cached_std_error,
                        }
                    )
                    if outlier:
                        outlier_rows.append(dict(outlier))
                        family_outliers.append(dict(outlier))

            raw_metrics = _calculate_metrics(family_rows, include_outliers=True)
            robust_metrics = _calculate_metrics(family_rows, include_outliers=False)
            summary = _build_summary_row(
                lane_id=lane_id,
                lane_meta=lane_meta,
                family=family,
                seed=int(seed),
                template_bank_id=template_bank_id,
                raw_metrics=raw_metrics,
                robust_metrics=robust_metrics,
            )
            family_summaries.append(summary)
            summary_rows.append(summary)

        lane_manifest = _build_lane_manifest(
            lane_id=lane_id,
            lane_meta=lane_meta,
            selected_families=selected_families,
            active_engines=active,
            missing_engines=missing,
            summary_rows=family_summaries,
            outlier_rows=family_outliers,
            seed=int(seed),
            template_bank_id=template_bank_id,
            scale_label=resolved_scale,
        )
        lane_manifests[lane_id] = lane_manifest
        (out / f"repeated_workload_{lane_id}_manifest.json").write_text(
            json.dumps(lane_manifest, indent=2),
            encoding="utf-8",
        )

    for lane_id in [LANE_A_ID, LANE_B_ID]:
        if lane_id in lane_manifests:
            continue
        lane_meta = LANE_ENGINE_POLICY[lane_id]
        skipped_manifest = {
            "lane_id": lane_id,
            "lane_label": lane_meta["lane_label"],
            "stable_lane_flag": bool(lane_meta["stable_lane_flag"]),
            "stress_lane_flag": bool(lane_meta["stress_lane_flag"]),
            "canonical_lane": bool(lane_meta["canonical_lane"]),
            "requested_engines": list(lane_meta["requested_engines"]),
            "active_engines": [],
            "missing_engines": list(lane_meta["requested_engines"]),
            "selected_workload_families": [],
            "scale_label": resolved_scale,
            "deterministic_seed": int(seed),
            "template_bank_id": template_bank_id,
            "summary_rows": [],
            "outlier_rows_count": 0,
            "evidence_valid": False,
            "exclusion_reason": "skipped_by_lane_selection",
            "generated_at_utc": _utc_now_iso(),
        }
        lane_manifests[lane_id] = skipped_manifest
        (out / f"repeated_workload_{lane_id}_manifest.json").write_text(
            json.dumps(skipped_manifest, indent=2),
            encoding="utf-8",
        )

    ranking_rows = _build_rankings(summary_rows)
    timing_rows = _build_timing_summary(summary_rows)
    cache_rows = _build_cache_summary(summary_rows)
    family_comparison_rows = _build_family_comparison(summary_rows)

    manifest_path = out / "repeated_workload_manifest.json"
    summary_csv = out / "repeated_workload_summary.csv"
    rankings_csv = out / "repeated_workload_rankings.csv"
    rankings_md = out / "repeated_workload_rankings_summary.md"
    timing_csv = out / "repeated_workload_timing_summary.csv"
    cache_csv = out / "repeated_workload_cache_summary.csv"
    family_comparison_csv = out / "repeated_workload_family_comparison.csv"
    requests_csv = out / "repeated_workload_requests.csv"
    results_csv = out / "repeated_workload_results.csv"
    outliers_csv = out / "repeated_workload_outliers.csv"

    _rows_to_csv(
        requests_csv,
        all_request_rows,
        fieldnames=[
            "lane_id",
            "workload_family",
            "request_id",
            "cluster_id",
            "exact_repeat_group_id",
            "similarity_group_id",
            "parameter_hash",
            "feature_hash",
            "event_window_id",
            "event_window_start",
            "event_window_end",
            "portfolio_id",
            "contract_id",
            "template_id",
            "S0",
            "K",
            "r",
            "sigma",
            "T",
            "num_paths",
            "payoff_type",
            "simulation_mode",
            "deterministic_seed",
            "template_bank_id",
        ],
    )
    _rows_to_csv(
        results_csv,
        all_result_rows,
        fieldnames=[
            "lane_id",
            "workload_family",
            "engine",
            "request_id",
            "request_key_hash",
            "parameter_hash",
            "feature_hash",
            "cluster_id",
            "exact_repeat_group_id",
            "similarity_group_id",
            "event_window_id",
            "cache_hit",
            "similarity_hit",
            "row_semantics",
            "pricing_compute_time_ms",
            "total_runtime_ms",
            "reuse_distance_events",
            "robust_included",
            "is_outlier",
            "exclusion_reason",
            "compute_avoided_proxy",
            "time_saved_proxy",
        ],
    )
    _rows_to_csv(
        summary_csv,
        summary_rows,
        fieldnames=[
            "workload_family",
            "lane_id",
            "stable_lane_flag",
            "stress_lane_flag",
            "deterministic_seed",
            "template_bank_id",
            "request_count",
            "unique_request_keys",
            "repeated_request_keys",
            "exact_hit_rate",
            "similarity_hit_rate",
            "miss_rate",
            "mean_reuse_distance",
            "locality_score",
            "approximate_working_set_size",
            "total_runtime_ms",
            "average_runtime_ms",
            "p50_runtime_ms",
            "p90_runtime_ms",
            "p99_runtime_ms",
            "compute_avoided_proxy",
            "time_saved_proxy",
            "outlier_count",
            "outlier_rate",
            "raw_total_runtime_ms",
            "raw_average_runtime_ms",
            "raw_p50_runtime_ms",
            "raw_p90_runtime_ms",
            "raw_p99_runtime_ms",
            "robust_request_count",
            "evidence_valid",
        ],
    )
    _rows_to_csv(
        rankings_csv,
        ranking_rows,
        fieldnames=[
            "lane_id",
            "workload_family",
            "cache_friendliness_score_with_outliers",
            "cache_friendliness_score_without_outliers",
            "cache_friendliness_rank_with_outliers",
            "cache_friendliness_rank_without_outliers",
            "stress_heaviness_score_with_outliers",
            "stress_heaviness_score_without_outliers",
            "stress_heaviness_rank_with_outliers",
            "stress_heaviness_rank_without_outliers",
            "similarity_support_score",
            "similarity_support_rank",
            "hpc_escalation_score_with_outliers",
            "hpc_escalation_score_without_outliers",
            "hpc_escalation_rank_with_outliers",
            "hpc_escalation_rank_without_outliers",
            "exact_hit_rate",
            "similarity_hit_rate",
            "miss_rate",
            "locality_score",
            "outlier_count",
            "outlier_rate",
        ],
    )
    _rows_to_csv(
        timing_csv,
        timing_rows,
        fieldnames=[
            "lane_id",
            "workload_family",
            "timing_mode",
            "request_count",
            "total_runtime_ms",
            "average_runtime_ms",
            "p50_runtime_ms",
            "p90_runtime_ms",
            "p99_runtime_ms",
            "outlier_count",
            "outlier_rate",
        ],
    )
    _rows_to_csv(
        cache_csv,
        cache_rows,
        fieldnames=[
            "lane_id",
            "workload_family",
            "request_count",
            "unique_request_keys",
            "repeated_request_keys",
            "exact_hit_rate",
            "similarity_hit_rate",
            "miss_rate",
            "mean_reuse_distance",
            "locality_score",
            "approximate_working_set_size",
            "compute_avoided_proxy",
            "time_saved_proxy",
        ],
    )
    _rows_to_csv(
        family_comparison_csv,
        family_comparison_rows,
        fieldnames=[
            "workload_family",
            "lane_a_exact_hit_rate",
            "lane_b_exact_hit_rate",
            "lane_exact_hit_rate_delta_a_minus_b",
            "lane_a_similarity_hit_rate",
            "lane_b_similarity_hit_rate",
            "lane_similarity_hit_rate_delta_a_minus_b",
            "lane_a_average_runtime_ms",
            "lane_b_average_runtime_ms",
            "lane_runtime_delta_a_minus_b",
            "lane_a_locality_score",
            "lane_b_locality_score",
            "lane_locality_delta_a_minus_b",
            "lane_a_outlier_count",
            "lane_b_outlier_count",
        ],
    )
    _rows_to_csv(
        outliers_csv,
        outlier_rows,
        fieldnames=[
            "lane_id",
            "engine",
            "workload_family",
            "request_id",
            "contract_id",
            "pricing_compute_time_ms",
            "row_semantics",
            "exclusion_decision",
            "reason",
        ],
    )

    manifest = {
        "study_id": "repeated_workload_phase",
        "generated_at_utc": _utc_now_iso(),
        "scale_label": resolved_scale,
        "deterministic_seed": int(seed),
        "template_bank_id": template_bank_id,
        "lane_selection": lane_selection,
        "selected_lanes": selected_lanes,
        "selected_workload_families": selected_families,
        "outlier_threshold_ms": float(outlier_threshold_ms),
        "lane_manifests": {
            lane: str((out / f"repeated_workload_{lane}_manifest.json").resolve())
            for lane in [LANE_A_ID, LANE_B_ID]
        },
        "summary_rows_count": len(summary_rows),
        "outlier_rows_count": len(outlier_rows),
        "outputs": {
            "repeated_workload_manifest_json": str(manifest_path.resolve()),
            "repeated_workload_summary_csv": str(summary_csv.resolve()),
            "repeated_workload_rankings_csv": str(rankings_csv.resolve()),
            "repeated_workload_rankings_summary_md": str(rankings_md.resolve()),
            "repeated_workload_timing_summary_csv": str(timing_csv.resolve()),
            "repeated_workload_cache_summary_csv": str(cache_csv.resolve()),
            "repeated_workload_family_comparison_csv": str(family_comparison_csv.resolve()),
            "repeated_workload_hit_rate_comparison_png": str(
                (out / "repeated_workload_hit_rate_comparison.png").resolve()
            ),
            "repeated_workload_runtime_comparison_png": str(
                (out / "repeated_workload_runtime_comparison.png").resolve()
            ),
            "repeated_workload_locality_comparison_png": str(
                (out / "repeated_workload_locality_comparison.png").resolve()
            ),
            "repeated_workload_rankings_png": str((out / "repeated_workload_rankings.png").resolve()),
            "repeated_workload_requests_csv": str(requests_csv.resolve()),
            "repeated_workload_results_csv": str(results_csv.resolve()),
            "repeated_workload_outliers_csv": str(outliers_csv.resolve()),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    rankings_summary_text = _render_rankings_summary(
        manifest=manifest,
        ranking_rows=ranking_rows,
        summary_rows=summary_rows,
        outlier_rows=outlier_rows,
    )
    rankings_md.write_text(rankings_summary_text, encoding="utf-8")

    if emit_plots:
        _plot_hit_rate(summary_rows, out / "repeated_workload_hit_rate_comparison.png")
        _plot_runtime(summary_rows, out / "repeated_workload_runtime_comparison.png")
        _plot_locality(summary_rows, out / "repeated_workload_locality_comparison.png")
        _plot_rankings(ranking_rows, out / "repeated_workload_rankings.png")

    # === Evidence bundle generation ===
    study_elapsed_s = time.perf_counter() - _study_t0
    evidence_artifacts: Dict[str, str] = {}
    try:
        from qhpc_cache.cache_evidence_bundle import generate_evidence_bundle
        from qhpc_cache.run_profiles import BudgetUtilization
        from qhpc_cache.hpc_provenance import write_hpc_execution_summary

        budget_tracker = BudgetUtilization(requested_budget_minutes=budget_minutes)
        budget_tracker.finalize(
            study_elapsed_s,
            total_pricings=len(all_result_rows),
            max_pricings=100_000,
        )

        evidence_dir = out / "evidence"
        evidence_artifacts = generate_evidence_bundle(
            all_result_rows,
            evidence_dir,
            run_label=f"repeated_workload_{resolved_scale}_seed{seed}",
            emit_plots=emit_plots,
            requested_backend=requested_backend,
            budget_info=budget_tracker.to_dict(),
        )
        manifest["evidence_bundle"] = evidence_artifacts
        manifest["budget_utilization"] = budget_tracker.to_dict()

        write_hpc_execution_summary(
            out,
            requested_backend=requested_backend,
            run_start_utc=manifest.get("generated_at_utc", ""),
        )
    except Exception as exc:
        manifest["evidence_bundle_error"] = str(exc)

    # === Canonical research bundle ===
    try:
        from qhpc_cache.cacheability_labels import (
            assign_cacheability_labels,
            summarize_cacheability_labels,
        )
        from qhpc_cache.reuse_utility import (
            compute_reuse_utility,
            summarize_utility,
        )
        from qhpc_cache.portfolio_overlap import (
            compute_portfolio_overlap,
            compute_scenario_overlap,
        )
        from qhpc_cache.hpc_utilization_analysis import compute_utilization_breakdown
        from qhpc_cache.research_claims import (
            evaluate_claims,
            write_claims_manifest,
        )
        from qhpc_cache.expanded_metrics import compute_expanded_metrics
        from qhpc_cache.research_honesty import build_honesty_manifest, write_honesty_manifest
        from qhpc_cache.similarity_validation import (
            SimilarityValidator,
            ValidationConfig,
            write_validation_artifacts,
        )
        from qhpc_cache.slm_exports import export_slm_dataset

        research_dir = out / "research"
        research_dir.mkdir(parents=True, exist_ok=True)

        # -- Cacheability labels --
        cacheability_assignments = assign_cacheability_labels(all_result_rows)
        cacheability_summary = summarize_cacheability_labels(cacheability_assignments)
        (research_dir / "cacheability_summary.json").write_text(
            json.dumps(cacheability_summary, indent=2)
        )
        manifest["cacheability_summary"] = cacheability_summary

        label_map = {a.request_id: a.ground_truth_label.value for a in cacheability_assignments}
        for row in all_result_rows:
            row["ground_truth_cacheability_label"] = label_map.get(
                str(row.get("request_id", "")), "undetermined"
            )

        # -- Utility --
        utility_rows = compute_reuse_utility(all_result_rows, policy_tier="exact_only")
        utility_summary = summarize_utility(utility_rows, label=f"seed{seed}")
        (research_dir / "utility_summary.json").write_text(
            json.dumps(utility_summary, indent=2)
        )
        manifest["utility_summary"] = utility_summary

        # -- Portfolio overlap --
        portfolio_metrics = compute_portfolio_overlap(all_request_rows)
        (research_dir / "portfolio_overlap.json").write_text(
            json.dumps([m.to_dict() for m in portfolio_metrics], indent=2)
        )

        scenario_metrics = compute_scenario_overlap(all_request_rows)
        (research_dir / "scenario_overlap.json").write_text(
            json.dumps([m.to_dict() for m in scenario_metrics], indent=2)
        )

        # -- HPC utilization --
        utilization = compute_utilization_breakdown(
            all_result_rows,
            total_wall_clock_ms=study_elapsed_s * 1000.0,
        )
        (research_dir / "hpc_utilization.json").write_text(
            json.dumps(utilization.to_dict(), indent=2)
        )
        manifest["hpc_utilization"] = utilization.to_dict()

        # -- Similarity control-validation --
        req_lookup = {str(r.get("request_id", "")): r for r in all_request_rows}
        validator = SimilarityValidator(ValidationConfig(mode="probabilistic", validation_rate=0.25, seed=seed))
        for row in all_result_rows:
            if row.get("cache_hit"):
                rid = str(row.get("request_id", ""))
                req_data = req_lookup.get(rid)
                if req_data and validator.should_validate(str(row.get("workload_family", ""))):
                    reuse_type = "exact" if not row.get("similarity_hit") else "similarity"
                    for eng_name, eng_obj in engines.items():
                        if eng_name == str(row.get("engine", "")):
                            validator.validate_reuse(
                                request=req_data,
                                engine=eng_obj,
                                reused_result={
                                    "price": float(row.get("cached_price", 0.0)),
                                    "std_error": float(row.get("cached_std_error", 0.0)),
                                },
                                reuse_type=reuse_type,
                                engine_name=eng_name,
                            )
                            break
        validation_paths = write_validation_artifacts(validator, research_dir)
        manifest["similarity_validation"] = validator.summarize()

        # -- Expanded metrics --
        val_dicts = [v.to_dict() for v in validator.results]
        expanded = compute_expanded_metrics(all_result_rows, validation_results=val_dicts)
        (research_dir / "expanded_metrics.json").write_text(json.dumps(expanded, indent=2))
        manifest["expanded_metrics"] = expanded

        # -- Overhead accounting --
        from qhpc_cache.overhead_accounting import (
            compute_overhead_accounting,
            summarize_overhead,
            write_net_utility_summary,
        )
        overhead_rows_list = compute_overhead_accounting(all_result_rows, validation_results=val_dicts)
        overhead_summary = summarize_overhead(overhead_rows_list)
        write_net_utility_summary(overhead_summary, research_dir)
        manifest["net_utility_summary"] = overhead_summary

        # -- Speedup bounds --
        from qhpc_cache.speedup_bounds import compute_speedup_bounds, write_speedup_bounds
        total_pricing_ms = sum(float(r.get("pricing_compute_time_ms", 0)) for r in all_result_rows)
        total_wall_ms = study_elapsed_s * 1000.0
        orch_ms = max(total_wall_ms - total_pricing_ms, 0.0)
        speedup_data = compute_speedup_bounds(
            total_wall_ms=total_wall_ms,
            pricing_compute_ms=total_pricing_ms,
            orchestration_ms=orch_ms,
            overhead_ms=overhead_summary.get("total_overhead_ms", 0.0),
            gross_savings_ms=overhead_summary.get("total_gross_saved_ms", 0.0),
            net_savings_ms=overhead_summary.get("total_net_saved_ms", 0.0),
            total_pricings=len(all_result_rows),
            exact_hit_rate=expanded.get("exact_hit_rate", 0.0),
            similarity_hit_rate=expanded.get("similarity_hit_rate", 0.0),
        )
        write_speedup_bounds(speedup_data, research_dir)
        manifest["speedup_bounds"] = speedup_data

        # -- Artifact contract --
        from qhpc_cache.artifact_contract import ArtifactContract
        contract = ArtifactContract(run_path="repeated_workload")
        contract.mark_generated("cacheability_summary")
        contract.mark_generated("utility_summary")
        contract.mark_generated("portfolio_overlap")
        contract.mark_generated("hpc_utilization")
        contract.mark_generated("similarity_validation_summary")
        if validator.results:
            contract.mark_generated("similarity_validation_examples")
        else:
            contract.mark_skipped("similarity_validation_examples", "no_validations_triggered")
        contract.mark_generated("expanded_metrics")
        contract.mark_generated("speedup_bounds")
        contract.mark_generated("net_utility_summary")

        # -- Research claims --
        families_tested = list(set(str(r.get("workload_family", "")) for r in all_result_rows))
        exact_hits = sum(1 for r in all_result_rows if r.get("cache_hit"))
        total_n = len(all_result_rows) or 1
        claim_evidence = {
            "total_pricings": len(all_result_rows),
            "exact_hit_rate": exact_hits / total_n,
            "families_tested": families_tested,
            "utility_summary": utility_summary,
            "portfolio_overlap": bool(portfolio_metrics),
        }
        evaluated_claims = evaluate_claims(claim_evidence)
        claims_paths = write_claims_manifest(evaluated_claims, research_dir)
        manifest["research_claims"] = claims_paths

        # -- Research honesty --
        active_engines_list = list(engines.keys())
        skipped_engines = {}
        for lane_id_h in selected_lanes:
            lm = LANE_ENGINE_POLICY[lane_id_h]
            for re in lm["requested_engines"]:
                if re not in engines:
                    skipped_engines[re] = "not_available_in_environment"
        honesty_data = build_honesty_manifest(
            engines_available=active_engines_list,
            engines_skipped=skipped_engines,
            similarity_validated=validator.summarize()["validation_count"] > 0,
            validation_coverage=validator.summarize().get("validation_coverage_rate", 0.0) if validator.results else 0.0,
            requested_backend=requested_backend,
            run_label=f"repeated_workload_{resolved_scale}_seed{seed}",
        )
        honesty_paths = write_honesty_manifest(honesty_data, research_dir)
        manifest["research_honesty"] = honesty_paths

        contract.mark_generated("research_claims_json")
        contract.mark_generated("research_claims_md")
        contract.mark_generated("research_honesty_json")
        contract.mark_generated("research_honesty_md")

        # -- SLM export --
        slm_dir = out / "slm_datasets"
        cacheability_dicts = [a.to_dict() for a in cacheability_assignments]
        utility_dicts = [u.to_dict() for u in utility_rows]
        overhead_dicts = [o.to_dict() for o in overhead_rows_list]
        slm_paths = export_slm_dataset(
            all_result_rows,
            slm_dir,
            cacheability_assignments=cacheability_dicts,
            utility_rows=utility_dicts,
            validation_results=val_dicts,
            overhead_rows=overhead_dicts,
            run_label=f"repeated_workload_{resolved_scale}_seed{seed}",
            run_seed=seed,
        )
        manifest["slm_exports"] = slm_paths
        contract.mark_generated("slm_training_jsonl")
        contract.mark_generated("reuse_decision_csv")
        contract.mark_generated("workload_family_csv")
        contract.mark_generated("cacheability_labels_csv")
        contract.mark_generated("slm_manifest")

        contract.write(out)
        manifest["artifact_contract"] = contract.summary()
    except Exception as exc:
        manifest["research_layer_error"] = str(exc)

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "manifest": manifest,
        "manifest_path": str(manifest_path.resolve()),
        "summary_rows": summary_rows,
        "ranking_rows": ranking_rows,
        "outlier_rows": outlier_rows,
        "lane_manifests": lane_manifests,
        "evidence_artifacts": evidence_artifacts,
    }

