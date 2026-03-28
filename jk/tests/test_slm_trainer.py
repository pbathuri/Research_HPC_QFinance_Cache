"""Tests for slm_trainer and slm_policy_study modules.

Tests that require scikit-learn are skipped gracefully when the package is
not installed, using pytest.importorskip.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


# -------------------------------------------------------------------
# Synthetic data (no sklearn required)
# -------------------------------------------------------------------


def test_generate_synthetic_data():
    from qhpc_cache.slm_trainer import (
        CATEGORICAL_FEATURES,
        NUMERIC_FEATURES,
        TARGET_COLUMN,
        generate_synthetic_training_data,
    )

    df = generate_synthetic_training_data(n_samples=60, seed=7)
    assert len(df) == 60

    for col in NUMERIC_FEATURES:
        assert col in df.columns, f"missing numeric column: {col}"
    for col in CATEGORICAL_FEATURES:
        assert col in df.columns, f"missing categorical column: {col}"
    assert TARGET_COLUMN in df.columns
    assert set(df[TARGET_COLUMN].unique()).issubset({0, 1})


def test_prepare_features():
    from qhpc_cache.slm_trainer import generate_synthetic_training_data, prepare_features

    df = generate_synthetic_training_data(n_samples=50, seed=3)
    X, y, feature_names = prepare_features(df)

    assert X.shape[0] == 50
    assert X.shape[1] == len(feature_names)
    assert len(y) == 50
    assert set(y).issubset({0, 1})
    assert feature_names == sorted(feature_names), "feature names must be sorted"
    assert not np.isnan(X).any(), "NaN values should be filled with 0"


# -------------------------------------------------------------------
# Training (requires sklearn)
# -------------------------------------------------------------------


def test_train_gradient_boosting():
    pytest.importorskip("sklearn")
    from qhpc_cache.slm_trainer import (
        generate_synthetic_training_data,
        prepare_features,
        train_reuse_model,
    )

    df = generate_synthetic_training_data(n_samples=100, seed=1)
    X, y, _ = prepare_features(df)
    model = train_reuse_model(X, y, model_type="gradient_boosting")

    assert hasattr(model, "predict_proba")
    probs = model.predict_proba(X)
    assert probs.shape == (100, 2)
    assert np.allclose(probs.sum(axis=1), 1.0, atol=1e-6)


def test_train_logistic_regression():
    pytest.importorskip("sklearn")
    from qhpc_cache.slm_trainer import (
        generate_synthetic_training_data,
        prepare_features,
        train_reuse_model,
    )

    df = generate_synthetic_training_data(n_samples=100, seed=2)
    X, y, _ = prepare_features(df)
    model = train_reuse_model(X, y, model_type="logistic_regression")

    assert hasattr(model, "predict_proba")
    assert hasattr(model, "coef_")


def test_train_random_forest():
    pytest.importorskip("sklearn")
    from qhpc_cache.slm_trainer import (
        generate_synthetic_training_data,
        prepare_features,
        train_reuse_model,
    )

    df = generate_synthetic_training_data(n_samples=100, seed=5)
    X, y, _ = prepare_features(df)
    model = train_reuse_model(X, y, model_type="random_forest")

    assert hasattr(model, "predict_proba")
    assert hasattr(model, "feature_importances_")


# -------------------------------------------------------------------
# Evaluation (requires sklearn)
# -------------------------------------------------------------------


def test_evaluate_model():
    pytest.importorskip("sklearn")
    from qhpc_cache.slm_trainer import (
        EvalMetrics,
        evaluate_model,
        generate_synthetic_training_data,
        prepare_features,
        train_reuse_model,
    )

    df = generate_synthetic_training_data(n_samples=200, seed=10)
    X, y, fnames = prepare_features(df)
    model = train_reuse_model(X, y, model_type="gradient_boosting")
    metrics = evaluate_model(model, X, y, feature_names=fnames)

    assert isinstance(metrics, EvalMetrics)
    assert 0.0 <= metrics.accuracy <= 1.0
    assert 0.0 <= metrics.precision <= 1.0
    assert 0.0 <= metrics.recall <= 1.0
    assert 0.0 <= metrics.f1 <= 1.0
    assert 0.0 <= metrics.auc_roc <= 1.0
    assert len(metrics.confusion_matrix) == 2
    assert len(metrics.feature_importances) == len(fnames)


def test_cross_validate():
    pytest.importorskip("sklearn")
    from qhpc_cache.slm_trainer import (
        CrossValReport,
        cross_validate_model,
        generate_synthetic_training_data,
        prepare_features,
    )

    df = generate_synthetic_training_data(n_samples=150, seed=11)
    X, y, _ = prepare_features(df)
    report = cross_validate_model(X, y, model_type="gradient_boosting", k=3, seed=11)

    assert isinstance(report, CrossValReport)
    assert len(report.fold_metrics) == 3
    assert 0.0 <= report.mean_accuracy <= 1.0
    assert 0.0 <= report.mean_f1 <= 1.0
    assert report.std_f1 >= 0.0


# -------------------------------------------------------------------
# Persistence (requires sklearn + joblib)
# -------------------------------------------------------------------


def test_model_export_load_roundtrip(tmp_path: Path):
    pytest.importorskip("sklearn")
    pytest.importorskip("joblib")
    from qhpc_cache.slm_trainer import (
        export_model,
        generate_synthetic_training_data,
        load_model,
        prepare_features,
        train_reuse_model,
    )

    df = generate_synthetic_training_data(n_samples=100, seed=20)
    X, y, _ = prepare_features(df)
    model = train_reuse_model(X, y, model_type="gradient_boosting")

    model_path = tmp_path / "test_model.joblib"
    returned_path = export_model(model, model_path)
    assert returned_path.exists()

    loaded = load_model(returned_path)
    orig_probs = model.predict_proba(X)
    loaded_probs = loaded.predict_proba(X)
    np.testing.assert_array_almost_equal(orig_probs, loaded_probs)


# -------------------------------------------------------------------
# Model card (no sklearn required for the dataclass itself)
# -------------------------------------------------------------------


def test_model_card():
    from qhpc_cache.slm_trainer import EvalMetrics, ModelCard

    metrics = EvalMetrics(
        accuracy=0.85,
        precision=0.82,
        recall=0.88,
        f1=0.85,
        auc_roc=0.91,
        confusion_matrix=[[40, 8], [6, 46]],
        feature_importances={"similarity_score": 0.35, "locality_score": 0.20},
    )
    card = ModelCard(
        model_type="gradient_boosting",
        training_date="2025-01-01T00:00:00Z",
        feature_names=["similarity_score", "locality_score"],
        n_training_samples=100,
        n_features=2,
        eval_metrics=metrics,
        data_provenance="unit_test",
    )

    assert card.model_type == "gradient_boosting"
    assert card.n_training_samples == 100
    assert card.n_features == 2
    assert card.schema_version == "1.0"
    assert card.eval_metrics.f1 == 0.85
    assert card.data_provenance == "unit_test"


# -------------------------------------------------------------------
# Full policy study smoke test (requires sklearn)
# -------------------------------------------------------------------


def test_policy_study_smoke(tmp_path: Path):
    pytest.importorskip("sklearn")
    from qhpc_cache.slm_policy_study import run_slm_policy_comparison

    out = tmp_path / "study_out"
    summary = run_slm_policy_comparison(
        output_dir=out,
        scale_label="smoke",
        model_type="gradient_boosting",
        seed=99,
        cv_folds=3,
    )

    assert "results" in summary
    for name in ("heuristic", "logistic", "slm_trained"):
        assert name in summary["results"], f"missing policy: {name}"
        r = summary["results"][name]
        assert r["total_requests"] > 0
        assert 0.0 <= r["precision"] <= 1.0
        assert 0.0 <= r["recall"] <= 1.0

    assert (out / "policy_comparison.csv").exists()
    assert (out / "slm_model_card.json").exists()
    assert (out / "policy_evaluation.json").exists()
    assert (out / "feature_importance.csv").exists()
