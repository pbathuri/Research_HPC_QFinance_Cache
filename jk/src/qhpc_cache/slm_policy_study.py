"""Compare heuristic, logistic, and SLM-trained cache policies head-to-head.

Runs a controlled experiment where each policy processes the same sequence of
requests against its own fresh cache, then compares precision / recall / F1 /
utility metrics to determine which policy best identifies reuse opportunities.
"""

from __future__ import annotations

import csv
import dataclasses
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from qhpc_cache.cache_policy import (
    AIAssistedCachePolicy,
    HeuristicCachePolicy,
    LogisticCachePolicy,
)
from qhpc_cache.cache_store import SimpleCacheStore
from qhpc_cache.slm_trainer import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    TARGET_COLUMN,
    CrossValReport,
    EvalMetrics,
    ModelCard,
    build_model_card,
    cross_validate_model,
    evaluate_model,
    generate_synthetic_training_data,
    train_reuse_model,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scale profiles for the study
# ---------------------------------------------------------------------------

STUDY_SCALE: Dict[str, Dict[str, int]] = {
    "smoke": {"n_train": 300, "n_test_unique": 80, "n_test_repeats": 40},
    "standard": {"n_train": 2000, "n_test_unique": 500, "n_test_repeats": 250},
    "heavy": {"n_train": 10000, "n_test_unique": 2500, "n_test_repeats": 1250},
}

