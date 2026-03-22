"""Transparent, weighted similarity for finance problems and circuit requests.

Scores are intentionally **interpretable**: every component is named, bounded,
and returned with a human-readable explanation list.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from qhpc_cache.quantum_mapping import FinanceProblemDescriptor, QuantumCircuitRequest


@dataclass
class SimilarityBreakdown:
    """Component scores in [0,1] and notes."""

    component_scores: Dict[str, float]
    notes: List[str]


def _bucket_maturity(maturity_in_years: float) -> str:
    if maturity_in_years < 0.25:
        return "short"
    if maturity_in_years < 1.0:
        return "medium"
    return "long"


def _bucket_volatility(volatility: float) -> str:
    if volatility < 0.15:
        return "low"
    if volatility < 0.35:
        return "mid"
    return "high"


def _bucket_strike_ratio(spot: float, strike: float) -> str:
    if spot <= 0.0:
        return "unknown"
    ratio = strike / spot
    if ratio < 0.95:
        return "itm_call"
    if ratio > 1.05:
        return "otm_call"
    return "atm"


def compute_basic_circuit_similarity(
    request_left: QuantumCircuitRequest,
    request_right: QuantumCircuitRequest,
) -> Tuple[float, SimilarityBreakdown]:
    """Similarity of two circuit requests using depth/qubit/family features."""
    notes: List[str] = []
    scores: Dict[str, float] = {}
    if request_left.circuit_family_name == request_right.circuit_family_name:
        scores["circuit_family_match"] = 1.0
        notes.append("Same circuit_family_name.")
    else:
        scores["circuit_family_match"] = 0.0
        notes.append("Different circuit_family_name.")

    depth_left = float(request_left.expected_depth)
    depth_right = float(request_right.expected_depth)
    depth_diff = abs(depth_left - depth_right)
    depth_scale = max(depth_left, depth_right, 1.0)
    depth_score = max(0.0, 1.0 - depth_diff / depth_scale)
    scores["depth_similarity"] = depth_score
    notes.append(f"Depth similarity {depth_score:.3f} (abs diff {depth_diff:.1f}).")

    q_left = float(request_left.expected_qubit_count)
    q_right = float(request_right.expected_qubit_count)
    q_diff = abs(q_left - q_right)
    q_scale = max(q_left, q_right, 1.0)
    q_score = max(0.0, 1.0 - q_diff / q_scale)
    scores["qubit_similarity"] = q_score
    notes.append(f"Qubit similarity {q_score:.3f} (abs diff {q_diff:.1f}).")

    weighted = (
        0.35 * scores["circuit_family_match"]
        + 0.35 * scores["depth_similarity"]
        + 0.30 * scores["qubit_similarity"]
    )
    return weighted, SimilarityBreakdown(component_scores=scores, notes=notes)


def compute_finance_problem_similarity(
    problem_left: FinanceProblemDescriptor,
    problem_right: FinanceProblemDescriptor,
    reference_spot_for_strike_bucket: float,
) -> Tuple[float, SimilarityBreakdown]:
    """Weighted match on payoff, model, buckets, and portfolio label."""
    notes: List[str] = []
    scores: Dict[str, float] = {}

    scores["payoff_match"] = (
        1.0 if problem_left.payoff_type == problem_right.payoff_type else 0.0
    )
    scores["model_match"] = (
        1.0
        if problem_left.stochastic_model_name == problem_right.stochastic_model_name
        else 0.0
    )
    scores["portfolio_label_match"] = (
        1.0
        if problem_left.portfolio_context_label == problem_right.portfolio_context_label
        else 0.3
    )

    left_mat = _bucket_maturity(problem_left.maturity_in_years)
    right_mat = _bucket_maturity(problem_right.maturity_in_years)
    scores["maturity_bucket_match"] = 1.0 if left_mat == right_mat else 0.4
    notes.append(f"Maturity buckets: {left_mat} vs {right_mat}.")

    left_vol = _bucket_volatility(problem_left.volatility)
    right_vol = _bucket_volatility(problem_right.volatility)
    scores["volatility_bucket_match"] = 1.0 if left_vol == right_vol else 0.4
    notes.append(f"Volatility buckets: {left_vol} vs {right_vol}.")

    left_strike = _bucket_strike_ratio(
        reference_spot_for_strike_bucket, problem_left.strike_price
    )
    right_strike = _bucket_strike_ratio(
        reference_spot_for_strike_bucket, problem_right.strike_price
    )
    scores["strike_bucket_match"] = 1.0 if left_strike == right_strike else 0.4
    notes.append(f"Strike buckets: {left_strike} vs {right_strike}.")

    weighted = (
        0.20 * scores["payoff_match"]
        + 0.15 * scores["model_match"]
        + 0.15 * scores["portfolio_label_match"]
        + 0.20 * scores["maturity_bucket_match"]
        + 0.15 * scores["volatility_bucket_match"]
        + 0.15 * scores["strike_bucket_match"]
    )
    return weighted, SimilarityBreakdown(component_scores=scores, notes=notes)


def compute_reuse_priority_score(
    finance_similarity: float,
    circuit_similarity: float,
    expected_reuse_value: float,
    expected_accuracy_risk: float,
) -> float:
    """Higher is better: prioritize similarity and reuse value, penalize risk."""
    risk_penalty = max(0.0, min(expected_accuracy_risk, 1.0))
    value_boost = max(0.0, min(expected_reuse_value, 1.0))
    return (
        0.45 * finance_similarity
        + 0.35 * circuit_similarity
        + 0.15 * value_boost
        - 0.10 * risk_penalty
    )


def explain_similarity_score(
    finance_breakdown: SimilarityBreakdown,
    circuit_breakdown: SimilarityBreakdown,
    reuse_priority: float,
) -> str:
    """Plain-language summary for lab notebooks."""
    lines: List[str] = []
    lines.append(f"Reuse priority score: {reuse_priority:.4f}")
    lines.append("Finance components:")
    for name, value in finance_breakdown.component_scores.items():
        lines.append(f"  - {name}: {value:.3f}")
    for note in finance_breakdown.notes:
        lines.append(f"  * {note}")
    lines.append("Circuit components:")
    for name, value in circuit_breakdown.component_scores.items():
        lines.append(f"  - {name}: {value:.3f}")
    for note in circuit_breakdown.notes:
        lines.append(f"  * {note}")
    return "\n".join(lines)
