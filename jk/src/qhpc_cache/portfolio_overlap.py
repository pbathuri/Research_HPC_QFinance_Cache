"""Portfolio-level overlap and reuse evidence.

Extends call-centric analysis to portfolio-level metrics:
- Cross-position parameter overlap
- Scenario overlap across positions
- Cluster condensation quality
- Rebalance-day workload duplication
- Factor/risk bucket overlap
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


@dataclass
class PortfolioOverlapMetrics:
    """Portfolio-level overlap summary."""

    portfolio_id: str
    position_count: int
    unique_param_hashes: int
    duplicate_param_hashes: int
    param_overlap_ratio: float
    unique_feature_hashes: int
    feature_overlap_ratio: float
    cluster_count: int
    mean_cluster_size: float
    max_cluster_size: int
    intra_cluster_similarity: float
    cross_cluster_distinctness: float
    condensation_potential: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "position_count": self.position_count,
            "unique_param_hashes": self.unique_param_hashes,
            "duplicate_param_hashes": self.duplicate_param_hashes,
            "param_overlap_ratio": round(self.param_overlap_ratio, 6),
            "unique_feature_hashes": self.unique_feature_hashes,
            "feature_overlap_ratio": round(self.feature_overlap_ratio, 6),
            "cluster_count": self.cluster_count,
            "mean_cluster_size": round(self.mean_cluster_size, 2),
            "max_cluster_size": self.max_cluster_size,
            "intra_cluster_similarity": round(self.intra_cluster_similarity, 6),
            "cross_cluster_distinctness": round(self.cross_cluster_distinctness, 6),
            "condensation_potential": round(self.condensation_potential, 6),
        }


@dataclass
class ScenarioOverlapMetrics:
    """Scenario-level overlap across positions or event windows."""

    scenario_id: str
    total_requests: int
    overlapping_requests: int
    overlap_ratio: float
    event_window_overlap_score: float
    portfolio_overlap_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "total_requests": self.total_requests,
            "overlapping_requests": self.overlapping_requests,
            "overlap_ratio": round(self.overlap_ratio, 6),
            "event_window_overlap_score": round(self.event_window_overlap_score, 6),
            "portfolio_overlap_score": round(self.portfolio_overlap_score, 6),
        }


def compute_portfolio_overlap(
    rows: Sequence[Dict[str, Any]],
    *,
    portfolio_key: str = "portfolio_id",
    cluster_key: str = "cluster_id",
) -> List[PortfolioOverlapMetrics]:
    """Compute portfolio-level overlap metrics from request rows."""
    by_portfolio: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        pid = str(row.get(portfolio_key, ""))
        if pid:
            by_portfolio[pid].append(row)

    if not by_portfolio:
        if not rows:
            return []
        by_portfolio["_all"] = list(rows)

    results: List[PortfolioOverlapMetrics] = []
    for pid, portfolio_rows in by_portfolio.items():
        n = len(portfolio_rows)
        param_hashes = [str(r.get("parameter_hash", "")) for r in portfolio_rows]
        feature_hashes = [str(r.get("feature_hash", "")) for r in portfolio_rows if r.get("feature_hash")]
        clusters = [str(r.get(cluster_key, "")) for r in portfolio_rows if r.get(cluster_key)]

        param_counts = Counter(param_hashes)
        unique_params = len(param_counts)
        dup_params = sum(1 for c in param_counts.values() if c > 1)

        feat_counts = Counter(feature_hashes)
        unique_feats = len(feat_counts) if feat_counts else n

        cluster_counts = Counter(clusters) if clusters else {}
        cluster_sizes = list(cluster_counts.values()) if cluster_counts else [1]

        param_overlap = 1.0 - (float(unique_params) / n) if n > 0 else 0.0
        feat_overlap = 1.0 - (float(unique_feats) / max(1, len(feature_hashes))) if feature_hashes else 0.0

        mean_cluster = (sum(cluster_sizes) / len(cluster_sizes)) if cluster_sizes else 1.0
        max_cluster = max(cluster_sizes) if cluster_sizes else 1
        num_clusters = len(cluster_counts) if cluster_counts else 1

        intra_sim = _estimate_intra_cluster_similarity(portfolio_rows, cluster_key)
        cross_dist = 1.0 - intra_sim if intra_sim < 1.0 else 0.0
        condensation = feat_overlap * 0.5 + param_overlap * 0.3 + (1.0 - float(num_clusters) / max(n, 1)) * 0.2

        results.append(PortfolioOverlapMetrics(
            portfolio_id=pid,
            position_count=n,
            unique_param_hashes=unique_params,
            duplicate_param_hashes=dup_params,
            param_overlap_ratio=param_overlap,
            unique_feature_hashes=unique_feats,
            feature_overlap_ratio=feat_overlap,
            cluster_count=num_clusters,
            mean_cluster_size=mean_cluster,
            max_cluster_size=max_cluster,
            intra_cluster_similarity=intra_sim,
            cross_cluster_distinctness=cross_dist,
            condensation_potential=condensation,
        ))

    return results


def _estimate_intra_cluster_similarity(
    rows: Sequence[Dict[str, Any]],
    cluster_key: str,
) -> float:
    """Estimate average intra-cluster parameter similarity."""
    by_cluster: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        cid = str(r.get(cluster_key, ""))
        if cid:
            by_cluster[cid].append(r)

    if not by_cluster:
        return 0.0

    similarities: List[float] = []
    for cluster_rows in by_cluster.values():
        if len(cluster_rows) < 2:
            continue
        for i in range(min(len(cluster_rows) - 1, 10)):
            a = cluster_rows[i]
            b = cluster_rows[i + 1]
            sim = _param_similarity(a, b)
            similarities.append(sim)

    return (sum(similarities) / len(similarities)) if similarities else 0.0


def _param_similarity(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    """Normalized parameter similarity between two requests (0=different, 1=identical)."""
    diffs: List[float] = []
    for key in ["S0", "K", "sigma", "T"]:
        va = float(a.get(key, 0))
        vb = float(b.get(key, 0))
        base = max(abs(va), abs(vb), 1e-6)
        diffs.append(1.0 - min(abs(va - vb) / base, 1.0))
    return sum(diffs) / len(diffs) if diffs else 0.0


def compute_scenario_overlap(
    rows: Sequence[Dict[str, Any]],
    *,
    event_window_key: str = "event_window_id",
) -> List[ScenarioOverlapMetrics]:
    """Compute event-window-level scenario overlap."""
    by_window: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        wid = str(r.get(event_window_key, ""))
        if wid:
            by_window[wid].append(r)

    results: List[ScenarioOverlapMetrics] = []
    all_param_hashes: Set[str] = set()

    for wid, window_rows in by_window.items():
        param_hashes = {str(r.get("parameter_hash", "")) for r in window_rows}
        overlapping = len(param_hashes & all_param_hashes)
        all_param_hashes.update(param_hashes)

        total = len(window_rows)
        overlap_ratio = float(overlapping) / len(param_hashes) if param_hashes else 0.0

        portfolios = {str(r.get("portfolio_id", "")) for r in window_rows if r.get("portfolio_id")}
        portfolio_score = min(1.0, float(len(portfolios)) / max(total, 1) * 2)

        results.append(ScenarioOverlapMetrics(
            scenario_id=wid,
            total_requests=total,
            overlapping_requests=overlapping,
            overlap_ratio=overlap_ratio,
            event_window_overlap_score=overlap_ratio,
            portfolio_overlap_score=portfolio_score,
        ))

    return results
