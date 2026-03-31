"""Reuse utility framework: evaluates cache decisions jointly on speed AND correctness.

Utility includes:
- latency savings
- pricing error penalty (deviation from recompute)
- risk penalty (std_error deviation)
- false-reuse penalty (policy approved reuse that was incorrect)
- false-miss penalty (policy rejected reuse that was correct)

Framework: utility = latency_savings - error_penalty - risk_penalty - false_reuse_penalty
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class UtilityWeights:
    """Configurable weights for the utility function."""

    latency_weight: float = 1.0
    price_error_penalty: float = 100.0
    std_error_penalty: float = 50.0
    false_reuse_penalty: float = 200.0
    false_miss_penalty: float = 10.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "latency_weight": self.latency_weight,
            "price_error_penalty": self.price_error_penalty,
            "std_error_penalty": self.std_error_penalty,
            "false_reuse_penalty": self.false_reuse_penalty,
            "false_miss_penalty": self.false_miss_penalty,
        }


@dataclass
class ReuseUtilityRow:
    """Per-decision utility evaluation."""

    event_index: int
    request_id: str
    reuse_type: str  # "exact_hit", "similarity_hit", "miss", "false_reuse", "false_miss"
    latency_saved_ms: float
    price_deviation: float
    std_error_deviation: float
    is_false_reuse: bool
    is_false_miss: bool
    utility_score: float
    policy_decision: str
    policy_tier: str
    epistemic_status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_index": self.event_index,
            "request_id": self.request_id,
            "reuse_type": self.reuse_type,
            "latency_saved_ms": round(self.latency_saved_ms, 4),
            "price_deviation": round(self.price_deviation, 8),
            "std_error_deviation": round(self.std_error_deviation, 8),
            "is_false_reuse": self.is_false_reuse,
            "is_false_miss": self.is_false_miss,
            "utility_score": round(self.utility_score, 4),
            "policy_decision": self.policy_decision,
            "policy_tier": self.policy_tier,
            "epistemic_status": self.epistemic_status,
        }


def compute_reuse_utility(
    result_rows: Sequence[Dict[str, Any]],
    *,
    weights: Optional[UtilityWeights] = None,
    policy_tier: str = "exact_only",
) -> List[ReuseUtilityRow]:
    """Evaluate utility of each cache decision in the result stream.

    For exact hits, price_deviation is 0 by construction.
    For similarity hits, deviation is estimated from structural metadata.
    For misses on reusable items, false_miss is flagged.
    """
    if weights is None:
        weights = UtilityWeights()

    rows: List[ReuseUtilityRow] = []
    for idx, r in enumerate(result_rows):
        hit = bool(r.get("cache_hit", False))
        sim_hit = bool(r.get("similarity_hit", False))
        latency_saved = float(r.get("time_saved_proxy", 0.0))
        compute_ms = float(r.get("pricing_compute_time_ms", 0.0))

        gt_label = str(r.get("ground_truth_cacheability_label", ""))
        is_reusable = gt_label in ("exact_reusable", "similarity_reusable_safe")

        price_dev = 0.0
        se_dev = 0.0
        is_false_reuse = False
        is_false_miss = False

        if hit:
            reuse_type = "exact_hit"
            policy_decision = "reuse_approved"
        elif sim_hit:
            reuse_type = "similarity_hit"
            policy_decision = "similarity_reuse_detected"
            price_dev = float(r.get("estimated_price_deviation", 0.0))
            se_dev = float(r.get("estimated_se_deviation", 0.0))
        else:
            reuse_type = "miss"
            policy_decision = "compute_required"
            if is_reusable:
                is_false_miss = True
                policy_decision = "false_miss"

        if hit and gt_label == "similarity_reusable_unsafe":
            is_false_reuse = True
            policy_decision = "false_reuse"

        utility = (
            weights.latency_weight * latency_saved
            - weights.price_error_penalty * abs(price_dev)
            - weights.std_error_penalty * abs(se_dev)
            - weights.false_reuse_penalty * (1.0 if is_false_reuse else 0.0)
            - weights.false_miss_penalty * (1.0 if is_false_miss else 0.0)
        )

        rows.append(ReuseUtilityRow(
            event_index=idx,
            request_id=str(r.get("request_id", "")),
            reuse_type=reuse_type,
            latency_saved_ms=latency_saved,
            price_deviation=price_dev,
            std_error_deviation=se_dev,
            is_false_reuse=is_false_reuse,
            is_false_miss=is_false_miss,
            utility_score=utility,
            policy_decision=policy_decision,
            policy_tier=policy_tier,
            epistemic_status="derived",
        ))

    return rows


def summarize_utility(
    rows: Sequence[ReuseUtilityRow],
    *,
    label: str = "",
) -> Dict[str, Any]:
    """Aggregate utility metrics."""
    n = len(rows)
    if n == 0:
        return {"label": label, "count": 0}

    total_utility = sum(r.utility_score for r in rows)
    false_reuses = sum(1 for r in rows if r.is_false_reuse)
    false_misses = sum(1 for r in rows if r.is_false_miss)
    exact_hits = sum(1 for r in rows if r.reuse_type == "exact_hit")
    sim_hits = sum(1 for r in rows if r.reuse_type == "similarity_hit")
    misses = sum(1 for r in rows if r.reuse_type == "miss")
    latency_saved = sum(r.latency_saved_ms for r in rows)
    utilities = [r.utility_score for r in rows]

    return {
        "label": label,
        "count": n,
        "total_utility": round(total_utility, 4),
        "mean_utility": round(total_utility / n, 4),
        "total_latency_saved_ms": round(latency_saved, 4),
        "exact_hits": exact_hits,
        "similarity_hits": sim_hits,
        "misses": misses,
        "false_reuse_count": false_reuses,
        "false_miss_count": false_misses,
        "false_reuse_rate": round(false_reuses / n, 6) if n > 0 else 0.0,
        "false_miss_rate": round(false_misses / n, 6) if n > 0 else 0.0,
        "utility_p50": round(sorted(utilities)[n // 2], 4) if utilities else 0.0,
        "utility_min": round(min(utilities), 4) if utilities else 0.0,
        "utility_max": round(max(utilities), 4) if utilities else 0.0,
    }


def compare_policy_tiers(
    result_rows: Sequence[Dict[str, Any]],
    *,
    weights: Optional[UtilityWeights] = None,
) -> List[Dict[str, Any]]:
    """Run utility evaluation under each policy tier for comparison."""
    from qhpc_cache.cacheability_labels import PolicyTier

    comparisons: List[Dict[str, Any]] = []
    for tier in PolicyTier:
        utility_rows = compute_reuse_utility(
            result_rows, weights=weights, policy_tier=tier.value,
        )
        summary = summarize_utility(utility_rows, label=tier.value)
        comparisons.append(summary)
    return comparisons
