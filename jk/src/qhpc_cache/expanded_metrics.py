"""Expanded cache metrics beyond hit rate.

Computes the full set of cache research metrics that go beyond
simple hit/miss counting, including useful/harmful hit classification,
validation coverage, policy metrics, and tolerance pass rates.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Sequence


def compute_expanded_metrics(
    result_rows: Sequence[Dict[str, Any]],
    *,
    validation_results: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Compute the full expanded metric set from result rows."""
    n = len(result_rows)
    if n == 0:
        return {"total_requests": 0, "status": "no_data"}

    exact_hits = sum(1 for r in result_rows if r.get("cache_hit"))
    similarity_hits = sum(1 for r in result_rows if r.get("similarity_hit"))
    misses = n - exact_hits - similarity_hits

    gt_labels = [str(r.get("ground_truth_cacheability_label", "")) for r in result_rows]
    reusable_labels = {"exact_reusable", "similarity_reusable_safe"}
    harmful_labels = {"similarity_reusable_unsafe"}

    useful_hits = sum(
        1 for r in result_rows
        if (r.get("cache_hit") or r.get("similarity_hit"))
        and str(r.get("ground_truth_cacheability_label", "")) in reusable_labels
    )
    harmful_hits = sum(
        1 for r in result_rows
        if (r.get("cache_hit") or r.get("similarity_hit"))
        and str(r.get("ground_truth_cacheability_label", "")) in harmful_labels
    )

    accepted_sim = sum(1 for r in result_rows if r.get("similarity_hit") and r.get("cache_hit", False) is False)
    rejected_sim = sum(
        1 for r in result_rows
        if r.get("similarity_group_id") and not r.get("cache_hit") and not r.get("similarity_hit")
    )

    reuse_distances = [
        float(r.get("reuse_distance_events", float("nan")))
        for r in result_rows
        if not math.isnan(float(r.get("reuse_distance_events", float("nan"))))
    ]

    val_count = len(validation_results) if validation_results else 0
    val_validated_ids = {str(v.get("request_id", "")) for v in (validation_results or [])}
    reuse_events = sum(1 for r in result_rows if r.get("cache_hit") or r.get("similarity_hit"))

    val_errors = []
    val_passes = 0
    if validation_results:
        for v in validation_results:
            val_errors.append(float(v.get("relative_error", 0.0)))
            if v.get("tolerance_pass"):
                val_passes += 1

    sorted_rd = sorted(reuse_distances) if reuse_distances else []
    sorted_val_err = sorted(val_errors) if val_errors else []

    by_family: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in result_rows:
        by_family[str(r.get("workload_family", "unknown"))].append(r)

    family_metrics = {}
    for fam, rows in by_family.items():
        fn = len(rows)
        fhits = sum(1 for r in rows if r.get("cache_hit"))
        fsim = sum(1 for r in rows if r.get("similarity_hit"))
        fuseful = sum(
            1 for r in rows
            if (r.get("cache_hit") or r.get("similarity_hit"))
            and str(r.get("ground_truth_cacheability_label", "")) in reusable_labels
        )
        fharmful = sum(
            1 for r in rows
            if (r.get("cache_hit") or r.get("similarity_hit"))
            and str(r.get("ground_truth_cacheability_label", "")) in harmful_labels
        )
        fam_rd = [
            float(r.get("reuse_distance_events", float("nan")))
            for r in rows
            if not math.isnan(float(r.get("reuse_distance_events", float("nan"))))
        ]
        fam_val = [
            v for v in (validation_results or [])
            if str(v.get("workload_family", "")) == fam
        ]
        family_metrics[fam] = {
            "count": fn,
            "exact_hit_rate": round(fhits / fn, 6),
            "similarity_hit_rate": round(fsim / fn, 6),
            "useful_hit_rate": round(fuseful / fn, 6),
            "harmful_hit_rate": round(fharmful / fn, 6),
            "mean_reuse_distance": round(sum(fam_rd) / len(fam_rd), 4) if fam_rd else 0.0,
            "median_reuse_distance": round(sorted(fam_rd)[len(fam_rd) // 2], 4) if fam_rd else 0.0,
            "validation_count": len(fam_val),
            "tolerance_pass_rate": (
                round(sum(1 for v in fam_val if v.get("tolerance_pass")) / len(fam_val), 6)
                if fam_val else 0.0
            ),
        }

    unique_keys = len(set(str(r.get("request_key_hash", r.get("request_id", ""))) for r in result_rows))
    wsg = unique_keys / n if n > 0 else 0.0

    return {
        "total_requests": n,
        "exact_hit_rate": round(exact_hits / n, 6),
        "similarity_hit_rate": round(similarity_hits / n, 6),
        "miss_rate": round(misses / n, 6),
        "useful_hit_rate": round(useful_hits / n, 6),
        "harmful_hit_rate": round(harmful_hits / n, 6),
        "useful_hit_count": useful_hits,
        "harmful_hit_count": harmful_hits,
        "accepted_similarity_count": accepted_sim,
        "rejected_similarity_count": rejected_sim,
        "accepted_similarity_rate": round(accepted_sim / n, 6),
        "rejected_similarity_rate": round(rejected_sim / n, 6),
        "validation_count": val_count,
        "validation_coverage_rate": round(val_count / max(reuse_events, 1), 6),
        "mean_reuse_distance": round(sum(reuse_distances) / len(reuse_distances), 4) if reuse_distances else 0.0,
        "median_reuse_distance": round(sorted_rd[len(sorted_rd) // 2], 4) if sorted_rd else 0.0,
        "reuse_distance_p90": round(sorted_rd[int(len(sorted_rd) * 0.9)], 4) if len(sorted_rd) > 1 else 0.0,
        "temporal_locality_score": (
            round(1.0 / (1.0 + sum(reuse_distances) / len(reuse_distances)), 6)
            if reuse_distances else 0.0
        ),
        "working_set_growth_rate": round(wsg, 6),
        "policy_acceptance_rate": round((exact_hits + similarity_hits) / n, 6),
        "accepted_similarity_error_p50": (
            round(sorted_val_err[len(sorted_val_err) // 2], 8) if sorted_val_err else 0.0
        ),
        "accepted_similarity_error_p90": (
            round(sorted_val_err[int(len(sorted_val_err) * 0.9)], 8) if len(sorted_val_err) > 1 else 0.0
        ),
        "worst_case_similarity_error": round(max(val_errors), 8) if val_errors else 0.0,
        "tolerance_pass_rate": round(val_passes / val_count, 6) if val_count > 0 else 0.0,
        "by_family": family_metrics,
    }
