"""Batch experiment helpers — return structured dicts (no printing).

These helpers prioritize measurable research outputs (timing/cache/error) and
support both lightweight and compute-heavy local Mac runs.
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict
from pathlib import Path
from random import Random
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from qhpc_cache.cache_policy import (
    AIAssistedCachePolicy,
    BaseCachePolicy,
    HeuristicCachePolicy,
)
from qhpc_cache.cache_store import SimpleCacheStore
from qhpc_cache.experiment_configs import (
    CacheExperimentConfig,
    MonteCarloExperimentConfig,
    PortfolioExperimentConfig,
)
from qhpc_cache.portfolio import (
    OptionPosition,
    PortfolioPricingRequest,
    compute_portfolio_profit_and_loss,
    price_portfolio_positions,
    summarize_portfolio_risk,
)
from qhpc_cache.pricing import MonteCarloPricer
from qhpc_cache.quantum_workflow import QuantumWorkflowBundle, run_quantum_mapping_workflow

EXECUTED_REAL = "executed_real"
EXECUTED_DEGRADED = "executed_degraded"
SKIPPED_MISSING_DEPENDENCY = "skipped_missing_dependency"
SKIPPED_NOT_IMPLEMENTED = "skipped_not_implemented"
PLACEHOLDER_ONLY = "placeholder_only"
FAILED_RUNTIME = "failed_runtime"
SKIPPED_BY_TIER_SELECTION = "skipped_by_tier_selection"

EVIDENCE_STATUS_FIELDS = [
    "execution_status",
    "evidence_valid",
    "excluded_from_summary",
    "exclusion_reason",
]

SCALE_LABELS = {"smoke", "standard", "heavy"}

EXPERIMENT_SCALE_PROFILES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "smoke": {
        "repeated_pricing": {"num_trials": 4, "num_paths": 2_000, "progress_every": 1},
        "canonical_exact_match": {"num_trials": 4, "num_paths": 3_000, "progress_every": 1},
        "policy_comparison": {"num_requests": 25, "progress_every": 5},
        "similarity_replay": {"num_requests": 20, "num_paths": 3_000, "progress_every": 5},
    },
    "standard": {
        "repeated_pricing": {"num_trials": 16, "num_paths": 8_000, "progress_every": 4},
        "canonical_exact_match": {"num_trials": 24, "num_paths": 12_000, "progress_every": 6},
        "policy_comparison": {"num_requests": 200, "progress_every": 25},
        "similarity_replay": {"num_requests": 120, "num_paths": 12_000, "progress_every": 20},
    },
    "heavy": {
        "repeated_pricing": {"num_trials": 96, "num_paths": 40_000, "progress_every": 8},
        "canonical_exact_match": {"num_trials": 180, "num_paths": 50_000, "progress_every": 15},
        "policy_comparison": {"num_requests": 5_000, "progress_every": 250},
        "similarity_replay": {"num_requests": 900, "num_paths": 35_000, "progress_every": 50},
    },
}

PLACEHOLDER_BOUNDARY_EXCLUSIONS = [
    {
        "module": "qhpc_cache.placeholders",
        "status": PLACEHOLDER_ONLY,
        "excluded_from_summary": True,
        "reason": "excluded because placeholder_only",
    },
    {
        "module": "qhpc_cache.fourier_placeholder",
        "status": PLACEHOLDER_ONLY,
        "excluded_from_summary": True,
        "reason": "excluded because placeholder_only",
    },
    {
        "module": "qhpc_cache.backends.mpi_placeholder",
        "status": PLACEHOLDER_ONLY,
        "excluded_from_summary": True,
        "reason": "excluded because placeholder_only",
    },
]

EXPERIMENT_LADDER: List[Dict[str, Any]] = [
    {
        "experiment_id": "canonical_exact_match_cache_experiment",
        "canonical_owner_module": "src/qhpc_cache/experiment_runner.py",
        "canonical_owner_function": "run_canonical_exact_match_cache_experiment",
        "tier": 1,
        "priority_order": 1,
        "research_justification": (
            "Directly tests repeated exact-request reuse, cache hit/miss behavior, "
            "and timing speedups for the core cache/reuse question."
        ),
        "required": True,
    },
    {
        "experiment_id": "seeded_repeated_monte_carlo_family_experiment",
        "canonical_owner_module": "src/qhpc_cache/experiment_runner.py",
        "canonical_owner_function": "run_seeded_repeated_monte_carlo_family_experiment",
        "tier": 1,
        "priority_order": 2,
        "research_justification": (
            "Validates reproducible repeated Monte Carlo families under fixed seeds "
            "to confirm stable workload signatures and reuse potential."
        ),
        "required": True,
    },
    {
        "experiment_id": "cache_policy_comparison_experiment",
        "canonical_owner_module": "src/qhpc_cache/experiment_runner.py",
        "canonical_owner_function": "run_cache_policy_comparison_experiment",
        "tier": 1,
        "priority_order": 3,
        "research_justification": (
            "Measures policy-gated reuse acceptance and miss-after-approval behavior "
            "needed before guided caching claims."
        ),
        "required": True,
    },
    {
        "experiment_id": "similarity_cache_replay_experiment",
        "canonical_owner_module": "src/qhpc_cache/experiment_runner.py",
        "canonical_owner_function": "run_similarity_cache_replay_experiment",
        "tier": 2,
        "priority_order": 1,
        "research_justification": (
            "Tests near-match reuse candidates, similarity hit rates, and quality "
            "error boundaries relative to no-cache baseline."
        ),
        "required": True,
    },
    {
        "experiment_id": "payoff_comparison_experiment",
        "canonical_owner_module": "src/qhpc_cache/experiment_runner.py",
        "canonical_owner_function": "run_payoff_comparison_experiment",
        "tier": 3,
        "priority_order": 1,
        "research_justification": (
            "Generalizes across payoff families; useful extension once core "
            "reuse/timing baselines are stable."
        ),
        "required": False,
    },
    {
        "experiment_id": "quantum_mapping_comparison_experiment",
        "canonical_owner_module": "src/qhpc_cache/experiment_runner.py",
        "canonical_owner_function": "run_quantum_mapping_comparison_experiment",
        "tier": 4,
        "priority_order": 1,
        "research_justification": (
            "Speculative/future-oriented mapping context; not primary evidence for "
            "current local cache/reuse thesis."
        ),
        "required": False,
    },
]


def _mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / float(len(values)))


def _validate_scale_label(scale_label: str) -> str:
    label = str(scale_label).strip().lower()
    if label not in SCALE_LABELS:
        raise ValueError(
            f"Invalid scale_label {scale_label!r}. Expected one of {sorted(SCALE_LABELS)}."
        )
    return label


def _normalize_tiers_to_run(tiers_to_run: Optional[List[int]]) -> List[int]:
    if tiers_to_run is None:
        return [1, 2]
    normalized = sorted({int(x) for x in tiers_to_run})
    valid = {1, 2, 3, 4}
    if not set(normalized).issubset(valid):
        raise ValueError(
            f"Invalid tiers_to_run {tiers_to_run!r}. Allowed tiers are [1, 2, 3, 4]."
        )
    return normalized


def get_experiment_ladder() -> List[Dict[str, Any]]:
    """Return ordered ladder for research-priority execution planning."""
    ordered = sorted(
        EXPERIMENT_LADDER,
        key=lambda row: (int(row["tier"]), int(row["priority_order"])),
    )
    return [dict(row) for row in ordered]


def _scale_value(scale_label: str, family: str, key: str) -> Any:
    label = _validate_scale_label(scale_label)
    return EXPERIMENT_SCALE_PROFILES[label][family][key]


def _append_jsonl(path: Optional[str | Path], payload: Dict[str, Any]) -> None:
    if path is None:
        return
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


def _write_json(path: Optional[str | Path], payload: Dict[str, Any]) -> None:
    if path is None:
        return
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _evidence_status(
    *,
    execution_status: str,
    evidence_valid: bool,
    exclusion_reason: str = "",
) -> Dict[str, Any]:
    excluded = (not bool(evidence_valid)) or bool(exclusion_reason)
    return {
        "execution_status": execution_status,
        "evidence_valid": bool(evidence_valid) and not bool(exclusion_reason),
        "excluded_from_summary": bool(excluded),
        "exclusion_reason": str(exclusion_reason),
    }


def _split_valid_excluded(
    rows: List[Dict[str, Any]],
    label_key: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    valid = [r for r in rows if bool(r.get("evidence_valid", False))]
    excluded: List[Dict[str, Any]] = []
    for row in rows:
        if bool(row.get("evidence_valid", False)):
            continue
        excluded.append(
            {
                "label": row.get(label_key),
                "execution_status": row.get("execution_status", ""),
                "exclusion_reason": row.get("exclusion_reason", "excluded_from_summary"),
            }
        )
    return valid, excluded


def _safe_quantile(sorted_values: List[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    q_clamped = max(0.0, min(1.0, float(q)))
    idx = int(round(q_clamped * float(len(sorted_values) - 1)))
    return float(sorted_values[idx])


def _distribution_summary(values: List[float]) -> Dict[str, Any]:
    cleaned = [float(v) for v in values if isinstance(v, (int, float))]
    if not cleaned:
        return {
            "count": 0,
            "min": 0.0,
            "mean": 0.0,
            "max": 0.0,
            "p10": 0.0,
            "p50": 0.0,
            "p90": 0.0,
            "is_constant": True,
        }
    sorted_values = sorted(cleaned)
    mean_value = float(sum(sorted_values) / float(len(sorted_values)))
    return {
        "count": int(len(sorted_values)),
        "min": float(sorted_values[0]),
        "mean": mean_value,
        "max": float(sorted_values[-1]),
        "p10": _safe_quantile(sorted_values, 0.10),
        "p50": _safe_quantile(sorted_values, 0.50),
        "p90": _safe_quantile(sorted_values, 0.90),
        "is_constant": bool(abs(sorted_values[-1] - sorted_values[0]) <= 1e-12),
    }


def _request_key_profile(requests: List[Dict[str, Any]]) -> Dict[str, Any]:
    keys = [
        json.dumps(_build_similarity_features_for_request(request), sort_keys=True)
        for request in requests
    ]
    total_count = len(keys)
    unique_count = len(set(keys))
    repeated_count = max(0, total_count - unique_count)
    return {
        "request_count": int(total_count),
        "unique_request_keys": int(unique_count),
        "repeated_request_keys": int(repeated_count),
    }


def _make_forensic_case(
    *,
    branch_name: str,
    experiment_name: str,
    scale_label: str,
    config: Dict[str, Any],
    trigger: str,
    exclusion_reason: str,
    cache_stats: Optional[Dict[str, Any]] = None,
    top_repeated_keys: Optional[List[Dict[str, Any]]] = None,
    similarity_distribution: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "branch_name": branch_name,
        "experiment_name": experiment_name,
        "scale_label": scale_label,
        "trigger": trigger,
        "exclusion_reason": exclusion_reason,
        "config": config,
        "cache_stats": cache_stats or {},
        "top_repeated_keys": top_repeated_keys or [],
        "similarity_distribution": similarity_distribution or {},
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def _cache_stats_for_return(cache_store: Optional[SimpleCacheStore]) -> Dict[str, Any]:
    if cache_store is None:
        return {
            "hits": 0,
            "misses": 0,
            "entries": 0,
            "put_count": 0,
            "overwrite_count": 0,
            "lookup_count": 0,
            "unique_lookup_keys": 0,
            "repeated_lookup_keys": 0,
            "hit_rate": 0.0,
            "miss_rate": 0.0,
        }
    stats = cache_store.stats()
    return {
        "hits": int(stats.get("hits", 0)),
        "misses": int(stats.get("misses", 0)),
        "entries": int(stats.get("entries", 0)),
        "put_count": int(stats.get("put_count", 0)),
        "overwrite_count": int(stats.get("overwrite_count", 0)),
        "lookup_count": int(stats.get("lookup_count", 0)),
        "unique_lookup_keys": int(stats.get("unique_lookup_keys", 0)),
        "repeated_lookup_keys": int(stats.get("repeated_lookup_keys", 0)),
        "hit_rate": float(stats.get("hit_rate", 0.0)),
        "miss_rate": float(stats.get("miss_rate", 0.0)),
    }


def _build_similarity_features_for_request(request: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "payoff_type": str(request.get("payoff_type", "european_call")),
        "S0": float(request["S0"]),
        "K": float(request["K"]),
        "r": float(request["r"]),
        "sigma": float(request["sigma"]),
        "T": float(request["T"]),
        "num_paths": int(request["num_paths"]),
        "simulation_mode": str(request.get("simulation_mode", "terminal")),
    }


def _pair_similarity_score(left: Dict[str, Any], right: Dict[str, Any]) -> float:
    if str(left.get("payoff_type")) != str(right.get("payoff_type")):
        return 0.0
    if str(left.get("simulation_mode")) != str(right.get("simulation_mode")):
        return 0.0
    left_spot = float(left.get("S0", 0.0))
    right_spot = float(right.get("S0", 0.0))
    left_k = float(left.get("K", 0.0))
    right_k = float(right.get("K", 0.0))
    left_sigma = float(left.get("sigma", 0.0))
    right_sigma = float(right.get("sigma", 0.0))
    left_t = float(left.get("T", 0.0))
    right_t = float(right.get("T", 0.0))
    left_r = float(left.get("r", 0.0))
    right_r = float(right.get("r", 0.0))
    left_paths = float(left.get("num_paths", 0))
    right_paths = float(right.get("num_paths", 0))

    left_moneyness = left_k / left_spot if left_spot > 0.0 else 1.0
    right_moneyness = right_k / right_spot if right_spot > 0.0 else 1.0
    moneyness_diff = abs(left_moneyness - right_moneyness)
    sigma_scale = max(abs(left_sigma), abs(right_sigma), 1e-8)
    sigma_diff = abs(left_sigma - right_sigma) / sigma_scale
    maturity_scale = max(abs(left_t), abs(right_t), 1e-8)
    maturity_diff = abs(left_t - right_t) / maturity_scale
    rate_diff = abs(left_r - right_r)
    path_scale = max(left_paths, right_paths, 1.0)
    path_diff = abs(left_paths - right_paths) / path_scale

    # Weighted normalized distance in [0, +inf), converted to score in [0,1].
    distance = (
        0.35 * moneyness_diff
        + 0.25 * sigma_diff
        + 0.20 * maturity_diff
        + 0.10 * rate_diff
        + 0.10 * path_diff
    )
    return max(0.0, min(1.0, 1.0 - distance))


def _build_repeated_similarity_workload(
    *,
    num_requests: int,
    pricing_kwargs: Dict[str, Any],
    random_seed: int,
) -> List[Dict[str, Any]]:
    rng = Random(int(random_seed))
    base = dict(pricing_kwargs)
    requests: List[Dict[str, Any]] = []
    for index in range(int(num_requests)):
        mode = index % 5
        req = dict(base)
        req["random_seed"] = int(random_seed) + index
        if mode == 0:
            req["workload_family"] = "exact_repeat_anchor"
        elif mode == 1:
            req["workload_family"] = "near_match_strike_sigma"
            req["K"] = float(base["K"]) * (1.0 + rng.uniform(-0.0125, 0.0125))
            req["sigma"] = float(base["sigma"]) * (1.0 + rng.uniform(-0.06, 0.06))
        elif mode == 2:
            req["workload_family"] = "near_match_maturity_rate"
            req["T"] = max(0.05, float(base["T"]) * (1.0 + rng.uniform(-0.1, 0.1)))
            req["r"] = float(base["r"]) + rng.uniform(-0.0075, 0.0075)
        elif mode == 3:
            req["workload_family"] = "exact_repeat_secondary_anchor"
            req["K"] = float(base["K"]) * 1.03
            req["sigma"] = float(base["sigma"]) * 1.05
            req["T"] = float(base["T"]) * 0.9
            req["random_seed"] = int(random_seed) + 1000 + (index % 7)
        else:
            req["workload_family"] = "far_match_control"
            req["K"] = float(base["K"]) * (1.0 + rng.uniform(-0.2, 0.2))
            req["sigma"] = float(base["sigma"]) * (1.0 + rng.uniform(-0.25, 0.25))
            req["T"] = max(0.05, float(base["T"]) * (1.0 + rng.uniform(-0.3, 0.3)))
        requests.append(req)
    return requests


def _price_monte_carlo_request(request: Dict[str, Any]) -> Tuple[float, float, float]:
    pricer_kwargs = {
        "S0": request["S0"],
        "K": request["K"],
        "r": request["r"],
        "sigma": request["sigma"],
        "T": request["T"],
        "num_paths": request["num_paths"],
        "payoff_type": request.get("payoff_type", "european_call"),
        "simulation_mode": request.get("simulation_mode", "terminal"),
        "num_time_steps": request.get("num_time_steps", 12),
        "use_antithetic_variates": request.get("use_antithetic_variates", False),
        "use_black_scholes_control_variate": request.get(
            "use_black_scholes_control_variate", False
        ),
        "compare_analytic_black_scholes": request.get(
            "compare_analytic_black_scholes", False
        ),
        "random_seed": request.get("random_seed"),
        "confidence_level": request.get("confidence_level", 0.95),
        "digital_payout_amount": request.get("digital_payout_amount", 1.0),
    }
    pricer = MonteCarloPricer(**pricer_kwargs)
    start = time.perf_counter()
    result = pricer.price_option()
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    runtime_ms = (
        float(result.total_runtime_ms)
        if float(getattr(result, "total_runtime_ms", 0.0)) > 0.0
        else float(elapsed_ms)
    )
    return (
        float(result.estimated_price),
        float(result.payoff_variance),
        float(runtime_ms),
    )


def run_repeated_pricing_experiment(
    pricer_factory: Callable[[], MonteCarloPricer],
    num_trials: int,
    *,
    scale_label: str = "standard",
    progress_every_trials: Optional[int] = None,
    progress_jsonl_path: Optional[str | Path] = None,
    checkpoint_json_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Run ``price_option`` repeatedly; return structured summary metrics.

    Designed for long local runs:
    - supports scale labels (`smoke`/`standard`/`heavy`)
    - writes periodic progress events when requested
    - writes checkpoint snapshots when requested
    """
    scale_label = _validate_scale_label(scale_label)
    if progress_every_trials is None:
        progress_every = int(_scale_value(scale_label, "repeated_pricing", "progress_every"))
    else:
        progress_every = max(1, int(progress_every_trials))
    pricer = pricer_factory()
    price_sum = 0.0
    variance_sum = 0.0
    runtime_sum = 0.0
    completed_trials = 0
    for trial_index in range(int(num_trials)):
        trial_start = time.perf_counter()
        result = pricer.price_option()
        price_sum += float(result.estimated_price)
        variance_sum += float(result.payoff_variance)
        runtime_ms = (
            result.total_runtime_ms
            if float(getattr(result, "total_runtime_ms", 0.0)) > 0.0
            else (time.perf_counter() - trial_start) * 1000.0
        )
        runtime_sum += float(runtime_ms)
        completed_trials += 1
        if (
            completed_trials % progress_every == 0
            or completed_trials == int(num_trials)
        ):
            stats = _cache_stats_for_return(pricer.cache_store)
            payload = {
                "event": "repeated_pricing_progress",
                "scale_label": scale_label,
                "completed_trials": int(completed_trials),
                "target_trials": int(num_trials),
                "running_average_price": float(price_sum / float(completed_trials)),
                "running_average_variance": float(variance_sum / float(completed_trials)),
                "running_average_runtime_per_trial_ms": float(
                    runtime_sum / float(completed_trials)
                ),
                "cache_hits": int(stats["hits"]),
                "cache_misses": int(stats["misses"]),
                "cache_entries": int(stats["entries"]),
            }
            _append_jsonl(progress_jsonl_path, payload)
            _write_json(
                checkpoint_json_path,
                {
                    "event": "repeated_pricing_checkpoint",
                    "scale_label": scale_label,
                    "completed_trials": int(completed_trials),
                    "target_trials": int(num_trials),
                    "running": payload,
                },
            )
    average_price = float(price_sum / float(max(1, completed_trials)))
    average_variance = float(variance_sum / float(max(1, completed_trials)))
    cache_stats = _cache_stats_for_return(pricer.cache_store)
    total_runtime = float(runtime_sum)
    average_runtime = float(runtime_sum / float(max(1, completed_trials)))
    forensics: List[Dict[str, Any]] = []
    if (
        pricer.cache_store is not None
        and int(completed_trials) > 1
        and int(cache_stats["hits"]) == 0
    ):
        forensics.append(
            _make_forensic_case(
                branch_name="repeated_pricing",
                experiment_name="repeated_pricing_experiment",
                scale_label=scale_label,
                config={
                    "num_trials": int(num_trials),
                    "completed_trials": int(completed_trials),
                },
                trigger="zero_cache_hits",
                exclusion_reason="diagnostic_only",
                cache_stats=cache_stats,
                top_repeated_keys=(
                    pricer.cache_store.top_repeated_keys()
                    if hasattr(pricer.cache_store, "top_repeated_keys")
                    else []
                ),
            )
        )
    return {
        "num_trials": num_trials,
        "completed_trials": int(completed_trials),
        "scale_label": scale_label,
        "average_price": average_price,
        "average_variance": average_variance,
        "cache_hits": cache_stats["hits"],
        "cache_misses": cache_stats["misses"],
        "cache_entries": cache_stats["entries"],
        "hit_rate": cache_stats["hit_rate"],
        "miss_rate": cache_stats["miss_rate"],
        "total_runtime_ms": total_runtime,
        "average_runtime_per_trial_ms": average_runtime,
        "put_count": cache_stats["put_count"],
        "overwrite_count": cache_stats["overwrite_count"],
        "lookup_count": cache_stats["lookup_count"],
        "unique_lookup_keys": cache_stats["unique_lookup_keys"],
        "repeated_lookup_keys": cache_stats["repeated_lookup_keys"],
        "forensics": forensics,
        "forensic_case_count": int(len(forensics)),
        **_evidence_status(
            execution_status=EXECUTED_REAL,
            evidence_valid=True,
        ),
    }


