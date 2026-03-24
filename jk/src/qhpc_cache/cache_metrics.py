"""Advanced cache research metrics: reuse distance, locality, efficiency, per-policy comparison.

Definitions follow cache theory conventions adapted for finance workloads:

- **Exact hit rate**: fraction of lookups that match an existing cache key exactly.
- **Similarity hit rate**: fraction of lookups where a near-match (within threshold)
  was found, enabling approximate reuse.
- **Reuse distance**: number of distinct keys accessed between two consecutive accesses
  to the same key.  Lower means higher temporal locality.
- **Locality score**: 1 / (1 + mean_reuse_distance).  Ranges (0, 1]; higher is better.
- **Cache efficiency**: (estimated_compute_avoided) / (total_compute_if_no_cache).
  Summarizes the fraction of work actually saved.
- **Critical cache window score**: fraction of high-risk event-window lookups served
  from cache (stress-scenario reuse effectiveness).

## Workload-family observations

Per–workload-family snapshots (portfolio / model / pipeline stage, feature-space sizes,
event-window stress flag) are logged to ``workload_cache_observations.csv`` via
``metrics_sink.WorkloadCacheObservationRow`` and ``cache_workload_mapping.record_workload_cache_snapshot``.
This complements aggregate ``CacheMetricRow`` rows without replacing them.
"""

from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from qhpc_cache.metrics_sink import CacheMetricRow, log_cache


@dataclass
class CacheAccessRecord:
    """One lookup against the cache."""
    key: str
    hit: bool
    similarity_hit: bool = False
    compute_time_saved: float = 0.0
    compute_time_if_miss: float = 0.0


@dataclass
class CacheResearchTracker:
    """Accumulates access records and computes research-grade cache metrics.

    Maintains a bounded access log for reuse-distance computation (bounded to
    ``max_history`` to avoid unbounded memory on long runs).
    """

    policy_name: str = "default"
    max_history: int = 100_000

    _access_log: List[CacheAccessRecord] = field(default_factory=list, repr=False)
    _key_last_seen: Dict[str, int] = field(default_factory=dict, repr=False)
    _reuse_distances: List[int] = field(default_factory=list, repr=False)
    _total_lookups: int = 0
    _exact_hits: int = 0
    _similarity_hits: int = 0
    _misses: int = 0
    _evictions: int = 0
    _total_compute_saved: float = 0.0
    _total_compute_possible: float = 0.0

    def record_access(self, rec: CacheAccessRecord) -> None:
        idx = self._total_lookups
        self._total_lookups += 1
        if rec.hit:
            self._exact_hits += 1
        elif rec.similarity_hit:
            self._similarity_hits += 1
        else:
            self._misses += 1

        self._total_compute_saved += rec.compute_time_saved
        self._total_compute_possible += rec.compute_time_if_miss

        if rec.key in self._key_last_seen:
            dist = self._count_distinct_keys_since(self._key_last_seen[rec.key])
            self._reuse_distances.append(dist)
        self._key_last_seen[rec.key] = idx

        if len(self._access_log) < self.max_history:
            self._access_log.append(rec)

    def record_eviction(self) -> None:
        self._evictions += 1

    def _count_distinct_keys_since(self, prev_index: int) -> int:
        start = max(0, prev_index + 1)
        end = min(len(self._access_log), self._total_lookups)
        seen: set = set()
        for i in range(start, end):
            if i < len(self._access_log):
                seen.add(self._access_log[i].key)
        return len(seen)

    @property
    def exact_hit_rate(self) -> float:
        return self._exact_hits / max(1, self._total_lookups)

    @property
    def similarity_hit_rate(self) -> float:
        return self._similarity_hits / max(1, self._total_lookups)

    @property
    def miss_rate(self) -> float:
        return self._misses / max(1, self._total_lookups)

    @property
    def mean_reuse_distance(self) -> float:
        if not self._reuse_distances:
            return float("inf")
        return sum(self._reuse_distances) / len(self._reuse_distances)

    @property
    def locality_score(self) -> float:
        """1 / (1 + mean_reuse_distance).  Higher is better."""
        mrd = self.mean_reuse_distance
        if math.isinf(mrd):
            return 0.0
        return 1.0 / (1.0 + mrd)

    @property
    def cache_efficiency(self) -> float:
        if self._total_compute_possible <= 0:
            return 0.0
        return self._total_compute_saved / self._total_compute_possible

    def summary(self) -> Dict[str, Any]:
        return {
            "policy_name": self.policy_name,
            "total_lookups": self._total_lookups,
            "exact_hits": self._exact_hits,
            "similarity_hits": self._similarity_hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "exact_hit_rate": round(self.exact_hit_rate, 6),
            "similarity_hit_rate": round(self.similarity_hit_rate, 6),
            "miss_rate": round(self.miss_rate, 6),
            "mean_reuse_distance": round(self.mean_reuse_distance, 2) if not math.isinf(self.mean_reuse_distance) else None,
            "locality_score": round(self.locality_score, 6),
            "cache_efficiency": round(self.cache_efficiency, 6),
            "estimated_compute_avoided_seconds": round(self._total_compute_saved, 4),
            "total_compute_if_no_cache_seconds": round(self._total_compute_possible, 4),
        }

    def flush_to_csv(self, run_id: str = "") -> None:
        log_cache(CacheMetricRow(
            run_id=run_id,
            policy_name=self.policy_name,
            exact_hits=self._exact_hits,
            similarity_hits=self._similarity_hits,
            misses=self._misses,
            evictions=self._evictions,
            reuse_distance_mean=round(self.mean_reuse_distance, 4) if not math.isinf(self.mean_reuse_distance) else -1.0,
            locality_score=round(self.locality_score, 6),
            estimated_compute_avoided_seconds=round(self._total_compute_saved, 4),
            cache_efficiency=round(self.cache_efficiency, 6),
        ))


