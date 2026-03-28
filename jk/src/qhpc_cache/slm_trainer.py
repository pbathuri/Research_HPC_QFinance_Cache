"""Train and evaluate ML models for cache reuse prediction using SLM export data.

Produces trained classifiers that predict whether a given request will produce
a cache hit, suitable for plugging into AIAssistedCachePolicy.predict_proba.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )
    from sklearn.model_selection import StratifiedKFold

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import joblib

    JOBLIB_AVAILABLE = True
except ImportError:
    JOBLIB_AVAILABLE = False


# ---------------------------------------------------------------------------
# Feature schema
# ---------------------------------------------------------------------------

NUMERIC_FEATURES = [
    "similarity_score",
    "locality_score",
    "reuse_distance",
    "working_set_size",
    "error_if_reused",
    "latency_saved_ms",
    "utility_score",
    "portfolio_overlap_score",
    "event_overlap_score",
    "S0",
    "K",
    "sigma",
    "T",
    "r",
    "num_paths",
    "pricing_compute_time_ms",
    "decision_overhead_ms",
    "gross_runtime_saved_ms",
    "net_runtime_saved_ms",
]

CATEGORICAL_FEATURES = [
    "workload_family",
    "lane_id",
    "engine_name",
    "reuse_candidate_type",
    "policy_tier",
    "workload_regime",
]

TARGET_COLUMN = "cache_hit"


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class EvalMetrics:
    accuracy: float
    precision: float
    recall: float
    f1: float
    auc_roc: float
    confusion_matrix: List[List[int]]
    feature_importances: Dict[str, float]


@dataclass
class CrossValReport:
    fold_metrics: List[EvalMetrics]
    mean_accuracy: float
    mean_f1: float
    mean_auc_roc: float
    std_f1: float


@dataclass
class ModelCard:
    model_type: str
    training_date: str
    feature_names: List[str]
    n_training_samples: int
    n_features: int
    eval_metrics: EvalMetrics
    data_provenance: str
    schema_version: str = "1.0"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_slm_dataset(path: Path) -> pd.DataFrame:
    """Read reuse_decision_dataset.csv or slm_training_examples.jsonl."""
    path = Path(path)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    if path.suffix == ".jsonl":
        records: List[Dict[str, Any]] = []
        with open(path) as fh:
            for line in fh:
                stripped = line.strip()
                if stripped:
                    records.append(json.loads(stripped))
        return pd.DataFrame(records)
    raise ValueError(f"Unsupported file format: {path.suffix}")


# ---------------------------------------------------------------------------
# Feature preparation
# ---------------------------------------------------------------------------


def prepare_features(
    df: pd.DataFrame,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Select numeric features, one-hot encode categoricals, fill NaN with 0.

    Returns ``(X, y, feature_names)`` with feature columns sorted
    alphabetically so the ordering is deterministic and compatible with
    AIAssistedCachePolicy's sorted-key feature extraction.
    """
    numeric_cols = [c for c in NUMERIC_FEATURES if c in df.columns]
    X_num = df[numeric_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)

    cat_cols = [c for c in CATEGORICAL_FEATURES if c in df.columns]
    if cat_cols:
        X_cat = pd.get_dummies(df[cat_cols].astype(str), prefix_sep="=")
    else:
        X_cat = pd.DataFrame(index=df.index)

    combined = pd.concat([X_num, X_cat], axis=1)
    combined = combined.reindex(sorted(combined.columns), axis=1).fillna(0.0)

    feature_names = list(combined.columns)
    X = combined.values.astype(float)

    y_raw = df[TARGET_COLUMN]
    if y_raw.dtype == object:
        y = y_raw.map(
            lambda v: 1 if str(v).strip().lower() in ("true", "1", "1.0") else 0
        ).values
    else:
        y = y_raw.astype(float).astype(int).values

    return X, y, feature_names


# ---------------------------------------------------------------------------
# Synthetic data generation (no sklearn required)
# ---------------------------------------------------------------------------