def run_seeded_repeated_monte_carlo_family_experiment(
    *,
    scale_label: str = "standard",
    random_seed: int = 123,
    output_csv_path: Optional[str | Path] = None,
    progress_jsonl_path: Optional[str | Path] = None,
    checkpoint_json_path: Optional[str | Path] = None,
    resume_from_checkpoint: bool = False,
) -> Dict[str, Any]:
    """Run reproducible repeated Monte Carlo families for reuse signature evidence."""
    scale_label = _validate_scale_label(scale_label)
    num_trials = int(_scale_value(scale_label, "repeated_pricing", "num_trials"))
    num_paths = int(_scale_value(scale_label, "repeated_pricing", "num_paths"))
    progress_every = int(_scale_value(scale_label, "repeated_pricing", "progress_every"))
    family_rows: List[Dict[str, Any]] = []
    forensic_cases: List[Dict[str, Any]] = []
    completed_families: set[str] = set()
    if resume_from_checkpoint and checkpoint_json_path is not None:
        cp = Path(checkpoint_json_path)
        if cp.exists():
            previous = json.loads(cp.read_text(encoding="utf-8"))
            family_rows = list(previous.get("per_family", []))
            completed_families = {str(row.get("family_label", "")) for row in family_rows}
    family_specs = [
        {"family_label": "atm_call", "payoff_type": "european_call", "K": 100.0},
        {"family_label": "otm_call", "payoff_type": "european_call", "K": 110.0},
        {"family_label": "itm_put", "payoff_type": "european_put", "K": 110.0},
    ]
    for idx, spec in enumerate(family_specs):
        family_label = str(spec["family_label"])
        if family_label in completed_families:
            _append_jsonl(
                progress_jsonl_path,
                {
                    "event": "seeded_family_resume_skip",
                    "scale_label": scale_label,
                    "family_label": family_label,
                    "reason": "already_completed_in_checkpoint",
                },
            )
            continue
        family_seed = int(random_seed) + idx * 100
        store = SimpleCacheStore()

        def _factory() -> MonteCarloPricer:
            return MonteCarloPricer(
                S0=100.0,
                K=float(spec["K"]),
                r=0.05,
                sigma=0.2,
                T=1.0,
                num_paths=num_paths,
                payoff_type=str(spec["payoff_type"]),
                simulation_mode="terminal",
                random_seed=family_seed,
                cache_store=store,
            )

        summary = run_repeated_pricing_experiment(
            _factory,
            num_trials=num_trials,
            scale_label=scale_label,
            progress_every_trials=progress_every,
            progress_jsonl_path=progress_jsonl_path,
        )
        summary["family_label"] = family_label
        summary["family_seed"] = family_seed
        summary["cache_mode"] = "exact_match_cache"
        family_forensics: List[Dict[str, Any]] = []
        family_stats = store.stats()
        request_key_profile = {
            "request_count": int(num_trials),
            "unique_request_keys": 1,
            "repeated_request_keys": max(0, int(num_trials) - 1),
        }
        if int(summary.get("cache_hits", 0)) == 0:
            family_forensics.append(
                _make_forensic_case(
                    branch_name=family_label,
                    experiment_name="seeded_repeated_monte_carlo_family_experiment",
                    scale_label=scale_label,
                    config={
                        "family_seed": int(family_seed),
                        "num_trials": int(num_trials),
                        "num_paths": int(num_paths),
                        "payoff_type": str(spec["payoff_type"]),
                        "K": float(spec["K"]),
                    },
                    trigger="zero_cache_hits",
                    exclusion_reason="diagnostic_only",
                    cache_stats=family_stats,
                    top_repeated_keys=store.top_repeated_keys(),
                    extra={"request_key_profile": request_key_profile},
                )
            )
        if float(summary.get("miss_rate", 0.0)) >= 1.0:
            family_forensics.append(
                _make_forensic_case(
                    branch_name=family_label,
                    experiment_name="seeded_repeated_monte_carlo_family_experiment",
                    scale_label=scale_label,
                    config={
                        "family_seed": int(family_seed),
                        "num_trials": int(num_trials),
                        "num_paths": int(num_paths),
                        "payoff_type": str(spec["payoff_type"]),
                        "K": float(spec["K"]),
                    },
                    trigger="all_misses",
                    exclusion_reason="diagnostic_only",
                    cache_stats=family_stats,
                    top_repeated_keys=store.top_repeated_keys(),
                    extra={"request_key_profile": request_key_profile},
                )
            )
        summary["top_repeated_keys"] = store.top_repeated_keys()
        summary["forensics"] = family_forensics
        summary["forensic_case_count"] = int(len(family_forensics))
        forensic_cases.extend(family_forensics)
        family_rows.append(summary)
        completed_families.add(family_label)
        if output_csv_path is not None:
            out_csv = Path(output_csv_path)
            out_csv.parent.mkdir(parents=True, exist_ok=True)
            fieldnames = [
                "family_label",
                "family_seed",
                "cache_mode",
                "scale_label",
                "num_trials",
                "completed_trials",
                "average_price",
                "average_variance",
                "cache_hits",
                "cache_misses",
                "cache_entries",
                "hit_rate",
                "miss_rate",
                "total_runtime_ms",
                "average_runtime_per_trial_ms",
                "forensic_case_count",
                "execution_status",
                "evidence_valid",
                "excluded_from_summary",
                "exclusion_reason",
            ]
            with out_csv.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in family_rows:
                    writer.writerow({k: row.get(k) for k in fieldnames})
        if checkpoint_json_path is not None:
            _write_json(
                checkpoint_json_path,
                {
                    "experiment_name": "seeded_repeated_monte_carlo_family_experiment",
                    "scale_label": scale_label,
                    "num_trials": num_trials,
                    "num_paths": num_paths,
                    "completed_families": sorted(completed_families),
                    "per_family": family_rows,
                },
            )
    valid_rows, excluded_rows = _split_valid_excluded(family_rows, label_key="family_label")
    return {
        "experiment_name": "seeded_repeated_monte_carlo_family_experiment",
        "scale_label": scale_label,
        "num_trials": int(num_trials),
        "num_paths": int(num_paths),
        "per_family": family_rows,
        "valid_evidence_families": [row["family_label"] for row in valid_rows],
        "excluded_families": excluded_rows,
        "forensic_cases": forensic_cases,
        "summary_computed_from_valid_evidence_only": True,
        "placeholder_module_exclusions": list(PLACEHOLDER_BOUNDARY_EXCLUSIONS),
    }


