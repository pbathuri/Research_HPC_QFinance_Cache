"""Human-readable feature vectors for classical and circuit-aware cache policies."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from qhpc_cache.quantum_mapping import FinanceProblemDescriptor, QuantumCircuitRequest


def build_cache_decision_features(
    payoff_family: str,
    maturity_in_years: float,
    volatility: float,
    expected_depth: int,
    expected_qubits: int,
    predicted_reuse_count: int,
    estimated_compile_cost: float,
    portfolio_cluster_label: str,
    similarity_score: float,
    exact_match_exists: bool,
    num_paths: int,
) -> Dict[str, Any]:
    """Flattened dict usable by heuristic, logistic, and research notebooks."""
    maturity_bucket = "short" if maturity_in_years < 0.25 else (
        "medium" if maturity_in_years < 1.0 else "long"
    )
    volatility_bucket = "low" if volatility < 0.15 else (
        "mid" if volatility < 0.35 else "high"
    )
    return {
        "payoff_family": payoff_family,
        "maturity_bucket": maturity_bucket,
        "maturity_in_years": maturity_in_years,
        "volatility_bucket": volatility_bucket,
        "volatility": volatility,
        "expected_depth": expected_depth,
        "expected_qubits": expected_qubits,
        "predicted_reuse_count": predicted_reuse_count,
        "estimated_compile_cost": estimated_compile_cost,
        "portfolio_cluster_label": portfolio_cluster_label,
        "similarity_score": similarity_score,
        "exact_match_exists": exact_match_exists,
        "num_paths": num_paths,
    }


def build_portfolio_aware_cache_features(
    base_features: Dict[str, Any],
    portfolio_cluster_label: str,
    cross_position_reuse_hint: str,
) -> Dict[str, Any]:
    """Augment base features with portfolio context for future cluster reuse."""
    enriched = dict(base_features)
    enriched["portfolio_cluster_label"] = portfolio_cluster_label
    enriched["cross_position_reuse_hint"] = cross_position_reuse_hint
    return enriched


def explain_cache_features(features: Dict[str, Any]) -> str:
    """Readable multi-line explanation for debugging policy decisions."""
    preferred_order: List[str] = [
        "payoff_family",
        "maturity_bucket",
        "volatility_bucket",
        "num_paths",
        "expected_depth",
        "expected_qubits",
        "similarity_score",
        "exact_match_exists",
        "predicted_reuse_count",
        "estimated_compile_cost",
        "portfolio_cluster_label",
        "cross_position_reuse_hint",
    ]
    lines: List[str] = []
    for key in preferred_order:
        if key in features:
            lines.append(f"{key}: {features[key]}")
    for key, value in sorted(features.items()):
        if key in preferred_order:
            continue
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def features_from_quantum_handles(
    finance_problem: FinanceProblemDescriptor,
    circuit_request: Optional[QuantumCircuitRequest] = None,
    similarity_score: float = 0.0,
    exact_match_exists: bool = False,
    predicted_reuse_count: int = 0,
    estimated_compile_cost: float = 1.0,
) -> Dict[str, Any]:
    """Helper bridging quantum_mapping objects to cache policy features."""
    depth = circuit_request.expected_depth if circuit_request else 0
    qubits = circuit_request.expected_qubit_count if circuit_request else 0
    return build_cache_decision_features(
        payoff_family=finance_problem.payoff_type,
        maturity_in_years=finance_problem.maturity_in_years,
        volatility=finance_problem.volatility,
        expected_depth=depth,
        expected_qubits=qubits,
        predicted_reuse_count=predicted_reuse_count,
        estimated_compile_cost=estimated_compile_cost,
        portfolio_cluster_label=finance_problem.portfolio_context_label,
        similarity_score=similarity_score,
        exact_match_exists=exact_match_exists,
        num_paths=finance_problem.number_of_samples,
    )