_SYNTHETIC_FAMILIES = [
    "exact_repeat_pricing",
    "near_repeat_pricing",
    "path_ladder_pricing",
    "stress_churn_pricing",
    "portfolio_cluster_condensation",
]
_SYNTHETIC_LANES = ["lane_a", "lane_b"]
_SYNTHETIC_ENGINES = ["classical_mc", "quantlib_mc"]
_SYNTHETIC_CANDIDATE_TYPES = ["exact", "similarity", "none"]
_SYNTHETIC_TIERS = ["exact_only", "similarity_enabled", "aggressive"]
_SYNTHETIC_REGIMES = ["normal", "high_vol", "crisis"]


def generate_synthetic_training_data(
    n_samples: int = 500, seed: int = 42
) -> pd.DataFrame:
    """Generate synthetic SLM data for testing/bootstrapping.

    Uses a latent logistic model so the target is learnable from features.
    """
    rng = np.random.RandomState(seed)

    data: Dict[str, Any] = {}

    data["similarity_score"] = rng.uniform(0.0, 1.0, n_samples)
    data["locality_score"] = rng.uniform(0.0, 1.0, n_samples)
    data["reuse_distance"] = rng.exponential(5.0, n_samples)
    data["working_set_size"] = rng.randint(10, 500, n_samples).astype(float)
    data["error_if_reused"] = rng.exponential(0.01, n_samples)
    data["latency_saved_ms"] = rng.uniform(0.0, 200.0, n_samples)
    data["utility_score"] = rng.uniform(-0.5, 1.0, n_samples)
    data["portfolio_overlap_score"] = rng.uniform(0.0, 1.0, n_samples)
    data["event_overlap_score"] = rng.uniform(0.0, 1.0, n_samples)

    data["S0"] = rng.uniform(50.0, 200.0, n_samples)
    data["K"] = data["S0"] * rng.uniform(0.8, 1.2, n_samples)
    data["sigma"] = rng.uniform(0.05, 0.60, n_samples)
    data["T"] = rng.uniform(0.1, 3.0, n_samples)
    data["r"] = rng.uniform(0.01, 0.10, n_samples)
    data["num_paths"] = rng.choice(
        [1000, 10000, 50000, 100000, 500000], n_samples
    ).astype(float)
    data["pricing_compute_time_ms"] = rng.uniform(5.0, 500.0, n_samples)
    data["decision_overhead_ms"] = rng.uniform(0.05, 5.0, n_samples)
    data["gross_runtime_saved_ms"] = data["latency_saved_ms"] * rng.uniform(
        0.5, 1.0, n_samples
    )
    data["net_runtime_saved_ms"] = (
        data["gross_runtime_saved_ms"] - data["decision_overhead_ms"]
    )

    data["workload_family"] = rng.choice(_SYNTHETIC_FAMILIES, n_samples)
    data["lane_id"] = rng.choice(_SYNTHETIC_LANES, n_samples)
    data["engine_name"] = rng.choice(_SYNTHETIC_ENGINES, n_samples)
    data["reuse_candidate_type"] = rng.choice(_SYNTHETIC_CANDIDATE_TYPES, n_samples)
    data["policy_tier"] = rng.choice(_SYNTHETIC_TIERS, n_samples)
    data["workload_regime"] = rng.choice(_SYNTHETIC_REGIMES, n_samples)

    logit = (
        1.5 * data["similarity_score"]
        + 0.8 * data["locality_score"]
        - 0.05 * data["reuse_distance"]
        - 0.3 * data["error_if_reused"]
        + 0.5 * data["portfolio_overlap_score"]
        - 0.8
    )
    prob = 1.0 / (1.0 + np.exp(-logit))
    data[TARGET_COLUMN] = (rng.uniform(0, 1, n_samples) < prob).astype(int)

    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Model training
# ---------------------------------------------------------------------------