def run_payoff_comparison_experiment(
    payoff_names: Sequence[str],
    initial_spot_price: float = 100.0,
    strike_price: float = 100.0,
    risk_free_rate: float = 0.05,
    volatility: float = 0.2,
    time_to_maturity: float = 1.0,
    number_of_paths: int = 4000,
    random_seed: Optional[int] = 101,
) -> Dict[str, Any]:
    """Price several payoff types with shared market parameters; return structured rows."""
    per_payoff: List[Dict[str, Any]] = []
    for index in range(len(payoff_names)):
        name = payoff_names[index]
        simulation_mode = "path" if name in ("asian_call", "asian_put") else "terminal"
        seed = (
            None if random_seed is None else int(random_seed) + index
        )
        pricer = MonteCarloPricer(
            S0=initial_spot_price,
            K=strike_price,
            r=risk_free_rate,
            sigma=volatility,
            T=time_to_maturity,
            num_paths=number_of_paths,
            payoff_type=name,
            simulation_mode=simulation_mode,
            num_time_steps=12,
            compare_analytic_black_scholes=name
            in ("european_call", "european_put"),
            random_seed=seed,
        )
        result = pricer.price_option()
        per_payoff.append(
            {
                "payoff_name": result.payoff_name,
                "estimated_price": result.estimated_price,
                "standard_error": result.standard_error,
                "analytic_reference_price": result.analytic_reference_price,
                "used_path_simulation": result.used_path_simulation,
            }
        )
    return {
        "per_payoff": per_payoff,
        "number_of_paths": number_of_paths,
        "initial_spot_price": initial_spot_price,
        "strike_price": strike_price,
    }


def run_monte_carlo_study(
    config: MonteCarloExperimentConfig,
) -> Dict[str, Any]:
    """Repeated independent batches with controlled seed offsets."""
    estimates: List[float] = []
    analytic_refs: List[Optional[float]] = []
    for rep_index in range(config.num_replications):
        seed = (
            None if config.random_seed is None else config.random_seed + rep_index
        )
        pricer = MonteCarloPricer(
            S0=config.initial_spot_price,
            K=config.strike_price,
            r=config.risk_free_rate,
            sigma=config.volatility,
            T=config.maturity_in_years,
            num_paths=config.num_paths,
            payoff_type=config.payoff_type,
            simulation_mode=config.simulation_mode,
            use_antithetic_variates=config.use_antithetic_variates,
            use_black_scholes_control_variate=config.use_black_scholes_control_variate,
            compare_analytic_black_scholes=config.compare_analytic_black_scholes,
            random_seed=seed,
        )
        result = pricer.price_option()
        estimates.append(result.estimated_price)
        analytic_refs.append(result.analytic_reference_price)
    mean_estimate = sum(estimates) / float(len(estimates))
    return {
        "mean_estimate": mean_estimate,
        "replication_estimates": estimates,
        "analytic_reference_per_run": analytic_refs,
        "config": asdict(config),
    }


def run_portfolio_risk_experiment(
    config: PortfolioExperimentConfig,
    positions: List[OptionPosition],
    portfolio_name: str = "experiment_portfolio",
) -> Dict[str, Any]:
    """Price book and compute VaR/CVaR on analytic scenario P&L."""
    request = PortfolioPricingRequest(
        portfolio_name=portfolio_name,
        positions=positions,
        number_of_paths=config.num_paths_per_position,
        random_seed=config.random_seed,
        scenario_underlying_prices=list(config.scenario_spots),
        baseline_underlying_price=config.baseline_spot,
        risk_confidence_level=config.confidence_level,
    )
    pricing_result = price_portfolio_positions(request)
    pnl = compute_portfolio_profit_and_loss(request)
    risk = summarize_portfolio_risk(
        request, confidence_level=config.confidence_level
    )
    return {
        "portfolio_name": pricing_result.portfolio_name,
        "total_estimated_value": pricing_result.total_estimated_value,
        "value_at_risk": risk.value_at_risk,
        "conditional_value_at_risk": risk.conditional_value_at_risk,
        "pnl_samples": pnl,
        "config": asdict(config),
    }


