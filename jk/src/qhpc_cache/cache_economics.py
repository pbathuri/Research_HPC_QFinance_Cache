"""Cache value and economics layer for quantifying net computational benefit.

Measures whether caching produced genuine computational savings, decomposed by:
- Exact reuse savings
- Similarity reuse savings (with approximation cost accounting)
- Lookup overhead
- Miss penalty distribution
- Net cache value ratio
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class CacheEconomicsRow:
    """Per-access economic accounting."""

    event_index: int
    request_key_hash: str
    cache_hit: bool
    similarity_hit: bool
    lookup_overhead_ms: float
    compute_time_ms: float
    saved_compute_ms: float
    net_value_ms: float
    reuse_type: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_index": self.event_index,
            "request_key_hash": self.request_key_hash,
            "cache_hit": self.cache_hit,
            "similarity_hit": self.similarity_hit,
            "lookup_overhead_ms": round(self.lookup_overhead_ms, 6),
            "compute_time_ms": round(self.compute_time_ms, 6),
            "saved_compute_ms": round(self.saved_compute_ms, 6),
            "net_value_ms": round(self.net_value_ms, 6),
            "reuse_type": self.reuse_type,
        }


@dataclass
class CacheEconomicsSummary:
    """Aggregate economics for a run/policy/family."""

    label: str
    total_accesses: int
    exact_hits: int
    similarity_hits: int
    misses: int
    total_lookup_overhead_ms: float
    total_saved_compute_ms_exact: float
    total_saved_compute_ms_similarity: float
    total_compute_ms_on_misses: float
    cache_storage_events: int
    overwrite_events: int
    net_cache_value_ms: float
    net_cache_value_ratio: float
    net_benefit_flag: bool
    benefit_per_hit: float
    miss_penalty_mean_ms: float
    miss_penalty_p50_ms: float
    miss_penalty_p90_ms: float
    miss_penalty_p99_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "total_accesses": self.total_accesses,
            "exact_hits": self.exact_hits,
            "similarity_hits": self.similarity_hits,
            "misses": self.misses,
            "total_lookup_overhead_ms": round(self.total_lookup_overhead_ms, 4),
            "total_saved_compute_ms_exact": round(self.total_saved_compute_ms_exact, 4),
            "total_saved_compute_ms_similarity": round(self.total_saved_compute_ms_similarity, 4),
            "total_compute_ms_on_misses": round(self.total_compute_ms_on_misses, 4),
            "cache_storage_events": self.cache_storage_events,
            "overwrite_events": self.overwrite_events,
            "net_cache_value_ms": round(self.net_cache_value_ms, 4),
            "net_cache_value_ratio": round(self.net_cache_value_ratio, 6),
            "net_benefit_flag": self.net_benefit_flag,
            "benefit_per_hit": round(self.benefit_per_hit, 4),
            "miss_penalty_mean_ms": round(self.miss_penalty_mean_ms, 4),
            "miss_penalty_p50_ms": round(self.miss_penalty_p50_ms, 4),
            "miss_penalty_p90_ms": round(self.miss_penalty_p90_ms, 4),
            "miss_penalty_p99_ms": round(self.miss_penalty_p99_ms, 4),
        }


@dataclass
class SimilarityAcceptanceRow:
    """Per-event similarity acceptance/rejection record."""

    event_index: int
    source_key_hash: str
    target_key_hash: str
    similarity_score: float
    accepted: bool
    estimated_pricing_delta: float
    reuse_savings_ms: float
    approximation_error_abs: float
    approximation_error_rel: float
    policy_decision_reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_index": self.event_index,
            "source_key_hash": self.source_key_hash,
            "target_key_hash": self.target_key_hash,
            "similarity_score": round(self.similarity_score, 6),
            "accepted": self.accepted,
            "estimated_pricing_delta": round(self.estimated_pricing_delta, 6),
            "reuse_savings_ms": round(self.reuse_savings_ms, 4),
            "approximation_error_abs": round(self.approximation_error_abs, 6),
            "approximation_error_rel": round(self.approximation_error_rel, 6),
            "policy_decision_reason": self.policy_decision_reason,
        }


@dataclass
class PolicyFrontierRow:
    """One point on the similarity threshold/quality frontier."""

    threshold: float
    acceptance_count: int
    mean_error: float
    max_error: float
    time_saved_ms: float
    net_benefit_ms: float
    rejected_safe_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "threshold": round(self.threshold, 4),
            "acceptance_count": self.acceptance_count,
            "mean_error": round(self.mean_error, 6),
            "max_error": round(self.max_error, 6),
            "time_saved_ms": round(self.time_saved_ms, 4),
            "net_benefit_ms": round(self.net_benefit_ms, 4),
            "rejected_safe_count": self.rejected_safe_count,
        }


def _quantile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = int(round(max(0.0, min(1.0, q)) * (len(s) - 1)))
    return float(s[idx])


def compute_economics_from_rows(
    rows: Sequence[Dict[str, Any]],
    *,
    label: str = "",
) -> CacheEconomicsSummary:
    """Compute economics summary from result rows with standardized fields.

    Expected fields per row:
    - cache_hit (bool)
    - similarity_hit (bool)
    - lookup_overhead_ms or total_runtime_ms (float, for hits)
    - pricing_compute_time_ms (float)
    - compute_avoided_proxy (float)
    - time_saved_proxy (float)
    """
    exact_hits = 0
    sim_hits = 0
    misses = 0
    storage_events = 0
    overwrite_events = 0
    total_lookup_overhead = 0.0
    saved_exact = 0.0
    saved_sim = 0.0
    compute_on_misses = 0.0
    miss_penalties: List[float] = []

    for r in rows:
        is_hit = bool(r.get("cache_hit", False))
        is_sim = bool(r.get("similarity_hit", False))
        compute_ms = float(r.get("pricing_compute_time_ms", 0.0))
        lookup_ms = float(r.get("total_runtime_ms", 0.0)) if is_hit else 0.0
        avoided = float(r.get("compute_avoided_proxy", 0.0))
        saved = float(r.get("time_saved_proxy", 0.0))

        total_lookup_overhead += lookup_ms

        if is_hit:
            exact_hits += 1
            saved_exact += saved
        elif is_sim:
            sim_hits += 1
            saved_sim += saved
        else:
            misses += 1
            compute_on_misses += compute_ms
            miss_penalties.append(compute_ms)
            storage_events += 1

    total_hits = exact_hits + sim_hits
    total_saved = saved_exact + saved_sim
    net_value = total_saved - total_lookup_overhead
    total_compute = compute_on_misses + total_lookup_overhead
    net_ratio = net_value / total_compute if total_compute > 0 else 0.0
    benefit_per = net_value / total_hits if total_hits > 0 else 0.0
    mean_penalty = (sum(miss_penalties) / len(miss_penalties)) if miss_penalties else 0.0

    return CacheEconomicsSummary(
        label=label,
        total_accesses=len(rows),
        exact_hits=exact_hits,
        similarity_hits=sim_hits,
        misses=misses,
        total_lookup_overhead_ms=total_lookup_overhead,
        total_saved_compute_ms_exact=saved_exact,
        total_saved_compute_ms_similarity=saved_sim,
        total_compute_ms_on_misses=compute_on_misses,
        cache_storage_events=storage_events,
        overwrite_events=overwrite_events,
        net_cache_value_ms=net_value,
        net_cache_value_ratio=net_ratio,
        net_benefit_flag=net_value > 0.0,
        benefit_per_hit=benefit_per,
        miss_penalty_mean_ms=mean_penalty,
        miss_penalty_p50_ms=_quantile(miss_penalties, 0.50),
        miss_penalty_p90_ms=_quantile(miss_penalties, 0.90),
        miss_penalty_p99_ms=_quantile(miss_penalties, 0.99),
    )


def compute_similarity_decomposition(
    rows: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Decompose hit rates into exact/similarity with full accounting.

    Returns dict with:
    - exact_hit_count, exact_hit_rate
    - similarity_candidate_count, similarity_accepted_count, similarity_rejected_count
    - similarity_hit_rate, combined_hit_rate
    """
    total = len(rows)
    exact_hits = sum(1 for r in rows if r.get("cache_hit"))
    sim_candidates = sum(1 for r in rows if r.get("similarity_group_id"))
    sim_accepted = sum(
        1 for r in rows if r.get("similarity_hit") and not r.get("cache_hit")
    )
    sim_rejected = max(0, sim_candidates - sim_accepted - exact_hits)

    return {
        "total_accesses": total,
        "exact_hit_count": exact_hits,
        "exact_hit_rate": float(exact_hits) / total if total > 0 else 0.0,
        "similarity_candidate_count": sim_candidates,
        "similarity_accepted_count": sim_accepted,
        "similarity_rejected_count": sim_rejected,
        "similarity_hit_rate": float(sim_accepted) / total if total > 0 else 0.0,
        "combined_hit_rate": float(exact_hits + sim_accepted) / total if total > 0 else 0.0,
    }


