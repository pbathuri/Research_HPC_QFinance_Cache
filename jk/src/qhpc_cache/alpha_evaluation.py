"""Lightweight feature evaluation: forward returns, IC-style correlations (research grade)."""

from __future__ import annotations

from typing import Any, Dict, List

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None  # type: ignore


def compute_forward_returns(
    wide_returns: "pd.DataFrame",
    horizon: int = 5,
) -> "pd.DataFrame":
    """Sum of next ``horizon`` daily simple returns (additive approximation)."""
    if pd is None:
        raise RuntimeError("pandas required")
    acc = wide_returns * 0.0
    for horizon_step in range(1, horizon + 1):
        acc = acc + wide_returns.shift(-horizon_step)
    return acc


def evaluate_feature_information_coefficient(
    feature_wide: "pd.DataFrame",
    forward_return_wide: "pd.DataFrame",
) -> "pd.Series":
    """Cross-sectional Pearson correlation per date (IC time series)."""
    if pd is None:
        raise RuntimeError("pandas required")
    common_index = feature_wide.index.intersection(forward_return_wide.index)
    common_cols = feature_wide.columns.intersection(forward_return_wide.columns)
    ic_list: List[float] = []
    idx_list: List[Any] = []
    for dt in common_index:
        fx = feature_wide.loc[dt, common_cols].astype(float)
        ry = forward_return_wide.loc[dt, common_cols].astype(float)
        pair = pd.concat([fx, ry], axis=1, keys=["f", "r"]).dropna()
        if len(pair) < 5:
            continue
        ic_list.append(float(pair["f"].corr(pair["r"])))
        idx_list.append(dt)
    return pd.Series(ic_list, index=idx_list, name="ic")


def evaluate_feature_rank_correlation(
    feature_wide: "pd.DataFrame",
    forward_return_wide: "pd.DataFrame",
) -> "pd.Series":
    """Cross-sectional Spearman per date when scipy available; else rank-Pearson."""
    if pd is None:
        raise RuntimeError("pandas required")
    common_index = feature_wide.index.intersection(forward_return_wide.index)
    common_cols = feature_wide.columns.intersection(forward_return_wide.columns)
    ranks_f = feature_wide.loc[common_index, common_cols].rank(axis=1, pct=True)
    ranks_r = forward_return_wide.loc[common_index, common_cols].rank(axis=1, pct=True)
    return evaluate_feature_information_coefficient(ranks_f, ranks_r)


def summarize_feature_predictiveness(ic_series: "pd.Series") -> Dict[str, float]:
    """Mean IC, std, hit rate (IC > 0)."""
    clean = ic_series.dropna().astype(float)
    if clean.empty:
        return {"mean_ic": 0.0, "std_ic": 0.0, "hit_rate": 0.0, "n": 0.0}
    return {
        "mean_ic": float(clean.mean()),
        "std_ic": float(clean.std()),
        "hit_rate": float((clean > 0).mean()),
        "n": float(len(clean)),
    }


def compare_feature_stability(
    ic_series: "pd.Series",
    *,
    split_fraction: float = 0.5,
) -> Dict[str, Any]:
    """Compare mean IC in first vs second half of dates (rough stability)."""
    clean = ic_series.dropna().astype(float)
    if len(clean) < 4:
        return {"first_half_mean": 0.0, "second_half_mean": 0.0, "stable": True}
    split_idx = int(len(clean) * split_fraction)
    first = clean.iloc[:split_idx]
    second = clean.iloc[split_idx:]
    return {
        "first_half_mean": float(first.mean()),
        "second_half_mean": float(second.mean()),
        "stable": abs(first.mean() - second.mean()) < 0.05,
    }