def train_reuse_model(
    X: np.ndarray,
    y: np.ndarray,
    model_type: str = "gradient_boosting",
    seed: int = 42,
) -> Any:
    """Train a sklearn classifier for cache-hit prediction."""
    if not SKLEARN_AVAILABLE:
        raise ImportError(
            "scikit-learn is required for model training. "
            "Install with: pip install scikit-learn"
        )

    constructors = {
        "gradient_boosting": lambda: GradientBoostingClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            random_state=seed,
            min_samples_leaf=5,
        ),
        "logistic_regression": lambda: LogisticRegression(
            max_iter=2000, random_state=seed, solver="lbfgs"
        ),
        "random_forest": lambda: RandomForestClassifier(
            n_estimators=100,
            max_depth=6,
            random_state=seed,
            min_samples_leaf=5,
        ),
    }

    if model_type not in constructors:
        raise ValueError(
            f"Unsupported model_type {model_type!r}. "
            f"Choose from {sorted(constructors)}."
        )

    model = constructors[model_type]()
    model.fit(X, y)
    return model


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate_model(
    model: Any,
    X_test: np.ndarray,
    y_test: np.ndarray,
    feature_names: Optional[List[str]] = None,
) -> EvalMetrics:
    """Compute classification metrics and feature importances."""
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    importances: Dict[str, float] = {}
    if feature_names:
        if hasattr(model, "feature_importances_"):
            raw = model.feature_importances_
        elif hasattr(model, "coef_"):
            raw = np.abs(model.coef_[0])
        else:
            raw = np.zeros(len(feature_names))
        for name, imp in zip(feature_names, raw):
            importances[name] = float(imp)

    cm = confusion_matrix(y_test, y_pred)

    try:
        auc = float(roc_auc_score(y_test, y_prob))
    except ValueError:
        auc = 0.5

    return EvalMetrics(
        accuracy=float(accuracy_score(y_test, y_pred)),
        precision=float(precision_score(y_test, y_pred, zero_division=0)),
        recall=float(recall_score(y_test, y_pred, zero_division=0)),
        f1=float(f1_score(y_test, y_pred, zero_division=0)),
        auc_roc=auc,
        confusion_matrix=cm.tolist(),
        feature_importances=importances,
    )


def cross_validate_model(
    X: np.ndarray,
    y: np.ndarray,
    model_type: str = "gradient_boosting",
    k: int = 5,
    seed: int = 42,
) -> CrossValReport:
    """Stratified k-fold cross-validation."""
    if not SKLEARN_AVAILABLE:
        raise ImportError("scikit-learn is required for cross-validation.")

    skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=seed)
    fold_metrics: List[EvalMetrics] = []

    for train_idx, test_idx in skf.split(X, y):
        X_tr, X_te = X[train_idx], X[test_idx]
        y_tr, y_te = y[train_idx], y[test_idx]
        model = train_reuse_model(X_tr, y_tr, model_type=model_type, seed=seed)
        fold_metrics.append(evaluate_model(model, X_te, y_te))

    accuracies = [m.accuracy for m in fold_metrics]
    f1s = [m.f1 for m in fold_metrics]
    aucs = [m.auc_roc for m in fold_metrics]

    return CrossValReport(
        fold_metrics=fold_metrics,
        mean_accuracy=float(np.mean(accuracies)),
        mean_f1=float(np.mean(f1s)),
        mean_auc_roc=float(np.mean(aucs)),
        std_f1=float(np.std(f1s)),
    )


# ---------------------------------------------------------------------------
# Model persistence
# ---------------------------------------------------------------------------


def export_model(model: Any, path: Path) -> Path:
    """Serialize model with joblib."""
    if not JOBLIB_AVAILABLE:
        raise ImportError(
            "joblib is required for model export. Install with: pip install joblib"
        )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    return path


def load_model(path: Path) -> Any:
    """Deserialize model with joblib."""
    if not JOBLIB_AVAILABLE:
        raise ImportError(
            "joblib is required for model loading. Install with: pip install joblib"
        )
    return joblib.load(Path(path))


# ---------------------------------------------------------------------------
# Model card
# ---------------------------------------------------------------------------


def build_model_card(
    model: Any,
    model_type: str,
    X: np.ndarray,
    y: np.ndarray,
    eval_metrics: EvalMetrics,
    data_provenance: str = "",
) -> ModelCard:
    """Assemble a ModelCard from training artefacts and evaluation results."""
    return ModelCard(
        model_type=model_type,
        training_date=datetime.now(timezone.utc).isoformat(),
        feature_names=list(eval_metrics.feature_importances.keys()),
        n_training_samples=int(X.shape[0]),
        n_features=int(X.shape[1]),
        eval_metrics=eval_metrics,
        data_provenance=data_provenance,
    )