_CACHE_KEY_PARAMS = ["S0", "K", "sigma", "T", "r", "num_paths"]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class PolicyRunResult:
    policy_name: str
    total_requests: int
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    precision: float
    recall: float
    f1: float
    total_utility: float
    mean_utility: float
    total_latency_saved_ms: float
    decisions: List[Dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _cache_key_dict(request: Dict[str, Any]) -> Dict[str, Any]:
    """Extract pricing parameters used as the deterministic cache key."""
    return {
        "S0": round(float(request.get("S0", 0)), 8),
        "K": round(float(request.get("K", 0)), 8),
        "sigma": round(float(request.get("sigma", 0)), 8),
        "T": round(float(request.get("T", 0)), 8),
        "r": round(float(request.get("r", 0)), 8),
        "num_paths": int(request.get("num_paths", 0)),
    }


def _build_heuristic_features(
    request: Dict[str, Any], is_cached: bool
) -> Dict[str, Any]:
    """Build features dict for HeuristicCachePolicy / LogisticCachePolicy."""
    return {
        "exact_match_exists": is_cached,
        "similarity_score": 1.0 if is_cached else float(request.get("similarity_score", 0.0)),
        "num_paths": int(request.get("num_paths", 10000)),
        "volatility": float(request.get("sigma", 0.2)),
        "maturity_in_years": float(request.get("T", 1.0)),
    }


def _build_ai_features(
    request: Dict[str, Any],
    deploy_feature_names: List[str],
    is_cached: bool,
) -> Dict[str, Any]:
    """Build features dict keyed by the model's sorted training feature names.

    AIAssistedCachePolicy sorts dict keys alphabetically before building the
    feature vector, so using the sorted training feature names as keys
    guarantees the same ordering the model was trained on.
    """
    features: Dict[str, Any] = {}
    for fname in deploy_feature_names:
        if fname == "similarity_score":
            features[fname] = 1.0 if is_cached else float(
                request.get("similarity_score", 0.0)
            )
        else:
            val = request.get(fname, 0.0)
            features[fname] = float(val) if isinstance(val, (int, float, np.floating, np.integer)) else 0.0
    return features


def _generate_test_requests(
    n_unique: int, n_repeats: int, seed: int
) -> List[Dict[str, Any]]:
    """Create a request sequence with intentional repeats for cache-hit testing."""
    base_df = generate_synthetic_training_data(n_samples=n_unique, seed=seed)
    base_dicts = [row.to_dict() for _, row in base_df.iterrows()]

    rng = np.random.RandomState(seed + 7777)
    repeat_indices = rng.choice(n_unique, size=n_repeats, replace=True)
    repeats = [base_dicts[i].copy() for i in repeat_indices]

    all_requests = base_dicts + repeats
    rng.shuffle(all_requests)
    return all_requests


# ---------------------------------------------------------------------------
# Simulation core
# ---------------------------------------------------------------------------


def _simulate_policy_decisions(
    requests: List[Dict[str, Any]],
    policy: Any,
    cache_store: SimpleCacheStore,
    deploy_feature_names: Optional[List[str]] = None,
) -> PolicyRunResult:
    """Run requests through a policy + cache, tracking TP / FP / TN / FN.

    Ground truth: whether the request's parameter set is already in the cache
    at the time the policy makes its decision.
    """
    use_ai = isinstance(policy, AIAssistedCachePolicy) and deploy_feature_names is not None
    policy_name = policy.__class__.__name__

    tp = fp = tn = fn = 0
    total_utility = 0.0
    total_latency_saved = 0.0
    decisions: List[Dict] = []

    for i, req in enumerate(requests):
        ck = _cache_key_dict(req)
        is_cached = cache_store.has(ck)

        if use_ai:
            features = _build_ai_features(req, deploy_feature_names, is_cached)
        else:
            features = _build_heuristic_features(req, is_cached)

        decision = policy.decide(features)
        compute_ms = float(req.get("pricing_compute_time_ms", 0.0))

        if decision and is_cached:
            tp += 1
            total_utility += compute_ms
            total_latency_saved += compute_ms
            classification = "TP"
        elif decision and not is_cached:
            fp += 1
            classification = "FP"
        elif not decision and not is_cached:
            tn += 1
            classification = "TN"
        else:
            fn += 1
            classification = "FN"

        decisions.append({
            "index": i,
            "ground_truth_cached": is_cached,
            "policy_decision": decision,
            "classification": classification,
        })

        if not is_cached:
            cache_store.put(ck, {"price": 0.0, "source": "simulated"})

    total = len(requests)
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2.0 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

    return PolicyRunResult(
        policy_name=policy_name,
        total_requests=total,
        true_positive=tp,
        false_positive=fp,
        true_negative=tn,
        false_negative=fn,
        precision=prec,
        recall=rec,
        f1=f1,
        total_utility=total_utility,
        mean_utility=total_utility / total if total > 0 else 0.0,
        total_latency_saved_ms=total_latency_saved,
        decisions=decisions,
    )


# ---------------------------------------------------------------------------
# Output writing
# ---------------------------------------------------------------------------


def _write_comparison_outputs(
    results: Dict[str, PolicyRunResult],
    model_card: ModelCard,
    feature_importances: Dict[str, float],
    output_dir: Path,
) -> None:
    """Write all study output artefacts."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- policy_comparison.csv ---
    csv_path = output_dir / "policy_comparison.csv"
    fieldnames = [
        "policy_name", "total_requests",
        "true_positive", "false_positive", "true_negative", "false_negative",
        "precision", "recall", "f1",
        "total_utility", "mean_utility", "total_latency_saved_ms",
    ]
    with open(csv_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for name in sorted(results):
            r = results[name]
            writer.writerow({
                "policy_name": name,
                "total_requests": r.total_requests,
                "true_positive": r.true_positive,
                "false_positive": r.false_positive,
                "true_negative": r.true_negative,
                "false_negative": r.false_negative,
                "precision": round(r.precision, 6),
                "recall": round(r.recall, 6),
                "f1": round(r.f1, 6),
                "total_utility": round(r.total_utility, 4),
                "mean_utility": round(r.mean_utility, 4),
                "total_latency_saved_ms": round(r.total_latency_saved_ms, 4),
            })

    # --- slm_model_card.json ---
    card_path = output_dir / "slm_model_card.json"
    card_dict = dataclasses.asdict(model_card)
    card_path.write_text(json.dumps(card_dict, indent=2, default=str))

    # --- policy_evaluation.json ---
    eval_path = output_dir / "policy_evaluation.json"
    eval_payload: Dict[str, Any] = {}
    for name, r in results.items():
        entry = dataclasses.asdict(r)
        entry.pop("decisions", None)
        eval_payload[name] = entry
    eval_path.write_text(json.dumps(eval_payload, indent=2, default=str))

    # --- feature_importance.csv ---
    fi_path = output_dir / "feature_importance.csv"
    sorted_fi = sorted(feature_importances.items(), key=lambda kv: -kv[1])
    with open(fi_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["feature_name", "importance"])
        for fname, imp in sorted_fi:
            writer.writerow([fname, round(imp, 8)])


# ---------------------------------------------------------------------------
# Main experiment entry point
# ---------------------------------------------------------------------------


def run_slm_policy_comparison(
    output_dir: Path,
    scale_label: str = "smoke",
    model_type: str = "gradient_boosting",
    seed: int = 42,
    cv_folds: int = 5,
) -> Dict[str, Any]:
    """Run the full SLM policy comparison experiment.

    Phase 1: Generate synthetic training data (or load existing SLM exports)
    Phase 2: Train SLM model
    Phase 3: Create heuristic, logistic, and AI-assisted policies
    Phase 4: Generate test workload with intentional repeats
    Phase 5: Simulate each policy on the test workload
    Phase 6: Write comparison outputs
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    scale = STUDY_SCALE.get(scale_label, STUDY_SCALE["smoke"])

    logger.info("Phase 1: generating %d training samples", scale["n_train"])
    train_df = generate_synthetic_training_data(
        n_samples=scale["n_train"], seed=seed
    )

    # Use sorted numeric features for deployment (compatible with AIAssistedCachePolicy)
    deploy_features = sorted(
        c for c in NUMERIC_FEATURES if c in train_df.columns
    )
    X_train = train_df[deploy_features].fillna(0).values.astype(float)
    y_train = train_df[TARGET_COLUMN].astype(float).astype(int).values

    logger.info("Phase 2: training %s model on %d features", model_type, len(deploy_features))
    model = train_reuse_model(X_train, y_train, model_type=model_type, seed=seed)

    eval_metrics = evaluate_model(model, X_train, y_train, deploy_features)
    cv_report = cross_validate_model(
        X_train, y_train, model_type=model_type, k=cv_folds, seed=seed
    )
    model_card = build_model_card(
        model, model_type, X_train, y_train, eval_metrics,
        data_provenance=f"synthetic_{scale_label}_n{scale['n_train']}",
    )

    logger.info("Phase 3: creating policies")
    heuristic_policy = HeuristicCachePolicy()
    logistic_policy = LogisticCachePolicy()
    ai_policy = AIAssistedCachePolicy(model=model)

    logger.info(
        "Phase 4: generating test workload (%d unique, %d repeats)",
        scale["n_test_unique"], scale["n_test_repeats"],
    )
    test_requests = _generate_test_requests(
        n_unique=scale["n_test_unique"],
        n_repeats=scale["n_test_repeats"],
        seed=seed + 1000,
    )

    logger.info("Phase 5: running policy simulations")
    policy_configs = {
        "heuristic": (heuristic_policy, None),
        "logistic": (logistic_policy, None),
        "slm_trained": (ai_policy, deploy_features),
    }
    results: Dict[str, PolicyRunResult] = {}
    for name, (policy, feat_names) in policy_configs.items():
        cache = SimpleCacheStore(enable_logging=False)
        results[name] = _simulate_policy_decisions(
            test_requests, policy, cache, deploy_feature_names=feat_names,
        )
        logger.info(
            "  %s: P=%.3f R=%.3f F1=%.3f saved=%.1fms",
            name, results[name].precision, results[name].recall,
            results[name].f1, results[name].total_latency_saved_ms,
        )

    logger.info("Phase 6: writing outputs to %s", output_dir)
    _write_comparison_outputs(
        results, model_card, eval_metrics.feature_importances, output_dir,
    )

    summary: Dict[str, Any] = {
        "results": {},
        "model_card": dataclasses.asdict(model_card),
        "cv_report": {
            "mean_accuracy": cv_report.mean_accuracy,
            "mean_f1": cv_report.mean_f1,
            "mean_auc_roc": cv_report.mean_auc_roc,
            "std_f1": cv_report.std_f1,
        },
        "output_dir": str(output_dir),
        "scale_label": scale_label,
    }
    for name, r in results.items():
        entry = dataclasses.asdict(r)
        entry.pop("decisions", None)
        summary["results"][name] = entry

    return summary