def run_cache_policy_comparison_experiment(
    cache_config: CacheExperimentConfig,
    policies: Dict[str, BaseCachePolicy],
    *,
    scale_label: str = "standard",
    progress_every_requests: Optional[int] = None,
    progress_jsonl_path: Optional[str | Path] = None,
    checkpoint_json_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Simulate repeated policy-gated cache requests with single-lookup flow."""
    scale_label = _validate_scale_label(scale_label)
    if progress_every_requests is None:
        progress_every = int(_scale_value(scale_label, "policy_comparison", "progress_every"))
    else:
        progress_every = max(1, int(progress_every_requests))
    rows: List[Dict[str, Any]] = []
    forensic_cases: List[Dict[str, Any]] = []
    for policy_name, policy in policies.items():
        store = SimpleCacheStore()
        features = dict(cache_config.base_features)
        approved_count = 0
        rejected_count = 0
        target_requests = int(cache_config.num_requests)
        start = time.perf_counter()
        for request_index in range(target_requests):
            decision = bool(policy.decide(features))
            if decision:
                approved_count += 1
                hit, _ = store.try_get(
                    features,
                    policy_approved_reuse=True,
                    engine_name=policy_name,
                )
                if not hit:
                    store.put(features, {"mean": 1.0, "variance": 0.01}, engine_name=policy_name)
            else:
                rejected_count += 1
                store.try_get(
                    features,
                    policy_approved_reuse=False,
                    engine_name=policy_name,
                )
            done = request_index + 1
            if done % progress_every == 0 or done == target_requests:
                _append_jsonl(
                    progress_jsonl_path,
                    {
                        "event": "cache_policy_progress",
                        "scale_label": scale_label,
                        "policy_name": policy_name,
                        "completed_requests": int(done),
                        "target_requests": int(target_requests),
                        "approved_count": int(approved_count),
                        "rejected_count": int(rejected_count),
                        "stats": store.stats(),
                    },
                )
                _write_json(
                    checkpoint_json_path,
                    {
                        "event": "cache_policy_checkpoint",
                        "scale_label": scale_label,
                        "policy_name": policy_name,
                        "completed_requests": int(done),
                        "target_requests": int(target_requests),
                        "approved_count": int(approved_count),
                        "rejected_count": int(rejected_count),
                        "stats": store.stats(),
                    },
                )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        stats = store.stats()
        policy_diagnostics = (
            policy.diagnostics() if hasattr(policy, "diagnostics") else {}
        )
        warnings: List[str] = []
        if (
            isinstance(policy, AIAssistedCachePolicy)
            and int(policy_diagnostics.get("fallback_used_count", 0)) > 0
        ):
            warnings.append(
                "AI policy fallback path was used; inspect policy_diagnostics "
                "for fallback_no_model_count and fallback_inference_error_count."
            )
        execution_status = EXECUTED_REAL
        exclusion_reason = ""
        if isinstance(policy, AIAssistedCachePolicy) and (
            int(policy_diagnostics.get("fallback_no_model_count", 0)) > 0
            or int(policy_diagnostics.get("fallback_inference_error_count", 0)) > 0
        ):
            execution_status = EXECUTED_DEGRADED
            exclusion_reason = "excluded because degraded_fallback_path_used"
        branch_forensics: List[Dict[str, Any]] = []
        if int(stats.get("hits", 0)) == 0 and target_requests > 0:
            branch_forensics.append(
                _make_forensic_case(
                    branch_name=policy_name,
                    experiment_name="cache_policy_comparison_experiment",
                    scale_label=scale_label,
                    config={
                        "num_requests": int(target_requests),
                        "base_features": dict(features),
                    },
                    trigger="zero_cache_hits",
                    exclusion_reason=exclusion_reason or "diagnostic_only",
                    cache_stats=stats,
                    top_repeated_keys=store.top_repeated_keys(),
                    extra={
                        "policy_approved_count": int(approved_count),
                        "policy_rejected_count": int(rejected_count),
                        "policy_diagnostics": policy_diagnostics,
                    },
                )
            )
        if float(stats.get("miss_rate", 0.0)) >= 1.0 and target_requests > 0:
            branch_forensics.append(
                _make_forensic_case(
                    branch_name=policy_name,
                    experiment_name="cache_policy_comparison_experiment",
                    scale_label=scale_label,
                    config={
                        "num_requests": int(target_requests),
                        "base_features": dict(features),
                    },
                    trigger="all_misses",
                    exclusion_reason=exclusion_reason or "diagnostic_only",
                    cache_stats=stats,
                    top_repeated_keys=store.top_repeated_keys(),
                    extra={
                        "policy_approved_count": int(approved_count),
                        "policy_rejected_count": int(rejected_count),
                        "policy_diagnostics": policy_diagnostics,
                    },
                )
            )
        if int(approved_count) == 0 and target_requests > 0:
            branch_forensics.append(
                _make_forensic_case(
                    branch_name=policy_name,
                    experiment_name="cache_policy_comparison_experiment",
                    scale_label=scale_label,
                    config={
                        "num_requests": int(target_requests),
                        "base_features": dict(features),
                    },
                    trigger="policy_never_approved_reuse",
                    exclusion_reason=exclusion_reason or "diagnostic_only",
                    cache_stats=stats,
                    top_repeated_keys=store.top_repeated_keys(),
                    extra={
                        "policy_approved_count": int(approved_count),
                        "policy_rejected_count": int(rejected_count),
                        "policy_diagnostics": policy_diagnostics,
                    },
                )
            )
        if execution_status != EXECUTED_REAL:
            branch_forensics.append(
                _make_forensic_case(
                    branch_name=policy_name,
                    experiment_name="cache_policy_comparison_experiment",
                    scale_label=scale_label,
                    config={
                        "num_requests": int(target_requests),
                        "base_features": dict(features),
                    },
                    trigger="excluded_from_valid_evidence",
                    exclusion_reason=exclusion_reason or "excluded_from_summary",
                    cache_stats=stats,
                    top_repeated_keys=store.top_repeated_keys(),
                    extra={
                        "policy_approved_count": int(approved_count),
                        "policy_rejected_count": int(rejected_count),
                        "policy_diagnostics": policy_diagnostics,
                    },
                )
            )
        row = {
            "policy_name": policy_name,
            "cache_hits": int(stats["hits"]),
            "cache_misses": int(stats["misses"]),
            "cache_entries": int(stats["entries"]),
            "hit_rate": float(stats["hit_rate"]),
            "miss_rate": float(stats["miss_rate"]),
            "total_runtime_ms": float(elapsed_ms),
            "average_runtime_per_request_ms": float(
                elapsed_ms / max(1, int(cache_config.num_requests))
            ),
            "stats": stats,
            "policy_label": policy_name,
            "policy_approved_count": int(approved_count),
            "policy_rejected_count": int(rejected_count),
            "policy_diagnostics": policy_diagnostics,
            "warnings": warnings,
            "scale_label": scale_label,
            "top_repeated_keys": store.top_repeated_keys(),
            "forensics": branch_forensics,
            "forensic_case_count": int(len(branch_forensics)),
            **_evidence_status(
                execution_status=execution_status,
                evidence_valid=(execution_status == EXECUTED_REAL),
                exclusion_reason=exclusion_reason,
            ),
        }
        rows.append(row)
        forensic_cases.extend(branch_forensics)
    valid_rows, excluded_rows = _split_valid_excluded(rows, label_key="policy_name")
    per_policy = {str(row["policy_name"]): row for row in rows}
    return {
        "per_policy": per_policy,
        "config": asdict(cache_config),
        "scale_label": scale_label,
        "valid_evidence_policies": [row["policy_name"] for row in valid_rows],
        "excluded_policies": excluded_rows,
        "forensic_cases": forensic_cases,
        "summary_computed_from_valid_evidence_only": True,
        "placeholder_module_exclusions": list(PLACEHOLDER_BOUNDARY_EXCLUSIONS),
    }


def run_canonical_exact_match_cache_experiment(
    *,
    num_trials: Optional[int] = None,
    pricing_kwargs: Optional[Dict[str, Any]] = None,
    random_seed: Optional[int] = 123,
    output_csv_path: Optional[str | Path] = None,
    scale_label: str = "standard",
    progress_every_trials: Optional[int] = None,
    progress_jsonl_path: Optional[str | Path] = None,
    checkpoint_json_path: Optional[str | Path] = None,
    resume_from_checkpoint: bool = False,
) -> Dict[str, Any]:
    """Run canonical exact-match cache baselines with structured summaries.

    Baselines:
    1) no cache
    2) exact cache with no policy gate
    3) heuristic policy + cache
    4) AI-assisted stub policy + cache (heuristic fallback by default)
    """
    scale_label = _validate_scale_label(scale_label)
    resolved_num_trials = (
        int(_scale_value(scale_label, "canonical_exact_match", "num_trials"))
        if num_trials is None
        else int(num_trials)
    )
    resolved_num_paths = int(_scale_value(scale_label, "canonical_exact_match", "num_paths"))
    resolved_progress_every = (
        int(_scale_value(scale_label, "canonical_exact_match", "progress_every"))
        if progress_every_trials is None
        else max(1, int(progress_every_trials))
    )
    base_kwargs = {
        "S0": 100.0,
        "K": 100.0,
        "r": 0.05,
        "sigma": 0.2,
        "T": 1.0,
        "num_paths": resolved_num_paths,
        "payoff_type": "european_call",
        "simulation_mode": "terminal",
        "random_seed": random_seed,
    }
    if pricing_kwargs:
        base_kwargs.update(dict(pricing_kwargs))

    rows: List[Dict[str, Any]] = []
    forensic_cases: List[Dict[str, Any]] = []
    completed_labels: set[str] = set()
    if resume_from_checkpoint and checkpoint_json_path is not None:
        cp = Path(checkpoint_json_path)
        if cp.exists():
            previous = json.loads(cp.read_text(encoding="utf-8"))
            rows = list(previous.get("per_condition", []))
            completed_labels = {str(r.get("experiment_label", "")) for r in rows}

    def _run(label: str, policy: Optional[BaseCachePolicy], use_cache: bool) -> None:
        if label in completed_labels:
            _append_jsonl(
                progress_jsonl_path,
                {
                    "event": "canonical_exact_match_resume_skip",
                    "scale_label": scale_label,
                    "condition_label": label,
                    "reason": "already_completed_in_checkpoint",
                },
            )
            return
        store = SimpleCacheStore() if use_cache else None

        def factory() -> MonteCarloPricer:
            return MonteCarloPricer(
                **base_kwargs,
                cache_policy=policy,
                cache_store=store,
            )

        summary = run_repeated_pricing_experiment(
            factory,
            num_trials=resolved_num_trials,
            scale_label=scale_label,
            progress_every_trials=resolved_progress_every,
            progress_jsonl_path=progress_jsonl_path,
        )
        summary["experiment_label"] = label
        summary["condition_label"] = label
        summary["policy_label"] = (
            "none"
            if policy is None
            else policy.__class__.__name__
        )
        summary["cache_enabled"] = bool(use_cache)
        summary["scale_label"] = scale_label
        policy_diagnostics = (
            policy.diagnostics() if (policy is not None and hasattr(policy, "diagnostics")) else {}
        )
        warnings: List[str] = []
        execution_status = EXECUTED_REAL
        exclusion_reason = ""
        if isinstance(policy, AIAssistedCachePolicy) and (
            int(policy_diagnostics.get("fallback_no_model_count", 0)) > 0
            or int(policy_diagnostics.get("fallback_inference_error_count", 0)) > 0
        ):
            execution_status = EXECUTED_DEGRADED
            exclusion_reason = "excluded because degraded_fallback_path_used"
            warnings.append(
                "Condition used AI stub fallback path; excluded from valid-evidence headline metrics."
            )
        summary["policy_diagnostics"] = policy_diagnostics
        summary["warnings"] = warnings
        summary.update(
            _evidence_status(
                execution_status=execution_status,
                evidence_valid=(execution_status == EXECUTED_REAL),
                exclusion_reason=exclusion_reason,
            )
        )
        branch_forensics: List[Dict[str, Any]] = []
        cache_stats = (
            store.stats()
            if store is not None
            else {
                "hits": 0,
                "misses": 0,
                "entries": 0,
                "lookup_count": 0,
                "unique_lookup_keys": 0,
                "repeated_lookup_keys": 0,
                "hit_rate": 0.0,
                "miss_rate": 0.0,
            }
        )
        top_repeated = store.top_repeated_keys() if store is not None else []
        if int(summary.get("cache_hits", 0)) == 0 and bool(use_cache):
            branch_forensics.append(
                _make_forensic_case(
                    branch_name=label,
                    experiment_name="canonical_exact_match_cache_experiment",
                    scale_label=scale_label,
                    config={
                        "num_trials": int(resolved_num_trials),
                        "pricing_kwargs": dict(base_kwargs),
                        "cache_enabled": bool(use_cache),
                    },
                    trigger="zero_cache_hits",
                    exclusion_reason=exclusion_reason or "diagnostic_only",
                    cache_stats=cache_stats,
                    top_repeated_keys=top_repeated,
                    extra={"policy_label": summary["policy_label"]},
                )
            )
        if execution_status != EXECUTED_REAL:
            branch_forensics.append(
                _make_forensic_case(
                    branch_name=label,
                    experiment_name="canonical_exact_match_cache_experiment",
                    scale_label=scale_label,
                    config={
                        "num_trials": int(resolved_num_trials),
                        "pricing_kwargs": dict(base_kwargs),
                        "cache_enabled": bool(use_cache),
                    },
                    trigger="excluded_from_valid_evidence",
                    exclusion_reason=exclusion_reason or "excluded_from_summary",
                    cache_stats=cache_stats,
                    top_repeated_keys=top_repeated,
                    extra={
                        "policy_label": summary["policy_label"],
                        "policy_diagnostics": policy_diagnostics,
                    },
                )
            )
        summary["forensics"] = branch_forensics
        summary["forensic_case_count"] = int(len(branch_forensics))
        rows.append(summary)
        forensic_cases.extend(branch_forensics)
        completed_labels.add(label)
        _append_jsonl(
            progress_jsonl_path,
            {
                "event": "canonical_exact_match_condition_complete",
                "scale_label": scale_label,
                "condition_label": label,
                "completed_conditions": sorted(completed_labels),
                "num_trials": int(resolved_num_trials),
                "summary": {
                    "average_price": summary["average_price"],
                    "cache_hits": summary["cache_hits"],
                    "cache_misses": summary["cache_misses"],
                    "total_runtime_ms": summary["total_runtime_ms"],
                    "execution_status": summary["execution_status"],
                    "evidence_valid": summary["evidence_valid"],
                },
            },
        )
        if checkpoint_json_path is not None:
            _write_json(
                checkpoint_json_path,
                {
                    "experiment_name": "canonical_exact_match_cache_experiment",
                    "scale_label": scale_label,
                    "num_trials": int(resolved_num_trials),
                    "pricing_kwargs": base_kwargs,
                    "completed_conditions": sorted(completed_labels),
                    "per_condition": rows,
                },
            )
        if output_csv_path is not None:
            path = Path(output_csv_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            fieldnames = [
                "experiment_label",
                "condition_label",
                "policy_label",
                "cache_enabled",
                "scale_label",
                "num_trials",
                "completed_trials",
                "average_price",
                "average_variance",
                "cache_hits",
                "cache_misses",
                "cache_entries",
                "hit_rate",
                "miss_rate",
                "total_runtime_ms",
                "average_runtime_per_trial_ms",
                "put_count",
                "overwrite_count",
                "lookup_count",
                "forensic_case_count",
                "execution_status",
                "evidence_valid",
                "excluded_from_summary",
                "exclusion_reason",
            ]
            with path.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow({k: row.get(k) for k in fieldnames})

    _run("no_cache_baseline", policy=None, use_cache=False)
    _run("exact_cache_no_policy_gate", policy=None, use_cache=True)
    _run("heuristic_policy_plus_cache", policy=HeuristicCachePolicy(), use_cache=True)
    _run(
        "ai_assisted_stub_policy_plus_cache",
        policy=AIAssistedCachePolicy(model=None, fallback_mode="heuristic"),
        use_cache=True,
    )

    for row in rows:
        if "forensics" not in row or not isinstance(row.get("forensics"), list):
            row["forensics"] = []
        if "forensic_case_count" not in row:
            row["forensic_case_count"] = int(len(row["forensics"]))

    valid_rows, excluded_rows = _split_valid_excluded(rows, label_key="experiment_label")
    return {
        "experiment_name": "canonical_exact_match_cache_experiment",
        "scale_label": scale_label,
        "num_trials": int(resolved_num_trials),
        "pricing_kwargs": base_kwargs,
        "per_condition": rows,
        "valid_evidence_conditions": [row["experiment_label"] for row in valid_rows],
        "excluded_conditions": excluded_rows,
        "completed_conditions": sorted(completed_labels),
        "forensic_cases": forensic_cases,
        "summary_computed_from_valid_evidence_only": True,
        "placeholder_module_exclusions": list(PLACEHOLDER_BOUNDARY_EXCLUSIONS),
    }


def run_similarity_cache_replay_experiment(
    *,
    num_requests: Optional[int] = None,
    pricing_kwargs: Optional[Dict[str, Any]] = None,
    random_seed: int = 777,
    similarity_threshold: float = 0.92,
    fail_on_low_similarity_quality: bool = False,
    max_mean_abs_error: float = 0.75,
    output_csv_path: Optional[str | Path] = None,
    output_manifest_path: Optional[str | Path] = None,
    scale_label: str = "standard",
    progress_every_requests: Optional[int] = None,
    progress_jsonl_path: Optional[str | Path] = None,
    checkpoint_json_path: Optional[str | Path] = None,
    resume_from_checkpoint: bool = False,
) -> Dict[str, Any]:
    """Run no-cache vs exact-cache vs similarity-cache replay on repeated workloads.

    This is intentionally compute-heavy by default (for local evidence collection).
    Similarity reuse is explicit and measurable:
    - exact hits
    - similarity hits
    - misses requiring fresh pricing
    - approximation error vs no-cache baseline
    """
    scale_label = _validate_scale_label(scale_label)
    resolved_num_requests = (
        int(_scale_value(scale_label, "similarity_replay", "num_requests"))
        if num_requests is None
        else int(num_requests)
    )
    resolved_num_paths = int(_scale_value(scale_label, "similarity_replay", "num_paths"))
    resolved_progress_every = (
        int(_scale_value(scale_label, "similarity_replay", "progress_every"))
        if progress_every_requests is None
        else max(1, int(progress_every_requests))
    )
    if similarity_threshold <= 0.0 or similarity_threshold > 1.0:
        raise ValueError(
            "similarity_threshold must be in (0, 1], "
            f"got {similarity_threshold!r}."
        )
    if resolved_num_requests < 1:
        raise ValueError(f"num_requests must be >= 1, got {resolved_num_requests!r}.")
    base_kwargs = {
        "S0": 100.0,
        "K": 100.0,
        "r": 0.05,
        "sigma": 0.2,
        "T": 1.0,
        "num_paths": resolved_num_paths,
        "payoff_type": "european_call",
        "simulation_mode": "terminal",
    }
    if pricing_kwargs:
        base_kwargs.update(dict(pricing_kwargs))
    requests = _build_repeated_similarity_workload(
        num_requests=resolved_num_requests,
        pricing_kwargs=base_kwargs,
        random_seed=random_seed,
    )
    request_profile = _request_key_profile(requests)
    forensic_cases: List[Dict[str, Any]] = []

    checkpoint_state: Dict[str, Any] = {
        "completed_stages": [],
        "baseline_prices": [],
        "baseline_variances": [],
        "baseline_runtime_ms": [],
        "no_cache_result": None,
        "exact_result": None,
        "similarity_result": None,
    }
    if resume_from_checkpoint and checkpoint_json_path is not None:
        cp = Path(checkpoint_json_path)
        if cp.exists():
            checkpoint_state.update(json.loads(cp.read_text(encoding="utf-8")))

    baseline_prices: List[float] = list(checkpoint_state.get("baseline_prices", []))
    baseline_variances: List[float] = list(checkpoint_state.get("baseline_variances", []))
    baseline_runtime_ms: List[float] = list(checkpoint_state.get("baseline_runtime_ms", []))
    completed_stages = set(checkpoint_state.get("completed_stages", []))

    no_cache_result = checkpoint_state.get("no_cache_result")
    if "baseline" in completed_stages and not isinstance(no_cache_result, dict):
        completed_stages.discard("baseline")
    if "baseline" not in completed_stages:
        baseline_prices = []
        baseline_variances = []
        baseline_runtime_ms = []
        for idx, request in enumerate(requests):
            price, variance, runtime_ms = _price_monte_carlo_request(request)
            baseline_prices.append(price)
            baseline_variances.append(variance)
            baseline_runtime_ms.append(runtime_ms)
            done = idx + 1
            if done % resolved_progress_every == 0 or done == len(requests):
                _append_jsonl(
                    progress_jsonl_path,
                    {
                        "event": "similarity_replay_progress",
                        "scale_label": scale_label,
                        "stage": "baseline",
                        "completed_requests": int(done),
                        "target_requests": int(len(requests)),
                        "running_average_price": _mean(baseline_prices),
                        "running_average_variance": _mean(baseline_variances),
                    },
                )
        no_cache_result = {
            "strategy_label": "no_cache",
            "scale_label": scale_label,
            "average_price": _mean(baseline_prices),
            "average_variance": _mean(baseline_variances),
            "cache_hits": 0,
            "similarity_hits": 0,
            "cache_misses": int(len(requests)),
            "hit_rate": 0.0,
            "similarity_hit_rate": 0.0,
            "mean_abs_error_vs_no_cache": 0.0,
            "p95_abs_error_vs_no_cache": 0.0,
            "total_runtime_ms": float(sum(baseline_runtime_ms)),
            "average_runtime_per_request_ms": _mean(baseline_runtime_ms),
            **_evidence_status(
                execution_status=EXECUTED_REAL,
                evidence_valid=True,
            ),
        }
        no_cache_forensics: List[Dict[str, Any]] = []
        if int(request_profile["repeated_request_keys"]) == 0:
            no_cache_forensics.append(
                _make_forensic_case(
                    branch_name="no_cache",
                    experiment_name="similarity_cache_replay_experiment",
                    scale_label=scale_label,
                    config={
                        "num_requests": int(resolved_num_requests),
                        "pricing_kwargs": dict(base_kwargs),
                        "similarity_threshold": float(similarity_threshold),
                        "random_seed": int(random_seed),
                    },
                    trigger="insufficient_workload_richness_no_repeated_keys",
                    exclusion_reason="diagnostic_only",
                    cache_stats={"hits": 0, "misses": int(len(requests)), "entries": 0},
                    top_repeated_keys=[],
                    extra={"request_key_profile": request_profile},
                )
            )
        no_cache_result["forensics"] = no_cache_forensics
        forensic_cases.extend(no_cache_forensics)
        completed_stages.add("baseline")
        checkpoint_state.update(
            {
                "completed_stages": sorted(completed_stages),
                "baseline_prices": baseline_prices,
                "baseline_variances": baseline_variances,
                "baseline_runtime_ms": baseline_runtime_ms,
                "no_cache_result": no_cache_result,
            }
        )
        _write_json(checkpoint_json_path, checkpoint_state)

    exact_result = checkpoint_state.get("exact_result")
    if "exact" in completed_stages and not isinstance(exact_result, dict):
        completed_stages.discard("exact")
    if "exact" not in completed_stages:
        exact_store = SimpleCacheStore()
        exact_prices: List[float] = []
        exact_variances: List[float] = []
        exact_abs_errors: List[float] = []
        exact_runtime_ms: List[float] = []
        for idx, request in enumerate(requests):
            features = _build_similarity_features_for_request(request)
            start = time.perf_counter()
            hit, cached = exact_store.try_get(
                features,
                engine_name="exact_cache_replay",
                policy_approved_reuse=True,
            )
            if hit:
                price = float(cached["price"])
                variance = float(cached["variance"])
            else:
                price, variance, _runtime = _price_monte_carlo_request(request)
                exact_store.put(
                    features,
                    {"price": price, "variance": variance},
                    engine_name="exact_cache_replay",
                )
            exact_runtime_ms.append((time.perf_counter() - start) * 1000.0)
            exact_prices.append(price)
            exact_variances.append(variance)
            exact_abs_errors.append(abs(price - baseline_prices[idx]))
            done = idx + 1
            if done % resolved_progress_every == 0 or done == len(requests):
                stats = exact_store.stats()
                _append_jsonl(
                    progress_jsonl_path,
                    {
                        "event": "similarity_replay_progress",
                        "scale_label": scale_label,
                        "stage": "exact_cache",
                        "completed_requests": int(done),
                        "target_requests": int(len(requests)),
                        "cache_hits": int(stats["hits"]),
                        "cache_misses": int(stats["misses"]),
                        "running_mean_abs_error_vs_no_cache": _mean(exact_abs_errors),
                    },
                )
        exact_stats = exact_store.stats()
        exact_errors_sorted = sorted(exact_abs_errors)
        exact_p95_index = (
            int(0.95 * (len(exact_errors_sorted) - 1))
            if len(exact_errors_sorted) > 1
            else 0
        )
        exact_result = {
            "strategy_label": "exact_cache",
            "scale_label": scale_label,
            "average_price": _mean(exact_prices),
            "average_variance": _mean(exact_variances),
            "cache_hits": int(exact_stats["hits"]),
            "similarity_hits": 0,
            "cache_misses": int(exact_stats["misses"]),
            "hit_rate": float(exact_stats["hit_rate"]),
            "similarity_hit_rate": 0.0,
            "mean_abs_error_vs_no_cache": _mean(exact_abs_errors),
            "p95_abs_error_vs_no_cache": (
                float(exact_errors_sorted[exact_p95_index]) if exact_errors_sorted else 0.0
            ),
            "total_runtime_ms": float(sum(exact_runtime_ms)),
            "average_runtime_per_request_ms": _mean(exact_runtime_ms),
            "lookup_count": int(exact_stats.get("lookup_count", 0)),
            "put_count": int(exact_stats.get("put_count", 0)),
            "overwrite_count": int(exact_stats.get("overwrite_count", 0)),
            **_evidence_status(
                execution_status=EXECUTED_REAL,
                evidence_valid=True,
            ),
        }
        exact_result["top_repeated_keys"] = exact_store.top_repeated_keys()
        exact_forensics: List[Dict[str, Any]] = []
        if int(exact_stats.get("hits", 0)) == 0:
            exact_forensics.append(
                _make_forensic_case(
                    branch_name="exact_cache",
                    experiment_name="similarity_cache_replay_experiment",
                    scale_label=scale_label,
                    config={
                        "num_requests": int(resolved_num_requests),
                        "pricing_kwargs": dict(base_kwargs),
                        "similarity_threshold": float(similarity_threshold),
                        "random_seed": int(random_seed),
                    },
                    trigger="zero_cache_hits",
                    exclusion_reason="diagnostic_only",
                    cache_stats=exact_stats,
                    top_repeated_keys=exact_store.top_repeated_keys(),
                    extra={"request_key_profile": request_profile},
                )
            )
        if float(exact_stats.get("miss_rate", 0.0)) >= 1.0:
            exact_forensics.append(
                _make_forensic_case(
                    branch_name="exact_cache",
                    experiment_name="similarity_cache_replay_experiment",
                    scale_label=scale_label,
                    config={
                        "num_requests": int(resolved_num_requests),
                        "pricing_kwargs": dict(base_kwargs),
                        "similarity_threshold": float(similarity_threshold),
                        "random_seed": int(random_seed),
                    },
                    trigger="all_misses",
                    exclusion_reason="diagnostic_only",
                    cache_stats=exact_stats,
                    top_repeated_keys=exact_store.top_repeated_keys(),
                    extra={"request_key_profile": request_profile},
                )
            )
        if (
            float(exact_result.get("average_runtime_per_request_ms", 0.0))
            >= float(no_cache_result.get("average_runtime_per_request_ms", 0.0))
        ):
            exact_forensics.append(
                _make_forensic_case(
                    branch_name="exact_cache",
                    experiment_name="similarity_cache_replay_experiment",
                    scale_label=scale_label,
                    config={
                        "num_requests": int(resolved_num_requests),
                        "pricing_kwargs": dict(base_kwargs),
                        "similarity_threshold": float(similarity_threshold),
                        "random_seed": int(random_seed),
                    },
                    trigger="empty_timing_benefit_vs_no_cache",
                    exclusion_reason="diagnostic_only",
                    cache_stats=exact_stats,
                    top_repeated_keys=exact_store.top_repeated_keys(),
                    extra={
                        "exact_avg_runtime_ms": float(
                            exact_result.get("average_runtime_per_request_ms", 0.0)
                        ),
                        "no_cache_avg_runtime_ms": float(
                            no_cache_result.get("average_runtime_per_request_ms", 0.0)
                        ),
                    },
                )
            )
        exact_result["forensics"] = exact_forensics
        forensic_cases.extend(exact_forensics)
        completed_stages.add("exact")
        checkpoint_state.update(
            {
                "completed_stages": sorted(completed_stages),
                "exact_result": exact_result,
            }
        )
        _write_json(checkpoint_json_path, checkpoint_state)

    similarity_result = checkpoint_state.get("similarity_result")
    if "similarity" in completed_stages and not isinstance(similarity_result, dict):
        completed_stages.discard("similarity")
    if "similarity" not in completed_stages:
        similarity_store = SimpleCacheStore()
        similarity_library: List[Tuple[Dict[str, Any], Dict[str, float]]] = []
        similarity_prices: List[float] = []
        similarity_variances: List[float] = []
        similarity_abs_errors: List[float] = []
        similarity_runtime_ms: List[float] = []
        similarity_hit_count = 0
        similarity_candidate_scores: List[float] = []
        for idx, request in enumerate(requests):
            features = _build_similarity_features_for_request(request)
            start = time.perf_counter()
            exact_hit, cached = similarity_store.try_get(
                features,
                engine_name="similarity_cache_replay",
                policy_approved_reuse=True,
            )
            if exact_hit:
                price = float(cached["price"])
                variance = float(cached["variance"])
            else:
                best_score = -1.0
                best_value: Optional[Dict[str, float]] = None
                for ref_features, ref_value in similarity_library:
                    score = _pair_similarity_score(features, ref_features)
                    if score > best_score:
                        best_score = score
                        best_value = ref_value
                similarity_candidate_scores.append(
                    float(best_score if best_score >= 0.0 else 0.0)
                )
                if best_value is not None and best_score >= float(similarity_threshold):
                    similarity_hit_count += 1
                    price = float(best_value["price"])
                    variance = float(best_value["variance"])
                else:
                    price, variance, _runtime = _price_monte_carlo_request(request)
                    similarity_store.put(
                        features,
                        {"price": price, "variance": variance},
                        engine_name="similarity_cache_replay",
                    )
                    similarity_library.append(
                        (features, {"price": price, "variance": variance})
                    )
            similarity_runtime_ms.append((time.perf_counter() - start) * 1000.0)
            similarity_prices.append(price)
            similarity_variances.append(variance)
            similarity_abs_errors.append(abs(price - baseline_prices[idx]))
            done = idx + 1
            if done % resolved_progress_every == 0 or done == len(requests):
                stats = similarity_store.stats()
                _append_jsonl(
                    progress_jsonl_path,
                    {
                        "event": "similarity_replay_progress",
                        "scale_label": scale_label,
                        "stage": "similarity_cache",
                        "completed_requests": int(done),
                        "target_requests": int(len(requests)),
                        "cache_hits": int(stats["hits"]),
                        "cache_misses": int(stats["misses"]),
                        "similarity_hits": int(similarity_hit_count),
                        "running_mean_abs_error_vs_no_cache": _mean(similarity_abs_errors),
                    },
                )
        similarity_stats = similarity_store.stats()
        similarity_errors_sorted = sorted(similarity_abs_errors)
        similarity_p95_index = (
            int(0.95 * (len(similarity_errors_sorted) - 1))
            if len(similarity_errors_sorted) > 1
            else 0
        )
        similarity_result = {
            "strategy_label": "similarity_cache",
            "scale_label": scale_label,
            "average_price": _mean(similarity_prices),
            "average_variance": _mean(similarity_variances),
            "cache_hits": int(similarity_stats["hits"]),
            "similarity_hits": int(similarity_hit_count),
            "cache_misses": int(similarity_stats["misses"]),
            "hit_rate": float(similarity_stats["hit_rate"]),
            "similarity_hit_rate": (
                float(similarity_hit_count) / float(len(requests)) if requests else 0.0
            ),
            "mean_abs_error_vs_no_cache": _mean(similarity_abs_errors),
            "p95_abs_error_vs_no_cache": (
                float(similarity_errors_sorted[similarity_p95_index])
                if similarity_errors_sorted
                else 0.0
            ),
            "total_runtime_ms": float(sum(similarity_runtime_ms)),
            "average_runtime_per_request_ms": _mean(similarity_runtime_ms),
            "lookup_count": int(similarity_stats.get("lookup_count", 0)),
            "put_count": int(similarity_stats.get("put_count", 0)),
            "overwrite_count": int(similarity_stats.get("overwrite_count", 0)),
            "computed_exact_count": int(similarity_stats.get("put_count", 0)),
        }
        similarity_mae = float(similarity_result["mean_abs_error_vs_no_cache"])
        similarity_execution_status = EXECUTED_REAL
        similarity_exclusion_reason = ""
        warnings: List[str] = []
        if int(similarity_hit_count) == 0:
            similarity_execution_status = EXECUTED_DEGRADED
            similarity_exclusion_reason = (
                "excluded because degraded_to_exact_only_no_similarity_hits"
            )
            warnings.append(
                "Similarity branch produced zero similarity hits; treated as degraded and excluded."
            )
        if similarity_mae > float(max_mean_abs_error):
            msg = (
                "Similarity branch mean absolute error exceeded configured threshold: "
                f"{similarity_mae:.6f} > {float(max_mean_abs_error):.6f}"
            )
            if fail_on_low_similarity_quality:
                raise RuntimeError(
                    f"{msg}. This path fails loudly by design; inspect workload and threshold."
                )
            similarity_execution_status = EXECUTED_DEGRADED
            similarity_exclusion_reason = (
                "excluded because output_invalid_similarity_quality_threshold"
            )
            warnings.append(msg)
        similarity_result["warnings"] = warnings
        similarity_result.update(
            _evidence_status(
                execution_status=similarity_execution_status,
                evidence_valid=(similarity_execution_status == EXECUTED_REAL),
                exclusion_reason=similarity_exclusion_reason,
            )
        )
        similarity_result["top_repeated_keys"] = similarity_store.top_repeated_keys()
        similarity_distribution = _distribution_summary(similarity_candidate_scores)
        similarity_result["similarity_score_distribution"] = similarity_distribution
        similarity_forensics: List[Dict[str, Any]] = []
        if int(similarity_hit_count) == 0:
            similarity_forensics.append(
                _make_forensic_case(
                    branch_name="similarity_cache",
                    experiment_name="similarity_cache_replay_experiment",
                    scale_label=scale_label,
                    config={
                        "num_requests": int(resolved_num_requests),
                        "pricing_kwargs": dict(base_kwargs),
                        "similarity_threshold": float(similarity_threshold),
                        "random_seed": int(random_seed),
                    },
                    trigger="zero_similarity_hits",
                    exclusion_reason=similarity_exclusion_reason or "diagnostic_only",
                    cache_stats=similarity_stats,
                    top_repeated_keys=similarity_store.top_repeated_keys(),
                    similarity_distribution=similarity_distribution,
                    extra={"request_key_profile": request_profile},
                )
            )
        if int(similarity_stats.get("hits", 0)) == 0:
            similarity_forensics.append(
                _make_forensic_case(
                    branch_name="similarity_cache",
                    experiment_name="similarity_cache_replay_experiment",
                    scale_label=scale_label,
                    config={
                        "num_requests": int(resolved_num_requests),
                        "pricing_kwargs": dict(base_kwargs),
                        "similarity_threshold": float(similarity_threshold),
                        "random_seed": int(random_seed),
                    },
                    trigger="zero_cache_hits",
                    exclusion_reason=similarity_exclusion_reason or "diagnostic_only",
                    cache_stats=similarity_stats,
                    top_repeated_keys=similarity_store.top_repeated_keys(),
                    similarity_distribution=similarity_distribution,
                    extra={"request_key_profile": request_profile},
                )
            )
        if bool(similarity_distribution.get("is_constant", False)):
            similarity_forensics.append(
                _make_forensic_case(
                    branch_name="similarity_cache",
                    experiment_name="similarity_cache_replay_experiment",
                    scale_label=scale_label,
                    config={
                        "num_requests": int(resolved_num_requests),
                        "pricing_kwargs": dict(base_kwargs),
                        "similarity_threshold": float(similarity_threshold),
                        "random_seed": int(random_seed),
                    },
                    trigger="constant_similarity_score_distribution",
                    exclusion_reason=similarity_exclusion_reason or "diagnostic_only",
                    cache_stats=similarity_stats,
                    top_repeated_keys=similarity_store.top_repeated_keys(),
                    similarity_distribution=similarity_distribution,
                    extra={"request_key_profile": request_profile},
                )
            )
        if (
            float(similarity_result.get("average_runtime_per_request_ms", 0.0))
            >= float(no_cache_result.get("average_runtime_per_request_ms", 0.0))
        ):
            similarity_forensics.append(
                _make_forensic_case(
                    branch_name="similarity_cache",
                    experiment_name="similarity_cache_replay_experiment",
                    scale_label=scale_label,
                    config={
                        "num_requests": int(resolved_num_requests),
                        "pricing_kwargs": dict(base_kwargs),
                        "similarity_threshold": float(similarity_threshold),
                        "random_seed": int(random_seed),
                    },
                    trigger="empty_timing_benefit_vs_no_cache",
                    exclusion_reason=similarity_exclusion_reason or "diagnostic_only",
                    cache_stats=similarity_stats,
                    top_repeated_keys=similarity_store.top_repeated_keys(),
                    similarity_distribution=similarity_distribution,
                    extra={
                        "similarity_avg_runtime_ms": float(
                            similarity_result.get("average_runtime_per_request_ms", 0.0)
                        ),
                        "no_cache_avg_runtime_ms": float(
                            no_cache_result.get("average_runtime_per_request_ms", 0.0)
                        ),
                    },
                )
            )
        if similarity_execution_status != EXECUTED_REAL:
            similarity_forensics.append(
                _make_forensic_case(
                    branch_name="similarity_cache",
                    experiment_name="similarity_cache_replay_experiment",
                    scale_label=scale_label,
                    config={
                        "num_requests": int(resolved_num_requests),
                        "pricing_kwargs": dict(base_kwargs),
                        "similarity_threshold": float(similarity_threshold),
                        "random_seed": int(random_seed),
                    },
                    trigger="excluded_from_valid_evidence",
                    exclusion_reason=similarity_exclusion_reason or "excluded_from_summary",
                    cache_stats=similarity_stats,
                    top_repeated_keys=similarity_store.top_repeated_keys(),
                    similarity_distribution=similarity_distribution,
                    extra={
                        "mean_abs_error_vs_no_cache": float(
                            similarity_result.get("mean_abs_error_vs_no_cache", 0.0)
                        ),
                        "max_mean_abs_error_threshold": float(max_mean_abs_error),
                        "request_key_profile": request_profile,
                    },
                )
            )
        similarity_result["forensics"] = similarity_forensics
        forensic_cases.extend(similarity_forensics)
        completed_stages.add("similarity")
        checkpoint_state.update(
            {
                "completed_stages": sorted(completed_stages),
                "similarity_result": similarity_result,
            }
        )
        _write_json(checkpoint_json_path, checkpoint_state)

    rows = [no_cache_result, exact_result, similarity_result]
    for row in rows:
        if "forensics" not in row or not isinstance(row.get("forensics"), list):
            row["forensics"] = []
        row["forensic_case_count"] = int(len(row["forensics"]))
        if "top_repeated_keys" not in row:
            row["top_repeated_keys"] = []
        if (
            row.get("strategy_label") == "similarity_cache"
            and "similarity_score_distribution" not in row
        ):
            row["similarity_score_distribution"] = _distribution_summary([])
    valid_rows, excluded_rows = _split_valid_excluded(rows, label_key="strategy_label")
    if output_csv_path is not None:
        csv_path = Path(output_csv_path)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "strategy_label",
            "scale_label",
            "average_price",
            "average_variance",
            "cache_hits",
            "similarity_hits",
            "cache_misses",
            "hit_rate",
            "similarity_hit_rate",
            "mean_abs_error_vs_no_cache",
            "p95_abs_error_vs_no_cache",
            "total_runtime_ms",
            "average_runtime_per_request_ms",
            "lookup_count",
            "put_count",
            "overwrite_count",
            "computed_exact_count",
            "forensic_case_count",
            "execution_status",
            "evidence_valid",
            "excluded_from_summary",
            "exclusion_reason",
        ]
        with csv_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k) for k in fieldnames})

    global_warnings: List[str] = []
    for row in rows:
        for warning in row.get("warnings", []):
            global_warnings.append(f"{row['strategy_label']}: {warning}")
    manifest = {
        "experiment_name": "similarity_cache_replay_experiment",
        "scale_label": scale_label,
        "num_requests": int(resolved_num_requests),
        "similarity_threshold": float(similarity_threshold),
        "pricing_kwargs": base_kwargs,
        "request_key_profile": request_profile,
        "strategies": rows,
        "valid_evidence_strategies": [row["strategy_label"] for row in valid_rows],
        "excluded_strategies": excluded_rows,
        "forensic_cases": forensic_cases,
        "summary_computed_from_valid_evidence_only": True,
        "workload_family_counts": {
            "exact_repeat_anchor": sum(1 for r in requests if r.get("workload_family") == "exact_repeat_anchor"),
            "near_match_strike_sigma": sum(1 for r in requests if r.get("workload_family") == "near_match_strike_sigma"),
            "near_match_maturity_rate": sum(1 for r in requests if r.get("workload_family") == "near_match_maturity_rate"),
            "exact_repeat_secondary_anchor": sum(
                1 for r in requests if r.get("workload_family") == "exact_repeat_secondary_anchor"
            ),
            "far_match_control": sum(1 for r in requests if r.get("workload_family") == "far_match_control"),
        },
        "degraded_paths": excluded_rows,
        "warnings": global_warnings,
        "placeholder_module_exclusions": list(PLACEHOLDER_BOUNDARY_EXCLUSIONS),
        "resumability": {
            "checkpoint_json_path": str(checkpoint_json_path) if checkpoint_json_path is not None else "",
            "resume_from_checkpoint": bool(resume_from_checkpoint),
            "completed_stages": sorted(completed_stages),
            "stage_resume_supported": True,
            "intra_stage_resume_supported": False,
        },
    }
    if output_manifest_path is not None:
        manifest_path = Path(output_manifest_path)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return manifest


def run_local_research_sweep(
    *,
    output_dir: str | Path = "outputs/long_runs",
    scale_label: str = "standard",
    random_seed: int = 123,
    resume_from_checkpoint: bool = True,
    tiers_to_run: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Run canonical local sweep in ladder order (Tier 1 -> Tier 2 -> Tier 3 -> Tier 4)."""
    scale_label = _validate_scale_label(scale_label)
    selected_tiers = _normalize_tiers_to_run(tiers_to_run)
    ladder = get_experiment_ladder()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    suite_checkpoint = out / "local_research_sweep_checkpoint.json"
    progress_jsonl = out / "local_research_sweep_progress.jsonl"
    _append_jsonl(
        progress_jsonl,
        {
            "event": "ladder_start",
            "scale_label": scale_label,
            "tiers_selected": selected_tiers,
        },
    )
    outputs: Dict[str, Any] = {}
    tier_status_rows: List[Dict[str, Any]] = []

    def _record_row(
        ladder_row: Dict[str, Any],
        *,
        execution_status: str,
        evidence_valid: bool,
        exclusion_reason: str,
        output_key: str = "",
    ) -> None:
        row = dict(ladder_row)
        row.update(
            _evidence_status(
                execution_status=execution_status,
                evidence_valid=evidence_valid,
                exclusion_reason=exclusion_reason,
            )
        )
        row["output_key"] = output_key
        tier_status_rows.append(row)
        _append_jsonl(
            progress_jsonl,
            {
                "event": "ladder_step_status",
                "experiment_id": row["experiment_id"],
                "tier": row["tier"],
                "execution_status": row["execution_status"],
                "evidence_valid": row["evidence_valid"],
                "exclusion_reason": row["exclusion_reason"],
            },
        )

    for ladder_row in ladder:
        experiment_id = str(ladder_row["experiment_id"])
        tier = int(ladder_row["tier"])
        if tier not in selected_tiers:
            _record_row(
                ladder_row,
                execution_status=SKIPPED_BY_TIER_SELECTION,
                evidence_valid=False,
                exclusion_reason="excluded because lower_priority_tier_not_selected",
            )
            continue
        if experiment_id == "canonical_exact_match_cache_experiment":
            exact = run_canonical_exact_match_cache_experiment(
                num_trials=None,
                random_seed=random_seed,
                scale_label=scale_label,
                output_csv_path=out / "exact_match_cache_results.csv",
                progress_jsonl_path=progress_jsonl,
                checkpoint_json_path=out / "exact_match_checkpoint.json",
                resume_from_checkpoint=resume_from_checkpoint,
            )
            outputs["exact_match"] = exact
            _record_row(
                ladder_row,
                execution_status=EXECUTED_REAL,
                evidence_valid=True,
                exclusion_reason="",
                output_key="exact_match",
            )
            _write_json(
                suite_checkpoint,
                {
                    "suite": "local_research_sweep",
                    "scale_label": scale_label,
                    "tiers_selected": selected_tiers,
                    "completed_ids": [r["experiment_id"] for r in tier_status_rows if r["execution_status"] == EXECUTED_REAL],
                    "outputs": outputs,
                    "ladder_status": tier_status_rows,
                },
            )
            continue
        if experiment_id == "seeded_repeated_monte_carlo_family_experiment":
            seeded_family = run_seeded_repeated_monte_carlo_family_experiment(
                scale_label=scale_label,
                random_seed=random_seed + 321,
                output_csv_path=out / "seeded_repeated_family_results.csv",
                progress_jsonl_path=progress_jsonl,
                checkpoint_json_path=out / "seeded_repeated_family_checkpoint.json",
                resume_from_checkpoint=resume_from_checkpoint,
            )
            outputs["seeded_repeated_family"] = seeded_family
            _record_row(
                ladder_row,
                execution_status=EXECUTED_REAL,
                evidence_valid=True,
                exclusion_reason="",
                output_key="seeded_repeated_family",
            )
            _write_json(
                suite_checkpoint,
                {
                    "suite": "local_research_sweep",
                    "scale_label": scale_label,
                    "tiers_selected": selected_tiers,
                    "completed_ids": [r["experiment_id"] for r in tier_status_rows if r["execution_status"] == EXECUTED_REAL],
                    "outputs": outputs,
                    "ladder_status": tier_status_rows,
                },
            )
            continue
        if experiment_id == "cache_policy_comparison_experiment":
            cache_cfg = CacheExperimentConfig(
                num_requests=int(_scale_value(scale_label, "policy_comparison", "num_requests")),
                base_features={
                    "instrument_type": "european_call",
                    "num_paths": int(_scale_value(scale_label, "canonical_exact_match", "num_paths")),
                    "volatility": 0.2,
                    "maturity": 1.0,
                    "exact_match_exists": False,
                    "similarity_score": 0.8,
                },
            )
            policy = run_cache_policy_comparison_experiment(
                cache_cfg,
                {
                    "heuristic": HeuristicCachePolicy(),
                    "ai_stub": AIAssistedCachePolicy(model=None, fallback_mode="heuristic"),
                },
                scale_label=scale_label,
                progress_jsonl_path=progress_jsonl,
                checkpoint_json_path=out / "policy_comparison_checkpoint.json",
            )
            outputs["policy_comparison"] = policy
            (out / "cache_policy_comparison_with_diagnostics.json").write_text(
                json.dumps(policy, indent=2),
                encoding="utf-8",
            )
            _record_row(
                ladder_row,
                execution_status=EXECUTED_REAL,
                evidence_valid=True,
                exclusion_reason="",
                output_key="policy_comparison",
            )
            _write_json(
                suite_checkpoint,
                {
                    "suite": "local_research_sweep",
                    "scale_label": scale_label,
                    "tiers_selected": selected_tiers,
                    "completed_ids": [r["experiment_id"] for r in tier_status_rows if r["execution_status"] == EXECUTED_REAL],
                    "outputs": outputs,
                    "ladder_status": tier_status_rows,
                },
            )
            continue
        if experiment_id == "similarity_cache_replay_experiment":
            similarity = run_similarity_cache_replay_experiment(
                num_requests=None,
                random_seed=random_seed + 654,
                scale_label=scale_label,
                output_csv_path=out / "similarity_cache_replay_results.csv",
                output_manifest_path=out / "similarity_cache_replay_manifest.json",
                progress_jsonl_path=progress_jsonl,
                checkpoint_json_path=out / "similarity_replay_checkpoint.json",
                resume_from_checkpoint=resume_from_checkpoint,
            )
            outputs["similarity_replay"] = similarity
            _record_row(
                ladder_row,
                execution_status=EXECUTED_REAL,
                evidence_valid=True,
                exclusion_reason="",
                output_key="similarity_replay",
            )
            _write_json(
                suite_checkpoint,
                {
                    "suite": "local_research_sweep",
                    "scale_label": scale_label,
                    "tiers_selected": selected_tiers,
                    "completed_ids": [r["experiment_id"] for r in tier_status_rows if r["execution_status"] == EXECUTED_REAL],
                    "outputs": outputs,
                    "ladder_status": tier_status_rows,
                },
            )
            continue
        # Tier 3/4 placeholders for future optional extensions.
        _record_row(
            ladder_row,
            execution_status=SKIPPED_NOT_IMPLEMENTED,
            evidence_valid=False,
            exclusion_reason="excluded because run_not_wired_in_local_research_sweep",
        )

    valid_ladder_rows = [row for row in tier_status_rows if bool(row.get("evidence_valid", False))]
    excluded_ladder_rows = [row for row in tier_status_rows if not bool(row.get("evidence_valid", False))]
    forensic_outputs: Dict[str, Any] = {}
    for output_key, output_payload in outputs.items():
        if isinstance(output_payload, dict):
            forensic_outputs[output_key] = output_payload.get("forensic_cases", [])
    forensic_case_count_total = int(
        sum(
            len(cases) for cases in forensic_outputs.values()
            if isinstance(cases, list)
        )
    )
    manifest = {
        "suite_name": "local_research_sweep",
        "scale_label": scale_label,
        "tiers_selected": selected_tiers,
        "random_seed": int(random_seed),
        "outputs": outputs,
        "ladder": ladder,
        "ladder_status": tier_status_rows,
        "valid_evidence_ladder_steps": [row["experiment_id"] for row in valid_ladder_rows],
        "excluded_ladder_steps": [
            {
                "experiment_id": row["experiment_id"],
                "tier": row["tier"],
                "execution_status": row["execution_status"],
                "exclusion_reason": row["exclusion_reason"],
            }
            for row in excluded_ladder_rows
        ],
        "progress_jsonl_path": str(progress_jsonl),
        "forensic_outputs": forensic_outputs,
        "forensic_case_count_total": forensic_case_count_total,
        "checkpoint_files": {
            "suite": str(suite_checkpoint),
            "exact_match": str(out / "exact_match_checkpoint.json"),
            "seeded_repeated_family": str(out / "seeded_repeated_family_checkpoint.json"),
            "policy_comparison": str(out / "policy_comparison_checkpoint.json"),
            "similarity_replay": str(out / "similarity_replay_checkpoint.json"),
        },
        "summary_computed_from_valid_evidence_only": True,
        "placeholder_module_exclusions": list(PLACEHOLDER_BOUNDARY_EXCLUSIONS),
    }
    _write_json(out / "local_research_sweep_manifest.json", manifest)
    return manifest


def run_quantum_mapping_comparison_experiment(
    pricers: List[MonteCarloPricer],
) -> Dict[str, Any]:
    """Build mapping bundles for several pricers (e.g. different payoffs)."""
    if not pricers:
        return {
            "bundles": [],
            "finance_keys": [],
            **_evidence_status(
                execution_status=SKIPPED_NOT_IMPLEMENTED,
                evidence_valid=False,
                exclusion_reason="excluded because no_pricers_provided",
            ),
            "placeholder_module_exclusions": list(PLACEHOLDER_BOUNDARY_EXCLUSIONS),
        }
    bundles: List[QuantumWorkflowBundle] = []
    for pricer_index in range(len(pricers)):
        bundle = run_quantum_mapping_workflow(
            pricers[pricer_index],
            request_identifier=f"compare-{pricer_index}",
        )
        bundles.append(bundle)
    return {
        "bundles": bundles,
        "finance_keys": [bundle.finance_problem for bundle in bundles],
        **_evidence_status(
            execution_status=EXECUTED_REAL,
            evidence_valid=True,
        ),
        "placeholder_module_exclusions": list(PLACEHOLDER_BOUNDARY_EXCLUSIONS),
    }
