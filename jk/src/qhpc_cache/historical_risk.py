"""Historical and event-window risk metrics; reuses sample VaR/CVaR from ``risk_metrics``."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None  # type: ignore

from qhpc_cache.risk_metrics import compute_conditional_value_at_risk, compute_value_at_risk


def compute_historical_var(
    return_samples: Sequence[float],
    *,
    confidence_level: float = 0.95,
) -> float:
    """VaR on **return** distribution: loss if return is negative tail (positive magnitude)."""
    pnl_proxy = [float(value) for value in return_samples]
    negated = [-value for value in pnl_proxy]
    return compute_value_at_risk(negated, confidence_level)


def compute_historical_cvar(
    return_samples: Sequence[float],
    *,
    confidence_level: float = 0.95,
) -> float:
    """CVaR on return tail via negated samples."""
    negated = [-float(value) for value in return_samples]
    return compute_conditional_value_at_risk(negated, confidence_level)


def compute_event_window_var(
    event_return_series: Sequence[float],
    *,
    confidence_level: float = 0.95,
) -> float:
    """VaR from intraday or short-window returns."""
    return compute_historical_var(event_return_series, confidence_level=confidence_level)


def compute_event_window_drawdown(
    price_series: Sequence[float],
) -> float:
    """Max drawdown on a single price path (e.g., event-window mid quotes)."""
    if not price_series:
        return 0.0
    peak = float(price_series[0])
    max_dd = 0.0
    for raw in price_series:
        price = float(raw)
        if price > peak:
            peak = price
        drawdown = price / peak - 1.0
        if drawdown < max_dd:
            max_dd = drawdown
    return float(-max_dd)


def summarize_historical_risk(
    wide_returns: "pd.DataFrame",
    *,
    confidence_level: float = 0.95,
) -> Dict[str, Any]:
    """Per-column VaR/CVaR on daily return samples (last 252 rows per column if longer)."""
    if pd is None:
        raise RuntimeError("pandas required")
    tail = wide_returns.tail(252)
    per_symbol: Dict[str, Dict[str, float]] = {}
    for column in tail.columns:
        series = tail[column].dropna().astype(float).tolist()
        if len(series) < 10:
            continue
        per_symbol[str(column)] = {
            "var_loss_on_return": compute_historical_var(series, confidence_level=confidence_level),
            "cvar_loss_on_return": compute_historical_cvar(series, confidence_level=confidence_level),
            "sample_count": float(len(series)),
        }
    return {"per_symbol": per_symbol, "confidence_level": confidence_level}