def compare_policies(trackers: Sequence[CacheResearchTracker]) -> List[Dict[str, Any]]:
    """Side-by-side summary table for multiple cache policies."""
    return [t.summary() for t in trackers]


def flush_workload_observation(
    *,
    run_id: str,
    tracker: CacheResearchTracker,
    pipeline_stage: str,
    portfolio_family: str,
    model_family: str,
    feature_dim_before: int = 0,
    feature_dim_after: int = 0,
    event_window_stress: bool = False,
    working_set_pressure: float = 0.0,
    workload_spine_id: str = "",
    workload_spine_rank: int = 0,
    notes: str = "",
) -> None:
    """Convenience wrapper for ``cache_workload_mapping.record_workload_cache_snapshot``."""
    from qhpc_cache.cache_workload_mapping import record_workload_cache_snapshot

    record_workload_cache_snapshot(
        run_id=run_id,
        tracker=tracker,
        pipeline_stage=pipeline_stage,
        portfolio_family=portfolio_family,
        model_family=model_family,
        feature_dim_before=feature_dim_before,
        feature_dim_after=feature_dim_after,
        event_window_stress=event_window_stress,
        working_set_pressure=working_set_pressure,
        workload_spine_id=workload_spine_id,
        workload_spine_rank=workload_spine_rank,
        notes=notes,
    )


def format_cache_metric_report(trackers: Sequence[CacheResearchTracker]) -> str:
    """Markdown comparison table."""
    lines = ["## Cache Policy Comparison", ""]
    header = "| Policy | Lookups | Exact HR | Sim HR | Miss R | Locality | Efficiency |"
    sep = "|--------|---------|----------|--------|--------|----------|------------|"
    lines.extend([header, sep])
    for t in trackers:
        s = t.summary()
        lines.append(
            f"| {s['policy_name']} | {s['total_lookups']} | "
            f"{s['exact_hit_rate']:.4f} | {s['similarity_hit_rate']:.4f} | "
            f"{s['miss_rate']:.4f} | {s['locality_score']:.4f} | "
            f"{s['cache_efficiency']:.4f} |"
        )
    return "\n".join(lines)
