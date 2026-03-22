"""Return panels and rolling risk features from saved daily OHLCV (pandas)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None  # type: ignore


def compute_log_returns(
    price_frame: "pd.DataFrame",
    *,
    close_column: str = "close",
    symbol_column: str = "symbol",
    date_column: str = "date",
) -> "pd.DataFrame":
    """Per-symbol log return: log(C_t) - log(C_{t-1})."""
    if pd is None:
        raise RuntimeError("pandas required")
    import numpy as np

    frame = price_frame.sort_values([symbol_column, date_column]).copy()
    frame["log_return"] = frame.groupby(symbol_column)[close_column].transform(
        lambda series: np.log(series).diff()
    )
    return frame.dropna(subset=["log_return"])


def compute_simple_returns(
    price_frame: "pd.DataFrame",
    *,
    close_column: str = "close",
    symbol_column: str = "symbol",
    date_column: str = "date",
) -> "pd.DataFrame":
    """Per-symbol simple return on close."""
    if pd is None:
        raise RuntimeError("pandas required")
    frame = price_frame.sort_values([symbol_column, date_column]).copy()
    frame["simple_return"] = frame.groupby(symbol_column)[close_column].pct_change()
    return frame.dropna(subset=["simple_return"])


def align_return_panel(
    return_frame: "pd.DataFrame",
    *,
    date_column: str = "date",
    symbol_column: str = "symbol",
    value_column: str = "log_return",
) -> "pd.DataFrame":
    """Pivot to wide: index=date, columns=symbol."""
    if pd is None:
        raise RuntimeError("pandas required")
    pivot = return_frame.pivot_table(
        index=date_column,
        columns=symbol_column,
        values=value_column,
        aggfunc="first",
    )
    pivot.sort_index(inplace=True)
    return pivot


def compute_rolling_volatility(
    wide_returns: "pd.DataFrame",
    window: int,
    *,
    annualization_factor: float = 252.0,
) -> "pd.DataFrame":
    """Rolling std of returns, annualized (sqrt factor scaling)."""
    if pd is None:
        raise RuntimeError("pandas required")
    rolling = wide_returns.rolling(window=window, min_periods=max(5, window // 4)).std()
    return rolling * (annualization_factor**0.5)


def compute_realized_volatility(
    wide_returns: "pd.DataFrame",
    window: int,
    *,
    annualization_factor: float = 252.0,
) -> "pd.DataFrame":
    """Alias for rolling volatility of returns (interpretable name for research docs)."""
    return compute_rolling_volatility(
        wide_returns, window, annualization_factor=annualization_factor
    )


def rolling_sharpe_ratio(
    wide_returns: "pd.DataFrame",
    window: int,
    *,
    annualization_factor: float = 252.0,
    risk_free_daily: float = 0.0,
) -> "pd.DataFrame":
    """Rolling Sharpe: sqrt(annualization) * mean(excess) / std(excess) per column."""
    if pd is None:
        raise RuntimeError("pandas required")
    min_periods = max(5, window // 4)
    excess = wide_returns - risk_free_daily
    mean_roll = excess.rolling(window=window, min_periods=min_periods).mean()
    std_roll = excess.rolling(window=window, min_periods=min_periods).std()
    sharpe = mean_roll / std_roll.replace(0.0, float("nan"))
    return sharpe * (annualization_factor**0.5)


def compute_rolling_drawdown(
    wide_prices: "pd.DataFrame",
    window: int,
) -> "pd.DataFrame":
    """Rolling max drawdown over ``window`` rows (price input, not returns)."""
    if pd is None:
        raise RuntimeError("pandas required")

    def max_drawdown(series: "pd.Series") -> float:
        cumulative_max = series.cummax()
        drawdown = series / cumulative_max - 1.0
        return float(drawdown.min())

    return wide_prices.rolling(window=window, min_periods=max(5, window // 4)).apply(
        max_drawdown, raw=False
    )


def compute_cross_sectional_summary(
    wide_returns: "pd.DataFrame",
    *,
    date: Optional[str] = None,
) -> Dict[str, Any]:
    """Mean, std, min, max across symbols for one date (last row if ``date`` None)."""
    if pd is None:
        raise RuntimeError("pandas required")
    row = wide_returns.loc[date] if date is not None else wide_returns.iloc[-1]
    values = row.dropna().astype(float)
    return {
        "date": str(values.name),
        "symbol_count": int(values.shape[0]),
        "mean": float(values.mean()),
        "std": float(values.std()),
        "min": float(values.min()),
        "max": float(values.max()),
    }
