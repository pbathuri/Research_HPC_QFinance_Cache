"""Ground-truth cacheability labeling and structured failure taxonomy.

Assigns principled labels to each workload request indicating whether it was
reusable in principle, separating:
- low hit rate due to unique workloads
- low hit rate due to weak cache logic
- low hit rate due to inadequate feature representation

Also provides a canonical failure taxonomy used across all modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence


class CacheabilityLabel(str, Enum):
    EXACT_REUSABLE = "exact_reusable"
    SIMILARITY_REUSABLE_SAFE = "similarity_reusable_safe"
    SIMILARITY_REUSABLE_UNSAFE = "similarity_reusable_unsafe"
    NON_REUSABLE_MODEL_CHANGE = "non_reusable_model_change"
    NON_REUSABLE_MARKET_STATE_CHANGE = "non_reusable_market_state_change"
    NON_REUSABLE_POLICY_FORBIDDEN = "non_reusable_policy_forbidden"
    NON_REUSABLE_FEATURE_INSUFFICIENT = "non_reusable_feature_insufficient"
    RECOMPUTE_REQUIRED = "recompute_required"
    UNIQUE_FIRST_ACCESS = "unique_first_access"
    UNDETERMINED = "undetermined"


class FailureReason(str, Enum):
    ENGINE_UNAVAILABLE = "engine_unavailable"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    FEATURE_REPRESENTATION_INSUFFICIENT = "feature_representation_insufficient"
    POLICY_TOO_STRICT = "policy_too_strict"
    POLICY_TOO_LOOSE = "policy_too_loose"
    UNIQUE_WORKLOAD = "unique_workload"
    UNSAFE_SIMILARITY = "unsafe_similarity"
    DATA_SOURCE_MISSING = "data_source_missing"
    PROXY_MEASUREMENT_ONLY = "proxy_measurement_only"
    CLUSTER_ENV_MISMATCH = "cluster_env_mismatch"
    OUTPUT_NOT_GENERATED = "output_not_generated"
    PARALLELISM_NOT_EXERCISED = "parallelism_not_exercised"
    NONE = "none"


class EpistemicStatus(str, Enum):
    OBSERVED = "observed"
    DERIVED = "derived"
    PROXY = "proxy"
    SIMULATED = "simulated"
    SKIPPED = "skipped"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"


class PolicyTier(str, Enum):
    NO_CACHE = "no_cache"
    EXACT_ONLY = "exact_only"
    EXACT_PLUS_HEURISTIC = "exact_plus_simple_heuristic"
    EXACT_PLUS_SIMILARITY = "exact_plus_similarity"
    EXACT_SIMILARITY_GUARDRAILS = "exact_similarity_guardrails"
    EXACT_SIMILARITY_REGIME_AWARE = "exact_similarity_regime_aware"


@dataclass
class CacheabilityAssignment:
    """Ground-truth cacheability label for one request."""

    request_id: str
    workload_family: str
    ground_truth_label: CacheabilityLabel
    observed_cache_hit: bool
    observed_similarity_hit: bool
    has_exact_repeat_group: bool
    has_similarity_group: bool
    prior_exact_seen: bool
    prior_similarity_seen: bool
    parameter_hash_repeated: bool
    feature_hash_repeated: bool
    failure_reason: FailureReason
    epistemic_status: EpistemicStatus
    label_reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "workload_family": self.workload_family,
            "ground_truth_cacheability_label": self.ground_truth_label.value,
            "observed_cache_hit": self.observed_cache_hit,
            "observed_similarity_hit": self.observed_similarity_hit,
            "has_exact_repeat_group": self.has_exact_repeat_group,
            "has_similarity_group": self.has_similarity_group,
            "prior_exact_seen": self.prior_exact_seen,
            "prior_similarity_seen": self.prior_similarity_seen,
            "parameter_hash_repeated": self.parameter_hash_repeated,
            "feature_hash_repeated": self.feature_hash_repeated,
            "failure_reason": self.failure_reason.value,
            "epistemic_status": self.epistemic_status.value,
            "label_reasoning": self.label_reasoning,
        }


def assign_cacheability_labels(
    result_rows: Sequence[Dict[str, Any]],
) -> List[CacheabilityAssignment]:
    """Assign ground-truth cacheability labels from observed request stream.

    Uses structural metadata (repeat groups, similarity groups, parameter hashes)
    to determine whether each request was reusable *in principle*, independent
    of whether the cache actually produced a hit.
    """
    seen_param_hashes: Dict[str, int] = {}
    seen_feature_hashes: Dict[str, int] = {}
    seen_exact_groups: Dict[str, int] = {}
    seen_sim_groups: Dict[str, int] = {}
    assignments: List[CacheabilityAssignment] = []

    for row in result_rows:
        request_id = str(row.get("request_id", ""))
        family = str(row.get("workload_family", ""))
        param_hash = str(row.get("parameter_hash", ""))
        feat_hash = str(row.get("feature_hash", ""))
        exact_group = str(row.get("exact_repeat_group_id", ""))
        sim_group = str(row.get("similarity_group_id", ""))
        hit = bool(row.get("cache_hit", False))
        sim_hit = bool(row.get("similarity_hit", False))

        param_repeated = param_hash in seen_param_hashes
        feat_repeated = feat_hash in seen_feature_hashes if feat_hash else False
        prior_exact = exact_group in seen_exact_groups if exact_group else False
        prior_sim = sim_group in seen_sim_groups if sim_group else False

        label, reasoning, failure = _classify_cacheability(
            param_repeated=param_repeated,
            feat_repeated=feat_repeated,
            prior_exact=prior_exact,
            prior_sim=prior_sim,
            has_exact_group=bool(exact_group),
            has_sim_group=bool(sim_group),
            observed_hit=hit,
            observed_sim_hit=sim_hit,
            family=family,
        )

        assignments.append(CacheabilityAssignment(
            request_id=request_id,
            workload_family=family,
            ground_truth_label=label,
            observed_cache_hit=hit,
            observed_similarity_hit=sim_hit,
            has_exact_repeat_group=bool(exact_group),
            has_similarity_group=bool(sim_group),
            prior_exact_seen=prior_exact,
            prior_similarity_seen=prior_sim,
            parameter_hash_repeated=param_repeated,
            feature_hash_repeated=feat_repeated,
            failure_reason=failure,
            epistemic_status=EpistemicStatus.DERIVED,
            label_reasoning=reasoning,
        ))

        if param_hash:
            seen_param_hashes[param_hash] = seen_param_hashes.get(param_hash, 0) + 1
        if feat_hash:
            seen_feature_hashes[feat_hash] = seen_feature_hashes.get(feat_hash, 0) + 1
        if exact_group:
            seen_exact_groups[exact_group] = seen_exact_groups.get(exact_group, 0) + 1
        if sim_group:
            seen_sim_groups[sim_group] = seen_sim_groups.get(sim_group, 0) + 1

    return assignments


def _classify_cacheability(
    *,
    param_repeated: bool,
    feat_repeated: bool,
    prior_exact: bool,
    prior_sim: bool,
    has_exact_group: bool,
    has_sim_group: bool,
    observed_hit: bool,
    observed_sim_hit: bool,
    family: str,
) -> tuple:
    """Return (label, reasoning, failure_reason)."""
    if observed_hit and param_repeated:
        return (
            CacheabilityLabel.EXACT_REUSABLE,
            "Parameter hash repeated and cache hit observed; exact reuse valid.",
            FailureReason.NONE,
        )

    if param_repeated and not observed_hit:
        return (
            CacheabilityLabel.EXACT_REUSABLE,
            "Parameter hash repeated but cache missed; reusable in principle, cache logic gap.",
            FailureReason.FEATURE_REPRESENTATION_INSUFFICIENT,
        )

    if prior_exact and has_exact_group:
        return (
            CacheabilityLabel.EXACT_REUSABLE,
            "Exact repeat group member with prior group access; structurally reusable.",
            FailureReason.NONE if observed_hit else FailureReason.FEATURE_REPRESENTATION_INSUFFICIENT,
        )

    if prior_sim and has_sim_group and feat_repeated:
        if observed_sim_hit:
            return (
                CacheabilityLabel.SIMILARITY_REUSABLE_SAFE,
                "Similarity group member with matching feature hash; safe similarity reuse.",
                FailureReason.NONE,
            )
        return (
            CacheabilityLabel.SIMILARITY_REUSABLE_SAFE,
            "Similarity group + feature match but no similarity hit observed; potentially under-exploited.",
            FailureReason.POLICY_TOO_STRICT,
        )

    if prior_sim and has_sim_group and not feat_repeated:
        return (
            CacheabilityLabel.SIMILARITY_REUSABLE_UNSAFE,
            "Similarity group member but feature hash differs; reuse would require tolerance validation.",
            FailureReason.NONE if not observed_sim_hit else FailureReason.POLICY_TOO_LOOSE,
        )

    if not param_repeated and not prior_exact and not prior_sim:
        return (
            CacheabilityLabel.UNIQUE_FIRST_ACCESS,
            "First access with no structural reuse indicators; genuinely unique workload item.",
            FailureReason.UNIQUE_WORKLOAD,
        )

    if family == "stress_churn_pricing":
        return (
            CacheabilityLabel.RECOMPUTE_REQUIRED,
            "Stress/churn family with high parameter dispersion; recompute expected.",
            FailureReason.UNIQUE_WORKLOAD,
        )

    return (
        CacheabilityLabel.UNDETERMINED,
        "Insufficient structural metadata to assign ground-truth label.",
        FailureReason.FEATURE_REPRESENTATION_INSUFFICIENT,
    )


def summarize_cacheability_labels(
    assignments: Sequence[CacheabilityAssignment],
) -> Dict[str, Any]:
    """Aggregate cacheability label statistics."""
    total = len(assignments)
    if total == 0:
        return {"total": 0, "label_distribution": {}, "failure_distribution": {}}

    from collections import Counter
    label_counts = Counter(a.ground_truth_label.value for a in assignments)
    failure_counts = Counter(
        a.failure_reason.value for a in assignments if a.failure_reason != FailureReason.NONE
    )
    hit_given_reusable = sum(
        1 for a in assignments
        if a.ground_truth_label in (CacheabilityLabel.EXACT_REUSABLE, CacheabilityLabel.SIMILARITY_REUSABLE_SAFE)
        and a.observed_cache_hit
    )
    reusable_total = sum(
        1 for a in assignments
        if a.ground_truth_label in (CacheabilityLabel.EXACT_REUSABLE, CacheabilityLabel.SIMILARITY_REUSABLE_SAFE)
    )

    return {
        "total": total,
        "label_distribution": dict(label_counts.most_common()),
        "failure_distribution": dict(failure_counts.most_common()),
        "reusable_count": reusable_total,
        "hit_given_reusable": hit_given_reusable,
        "cache_recall_on_reusable": float(hit_given_reusable) / reusable_total if reusable_total > 0 else 0.0,
        "unique_first_access_fraction": float(label_counts.get("unique_first_access", 0)) / total,
    }
