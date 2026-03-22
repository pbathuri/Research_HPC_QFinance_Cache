"""Interpretable cross-sectional / time-series alpha-style features (research, not production)."""

from __future__ import annotations

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None  # type: ignore


def price_momentum_feature(
    price_frame: "pd.DataFrame",
    *,
    lookback: int = 21,
    close_column: str = "close",
    symbol_column: str = "symbol",
    date_column: str = "date",
) -> "pd.DataFrame":
    """Cumulative simple return over ``lookback`` days per symbol."""
    if pd is None:
        raise RuntimeError("pandas required")
    frame = price_frame.sort_values([symbol_column, date_column]).copy()
    frame["momentum"] = frame.groupby(symbol_column)[close_column].pct_change(lookback)
    return frame


def moving_average_spread_feature(
    price_frame: "pd.DataFrame",
    *,
    fast_window: int = 10,
    slow_window: int = 50,
    close_column: str = "close",
    symbol_column: str = "symbol",
    date_column: str = "date",
) -> "pd.DataFrame":
    """Fast minus slow simple moving average of close (levels, not normalized)."""
    if pd is None:
        raise RuntimeError("pandas required")
    frame = price_frame.sort_values([symbol_column, date_column]).copy()
    grouped = frame.groupby(symbol_column, group_keys=False)[close_column]
    fast_ma = grouped.transform(lambda s: s.rolling(fast_window, min_periods=3).mean())
    slow_ma = grouped.transform(lambda s: s.rolling(slow_window, min_periods=5).mean())
    frame["ma_spread"] = fast_ma - slow_ma
    return frame


def rolling_z_score_feature(
    series_frame: "pd.DataFrame",
    *,
    value_column: str,
    window: int = 60,
    symbol_column: str = "symbol",
    date_column: str = "date",
    output_column: str = "z_score",
) -> "pd.DataFrame":
    """Rolling z-score of ``value_column`` within each symbol."""
    if pd is None:
        raise RuntimeError("pandas required")
    frame = series_frame.sort_values([symbol_column, date_column]).copy()

    def zscore(group: "pd.Series") -> "pd.Series":
        roll_mean = group.rolling(window, min_periods=max(5, window // 5)).mean()
        roll_std = group.rolling(window, min_periods=max(5, window // 5)).std()
        return (group - roll_mean) / roll_std.replace(0.0, float("nan"))

    frame[output_column] = frame.groupby(symbol_column, group_keys=False)[value_column].transform(
        zscore
    )
    return frame


def rolling_volume_change_feature(
    price_frame: "pd.DataFrame",
    *,
    volume_column: str = "volume",
    lag: int = 5,
    symbol_column: str = "symbol",
    date_column: str = "date",
) -> "pd.DataFrame":
    """Percent change in volume over ``lag`` days."""
    if pd is None:
        raise RuntimeError("pandas required")
    if volume_column not in price_frame.columns:
        raise KeyError(f"missing {volume_column}")
    frame = price_frame.sort_values([symbol_column, date_column]).copy()
    frame["volume_change"] = frame.groupby(symbol_column)[volume_column].pct_change(lag)
    return frame


def realized_volatility_feature(
    wide_returns: "pd.DataFrame",
    *,
    window: int = 21,
    annualization_factor: float = 252.0,
) -> "pd.DataFrame":
    """Rolling realized vol (annualized) from wide return panel."""
    if pd is None:
        raise RuntimeError("pandas required")
    from qhpc_cache.historical_returns import compute_realized_volatility

    return compute_realized_volatility(
        wide_returns, window, annualization_factor=annualization_factor
    )


def downside_volatility_feature(
    wide_returns: "pd.DataFrame",
    *,
    window: int = 21,
    annualization_factor: float = 252.0,
) -> "pd.DataFrame":
    """Rolling std of negative returns only (annualized), per column."""
    if pd is None:
        raise RuntimeError("pandas required")
    neg = wide_returns.where(wide_returns < 0.0)
    rolling = neg.rolling(window=window, min_periods=max(5, window // 4)).std()
    return rolling * (annualization_factor**0.5)


def simple_mean_reversion_feature(
    price_frame: "pd.DataFrame",
    *,
    lookback: int = 21,
    close_column: str = "close",
    symbol_column: str = "symbol",
    date_column: str = "date",
) -> "pd.DataFrame":
    """Negative of short-horizon return (coarse mean-reversion tilt)."""
    if pd is None:
        raise RuntimeError("pandas required")
    mom = price_momentum_feature(
        price_frame,
        lookback=lookback,
        close_column=close_column,
        symbol_column=symbol_column,
        date_column=date_column,
    )
    mom["mean_reversion"] = -mom["momentum"]
    return mom.drop(columns=["momentum"], errors="ignore")
