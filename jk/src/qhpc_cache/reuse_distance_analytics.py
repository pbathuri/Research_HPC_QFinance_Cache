"""Reuse-distance, locality, and working-set analytics for cache research evidence.

Computes mathematically explicit metrics from a stream of cache access events:
- Exact and similarity reuse distances
- Stack-distance percentiles
- Temporal locality scores
- Key-stream entropy
- Hotset concentration
- Working-set size over sliding windows
- Burstiness and periodicity measures
- Locality regime classification
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass
class ReuseDistanceRow:
    """Per-access reuse-distance record."""

    event_index: int
    request_key: str
    exact_reuse_distance: float
    similarity_reuse_distance: float
    first_seen_flag: bool
    cold_start_flag: bool
    hit_after_n_distinct_keys: int
    reuse_distance_bucket: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_index": self.event_index,
            "request_key_hash": self.request_key[:32],
            "exact_reuse_distance": self.exact_reuse_distance,
            "similarity_reuse_distance": self.similarity_reuse_distance,
            "first_seen_flag": self.first_seen_flag,
            "cold_start_flag": self.cold_start_flag,
            "hit_after_n_distinct_keys": self.hit_after_n_distinct_keys,
            "reuse_distance_bucket": self.reuse_distance_bucket,
        }


@dataclass
class LocalityMetrics:
    """Aggregate locality metrics for a key stream."""

    temporal_locality_score: float
    key_stream_entropy: float
    hotset_concentration_ratio: float
    top_k_key_share: float
    burstiness_score: float
    periodicity_score: float
    locality_regime: str
    one_hit_wonder_fraction: float
    stack_distance_p50: float
    stack_distance_p90: float
    stack_distance_p99: float
    total_accesses: int
    unique_keys: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "temporal_locality_score": round(self.temporal_locality_score, 6),
            "key_stream_entropy": round(self.key_stream_entropy, 6),
            "hotset_concentration_ratio": round(self.hotset_concentration_ratio, 6),
            "top_k_key_share": round(self.top_k_key_share, 6),
            "burstiness_score": round(self.burstiness_score, 6),
            "periodicity_score": round(self.periodicity_score, 6),
            "locality_regime": self.locality_regime,
            "one_hit_wonder_fraction": round(self.one_hit_wonder_fraction, 6),
            "stack_distance_p50": round(self.stack_distance_p50, 6),
            "stack_distance_p90": round(self.stack_distance_p90, 6),
            "stack_distance_p99": round(self.stack_distance_p99, 6),
            "total_accesses": self.total_accesses,
            "unique_keys": self.unique_keys,
        }


@dataclass
class WorkingSetWindow:
    """Working-set snapshot for one time window."""

    window_id: int
    time_index_start: int
    time_index_end: int
    working_set_size: int
    cumulative_unique_keys: int
    hotset_coverage: float
    reuse_intensity: float
    miss_pressure: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_id": self.window_id,
            "time_index_start": self.time_index_start,
            "time_index_end": self.time_index_end,
            "working_set_size": self.working_set_size,
            "cumulative_unique_keys": self.cumulative_unique_keys,
            "hotset_coverage": round(self.hotset_coverage, 6),
            "reuse_intensity": round(self.reuse_intensity, 6),
            "miss_pressure": round(self.miss_pressure, 6),
        }


def _quantile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = int(round(max(0.0, min(1.0, q)) * (len(s) - 1)))
    return float(s[idx])


def _bucket_label(distance: float) -> str:
    if math.isnan(distance):
        return "first_access"
    d = int(distance)
    if d == 0:
        return "immediate_reuse"
    if d <= 4:
        return "near_reuse_1_4"
    if d <= 16:
        return "medium_reuse_5_16"
    if d <= 64:
        return "far_reuse_17_64"
    return "distant_reuse_65_plus"


def compute_reuse_distances(
    key_stream: Sequence[str],
    *,
    similarity_group_stream: Optional[Sequence[str]] = None,
) -> List[ReuseDistanceRow]:
    """Compute per-access reuse distance from an ordered key stream.

    Parameters
    ----------
    key_stream : sequence of cache keys (one per access in order)
    similarity_group_stream : optional parallel sequence of similarity group IDs
    """
    last_seen: Dict[str, int] = {}
    last_seen_sim: Dict[str, int] = {}
    distinct_since: Dict[str, int] = {}
    all_seen: set = set()
    rows: List[ReuseDistanceRow] = []

    for idx, key in enumerate(key_stream):
        sim_group = (
            similarity_group_stream[idx]
            if similarity_group_stream and idx < len(similarity_group_stream)
            else ""
        )
        first_seen = key not in all_seen
        all_seen.add(key)

        if key in last_seen:
            exact_rd = float(idx - last_seen[key] - 1)
            distinct_between = len(
                {k for k, pos in last_seen.items() if last_seen[key] < pos < idx}
            )
        else:
            exact_rd = float("nan")
            distinct_between = len(all_seen) - 1

        if sim_group and sim_group in last_seen_sim:
            sim_rd = float(idx - last_seen_sim[sim_group] - 1)
        else:
            sim_rd = float("nan")

        cold_start = first_seen and idx < max(10, len(all_seen))

        rows.append(
            ReuseDistanceRow(
                event_index=idx,
                request_key=key,
                exact_reuse_distance=exact_rd,
                similarity_reuse_distance=sim_rd,
                first_seen_flag=first_seen,
                cold_start_flag=cold_start,
                hit_after_n_distinct_keys=distinct_between,
                reuse_distance_bucket=_bucket_label(exact_rd),
            )
        )

        last_seen[key] = idx
        if sim_group:
            last_seen_sim[sim_group] = idx

    return rows


def compute_locality_metrics(
    key_stream: Sequence[str],
    reuse_rows: Optional[List[ReuseDistanceRow]] = None,
    *,
    top_k: int = 10,
) -> LocalityMetrics:
    """Compute aggregate locality metrics from a key stream."""
    n = len(key_stream)
    if n == 0:
        return LocalityMetrics(
            temporal_locality_score=0.0,
            key_stream_entropy=0.0,
            hotset_concentration_ratio=0.0,
            top_k_key_share=0.0,
            burstiness_score=0.0,
            periodicity_score=0.0,
            locality_regime="empty",
            one_hit_wonder_fraction=0.0,
            stack_distance_p50=0.0,
            stack_distance_p90=0.0,
            stack_distance_p99=0.0,
            total_accesses=0,
            unique_keys=0,
        )

    counts = Counter(key_stream)
    unique = len(counts)

    # Shannon entropy of key frequency distribution
    total = float(n)
    entropy = 0.0
    for c in counts.values():
        p = float(c) / total
        if p > 0:
            entropy -= p * math.log2(p)
    max_entropy = math.log2(unique) if unique > 1 else 1.0
    normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

    # Top-k concentration
    top_k_keys = sorted(counts.values(), reverse=True)[:top_k]
    top_k_share = sum(top_k_keys) / total if total > 0 else 0.0

    # Hotset: keys responsible for 80% of accesses
    sorted_counts = sorted(counts.values(), reverse=True)
    cumsum = 0.0
    hotset_size = 0
    for c in sorted_counts:
        cumsum += c
        hotset_size += 1
        if cumsum >= 0.8 * total:
            break
    hotset_concentration = 1.0 - (float(hotset_size) / float(unique)) if unique > 0 else 0.0

    # One-hit wonders
    one_hit_count = sum(1 for c in counts.values() if c == 1)
    one_hit_fraction = float(one_hit_count) / float(unique) if unique > 0 else 0.0

    # Reuse distances for stack-distance percentiles
    if reuse_rows is None:
        reuse_rows = compute_reuse_distances(key_stream)
    finite_distances = [
        r.exact_reuse_distance
        for r in reuse_rows
        if not math.isnan(r.exact_reuse_distance)
    ]
    mean_rd = (sum(finite_distances) / len(finite_distances)) if finite_distances else float("inf")
    temporal_locality = 1.0 / (1.0 + mean_rd) if math.isfinite(mean_rd) else 0.0

    # Burstiness: coefficient of variation of inter-access times per key
    access_positions: Dict[str, List[int]] = defaultdict(list)
    for idx, key in enumerate(key_stream):
        access_positions[key].append(idx)
    cv_values: List[float] = []
    for positions in access_positions.values():
        if len(positions) < 3:
            continue
        gaps = [float(positions[i + 1] - positions[i]) for i in range(len(positions) - 1)]
        mean_gap = sum(gaps) / len(gaps)
        if mean_gap > 0:
            std_gap = (sum((g - mean_gap) ** 2 for g in gaps) / len(gaps)) ** 0.5
            cv_values.append(std_gap / mean_gap)
    burstiness = (sum(cv_values) / len(cv_values)) if cv_values else 0.0

    # Periodicity: fraction of keys with roughly periodic access patterns
    periodic_count = 0
    checked_count = 0
    for positions in access_positions.values():
        if len(positions) < 4:
            continue
        checked_count += 1
        gaps = [float(positions[i + 1] - positions[i]) for i in range(len(positions) - 1)]
        mean_gap = sum(gaps) / len(gaps)
        if mean_gap > 0:
            relative_devs = [abs(g - mean_gap) / mean_gap for g in gaps]
            if (sum(relative_devs) / len(relative_devs)) < 0.3:
                periodic_count += 1
    periodicity = float(periodic_count) / float(checked_count) if checked_count > 0 else 0.0

    # Locality regime classification
    regime = _classify_locality_regime(
        temporal_locality=temporal_locality,
        hotset_concentration=hotset_concentration,
        one_hit_fraction=one_hit_fraction,
        burstiness=burstiness,
        normalized_entropy=normalized_entropy,
    )

    return LocalityMetrics(
        temporal_locality_score=temporal_locality,
        key_stream_entropy=normalized_entropy,
        hotset_concentration_ratio=hotset_concentration,
        top_k_key_share=top_k_share,
        burstiness_score=burstiness,
        periodicity_score=periodicity,
        locality_regime=regime,
        one_hit_wonder_fraction=one_hit_fraction,
        stack_distance_p50=_quantile(finite_distances, 0.50),
        stack_distance_p90=_quantile(finite_distances, 0.90),
        stack_distance_p99=_quantile(finite_distances, 0.99),
        total_accesses=n,
        unique_keys=unique,
    )


def _classify_locality_regime(
    *,
    temporal_locality: float,
    hotset_concentration: float,
    one_hit_fraction: float,
    burstiness: float,
    normalized_entropy: float,
) -> str:
    if temporal_locality > 0.5 and hotset_concentration > 0.7:
        return "strong_temporal_locality"
    if temporal_locality > 0.3 and hotset_concentration > 0.4:
        return "moderate_temporal_locality"
    if one_hit_fraction > 0.8 and normalized_entropy > 0.9:
        return "streaming_no_reuse"
    if burstiness > 1.5 and hotset_concentration > 0.3:
        return "bursty_hotset"
    if 0.1 < temporal_locality <= 0.3:
        return "weak_temporal_locality"
    if normalized_entropy < 0.5 and hotset_concentration > 0.5:
        return "skewed_popularity"
    return "mixed_or_indeterminate"


def compute_working_set_timeline(
    key_stream: Sequence[str],
    hit_stream: Sequence[bool],
    *,
    window_size: int = 50,
    top_k: int = 10,
) -> List[WorkingSetWindow]:
    """Compute working-set dynamics over sliding windows."""
    n = len(key_stream)
    if n == 0:
        return []

    global_counts = Counter(key_stream)
    global_top_keys = set(
        k for k, _ in sorted(global_counts.items(), key=lambda x: -x[1])[:top_k]
    )
    cumulative_seen: set = set()
    windows: List[WorkingSetWindow] = []

    for win_idx, start in enumerate(range(0, n, window_size)):
        end = min(start + window_size, n)
        window_keys = key_stream[start:end]
        window_hits = hit_stream[start:end]

        window_unique = set(window_keys)
        cumulative_seen.update(window_unique)

        hits_in_window = sum(1 for h in window_hits if h)
        misses_in_window = len(window_hits) - hits_in_window
        hotset_keys_in_window = window_unique & global_top_keys
        hotset_coverage = (
            float(len(hotset_keys_in_window)) / float(len(global_top_keys))
            if global_top_keys
            else 0.0
        )
        window_total = float(end - start)
        reuse_intensity = 1.0 - (float(len(window_unique)) / window_total) if window_total > 0 else 0.0
        miss_pressure = float(misses_in_window) / window_total if window_total > 0 else 0.0

        windows.append(
            WorkingSetWindow(
                window_id=win_idx,
                time_index_start=start,
                time_index_end=end,
                working_set_size=len(window_unique),
                cumulative_unique_keys=len(cumulative_seen),
                hotset_coverage=hotset_coverage,
                reuse_intensity=reuse_intensity,
                miss_pressure=miss_pressure,
            )
        )

    return windows


def build_locality_summary_csv_rows(
    locality: LocalityMetrics,
    *,
    label: str = "",
    workload_family: str = "",
    lane_id: str = "",
) -> List[Dict[str, Any]]:
    """Format locality metrics as CSV-ready rows."""
    row = locality.to_dict()
    row["label"] = label
    row["workload_family"] = workload_family
    row["lane_id"] = lane_id
    return [row]
