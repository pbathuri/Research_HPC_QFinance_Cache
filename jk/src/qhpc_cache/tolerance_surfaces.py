"""Tolerance sweeps and safe-reuse surface generation.

Sweeps across multiple tolerance dimensions to map regions where
similarity-based reuse is safe vs unsafe, producing data for
heatmaps, sensitivity tables, and Pareto fronts.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass
class ToleranceSweepPoint:
    """One point in a tolerance sweep."""

    price_tolerance: float
    sigma_tolerance: float
    maturity_tolerance: float
    path_count_tolerance: float
    feature_distance_threshold: float
    accepted_count: int
    rejected_count: int
    mean_price_error: float
    max_price_error: float
    mean_latency_saved_ms: float
    total_latency_saved_ms: float
    false_acceptance_count: int
    safe_region_flag: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "price_tolerance": self.price_tolerance,
            "sigma_tolerance": self.sigma_tolerance,
            "maturity_tolerance": self.maturity_tolerance,
            "path_count_tolerance": self.path_count_tolerance,
            "feature_distance_threshold": self.feature_distance_threshold,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "mean_price_error": round(self.mean_price_error, 8),
            "max_price_error": round(self.max_price_error, 8),
            "mean_latency_saved_ms": round(self.mean_latency_saved_ms, 4),
            "total_latency_saved_ms": round(self.total_latency_saved_ms, 4),
            "false_acceptance_count": self.false_acceptance_count,
            "safe_region_flag": self.safe_region_flag,
        }


def _compute_param_distance(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, float]:
    """Compute normalized parameter distances between two requests."""
    base_s0 = max(abs(float(a.get("S0", 100))), 1e-6)
    base_sigma = max(abs(float(a.get("sigma", 0.2))), 1e-6)
    base_t = max(abs(float(a.get("T", 1.0))), 1e-6)
    base_paths = max(int(a.get("num_paths", 10000)), 1)

    return {
        "price_rel_diff": abs(float(a.get("S0", 0)) - float(b.get("S0", 0))) / base_s0,
        "sigma_rel_diff": abs(float(a.get("sigma", 0)) - float(b.get("sigma", 0))) / base_sigma,
        "maturity_rel_diff": abs(float(a.get("T", 0)) - float(b.get("T", 0))) / base_t,
        "path_count_rel_diff": abs(int(a.get("num_paths", 0)) - int(b.get("num_paths", 0))) / base_paths,
    }


def run_tolerance_sweep(
    request_pairs: Sequence[Tuple[Dict[str, Any], Dict[str, Any]]],
    *,
    price_tolerances: Optional[Sequence[float]] = None,
    sigma_tolerances: Optional[Sequence[float]] = None,
    maturity_tolerances: Optional[Sequence[float]] = None,
    path_tolerances: Optional[Sequence[float]] = None,
    max_acceptable_error: float = 0.05,
) -> List[ToleranceSweepPoint]:
    """Sweep tolerance thresholds across request pairs.

    Parameters
    ----------
    request_pairs : pairs of (source_request, candidate_reuse_request)
        with optional 'realized_price_error' field on the candidate
    """
    if price_tolerances is None:
        price_tolerances = [0.001, 0.005, 0.01, 0.02, 0.05, 0.10]
    if sigma_tolerances is None:
        sigma_tolerances = [0.005, 0.01, 0.02, 0.05, 0.10]
    if maturity_tolerances is None:
        maturity_tolerances = [0.005, 0.01, 0.02, 0.05, 0.10]
    if path_tolerances is None:
        path_tolerances = [0.0, 0.10, 0.25, 0.50, 1.0]

    sweep_points: List[ToleranceSweepPoint] = []

    for pt, st, mt, pct in itertools.product(
        price_tolerances, sigma_tolerances, maturity_tolerances, path_tolerances
    ):
        accepted = 0
        rejected = 0
        false_acceptances = 0
        errors: List[float] = []
        latencies: List[float] = []

        for source, candidate in request_pairs:
            dists = _compute_param_distance(source, candidate)
            within_tolerance = (
                dists["price_rel_diff"] <= pt
                and dists["sigma_rel_diff"] <= st
                and dists["maturity_rel_diff"] <= mt
                and dists["path_count_rel_diff"] <= pct
            )

            if within_tolerance:
                accepted += 1
                error = abs(float(candidate.get("realized_price_error", 0.0)))
                errors.append(error)
                latencies.append(float(candidate.get("latency_saved_ms", 0.0)))
                if error > max_acceptable_error:
                    false_acceptances += 1
            else:
                rejected += 1

        mean_err = (sum(errors) / len(errors)) if errors else 0.0
        max_err = max(errors) if errors else 0.0
        mean_lat = (sum(latencies) / len(latencies)) if latencies else 0.0
        total_lat = sum(latencies)
        safe = false_acceptances == 0 and accepted > 0

        sweep_points.append(ToleranceSweepPoint(
            price_tolerance=pt,
            sigma_tolerance=st,
            maturity_tolerance=mt,
            path_count_tolerance=pct,
            feature_distance_threshold=max(pt, st, mt),
            accepted_count=accepted,
            rejected_count=rejected,
            mean_price_error=mean_err,
            max_price_error=max_err,
            mean_latency_saved_ms=mean_lat,
            total_latency_saved_ms=total_lat,
            false_acceptance_count=false_acceptances,
            safe_region_flag=safe,
        ))

    return sweep_points


def build_pareto_front(
    sweep_points: Sequence[ToleranceSweepPoint],
) -> List[ToleranceSweepPoint]:
    """Extract Pareto-optimal points: maximize savings, minimize error."""
    points = sorted(sweep_points, key=lambda p: (-p.total_latency_saved_ms, p.max_price_error))
    front: List[ToleranceSweepPoint] = []
    best_error = float("inf")

    for p in points:
        if p.max_price_error < best_error:
            front.append(p)
            best_error = p.max_price_error

    return front


def generate_sensitivity_table(
    sweep_points: Sequence[ToleranceSweepPoint],
    *,
    vary_dimension: str = "price_tolerance",
) -> List[Dict[str, Any]]:
    """Group sweep results by one dimension for sensitivity analysis."""
    from collections import defaultdict
    groups: Dict[float, List[ToleranceSweepPoint]] = defaultdict(list)

    for p in sweep_points:
        key = getattr(p, vary_dimension, 0.0)
        groups[key].append(p)

    table: List[Dict[str, Any]] = []
    for threshold, pts in sorted(groups.items()):
        avg_accepted = sum(p.accepted_count for p in pts) / len(pts)
        avg_error = sum(p.mean_price_error for p in pts) / len(pts)
        avg_savings = sum(p.total_latency_saved_ms for p in pts) / len(pts)
        safe_fraction = sum(1 for p in pts if p.safe_region_flag) / len(pts)

        table.append({
            vary_dimension: threshold,
            "sample_count": len(pts),
            "avg_accepted": round(avg_accepted, 2),
            "avg_price_error": round(avg_error, 8),
            "avg_total_savings_ms": round(avg_savings, 4),
            "safe_fraction": round(safe_fraction, 4),
        })

    return table