def compute_policy_frontier(
    similarity_rows: Sequence[SimilarityAcceptanceRow],
    *,
    thresholds: Optional[Sequence[float]] = None,
) -> List[PolicyFrontierRow]:
    """Sweep similarity thresholds to build quality/savings frontier."""
    if thresholds is None:
        thresholds = [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.98, 0.99]

    frontier: List[PolicyFrontierRow] = []
    for thresh in thresholds:
        accepted = [r for r in similarity_rows if r.similarity_score >= thresh]
        rejected = [r for r in similarity_rows if r.similarity_score < thresh]
        errors = [r.approximation_error_abs for r in accepted if r.accepted]
        safe_rejected = sum(
            1 for r in rejected if r.approximation_error_abs < 0.01
        )
        time_saved = sum(r.reuse_savings_ms for r in accepted if r.accepted)
        mean_err = (sum(errors) / len(errors)) if errors else 0.0
        max_err = max(errors) if errors else 0.0
        net_benefit = time_saved  # overhead already subtracted in per-row accounting

        frontier.append(
            PolicyFrontierRow(
                threshold=thresh,
                acceptance_count=len(accepted),
                mean_error=mean_err,
                max_error=max_err,
                time_saved_ms=time_saved,
                net_benefit_ms=net_benefit,
                rejected_safe_count=safe_rejected,
            )
        )

    return frontier
