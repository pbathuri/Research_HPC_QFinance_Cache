"""Market overview plots: cumulative returns, rolling volatility, correlation heatmap."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np

from qhpc_cache.visualization.plot_utils import HAS_SEABORN, save_figure

if HAS_SEABORN:
    import seaborn as sns


def plot_cumulative_returns(
    wide_returns: "np.ndarray | Any",
    *,
    columns: Optional[List[str]] = None,
    index: Optional[List[str]] = None,
    title: str = "Cumulative Returns",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Line plot of cumulative log returns per symbol."""
    try:
        import pandas as pd
        if isinstance(wide_returns, pd.DataFrame):
            cumulative = wide_returns.cumsum()
        else:
            cumulative = np.cumsum(wide_returns, axis=0)
            cumulative = pd.DataFrame(cumulative, columns=columns, index=index)
    except ImportError:
        cumulative = np.cumsum(np.asarray(wide_returns), axis=0)

    fig, ax = plt.subplots(figsize=(12, 6))
    if hasattr(cumulative, "plot"):
        cumulative.plot(ax=ax, linewidth=0.9, alpha=0.85)
    else:
        ax.plot(cumulative, linewidth=0.9, alpha=0.85)
    ax.set_title(title, fontsize=13)
    ax.set_ylabel("Cumulative log return")
    ax.set_xlabel("Date")
    ax.legend(fontsize=8, ncol=3, loc="upper left")

    if output_path is not None:
        return save_figure(fig, output_path)
    plt.close(fig)
    return {"status": "ok", "path": None}


def plot_rolling_volatility(
    rolling_vol: "Any",
    *,
    title: str = "21-Day Rolling Annualized Volatility",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Line plot of rolling volatility per symbol."""
    fig, ax = plt.subplots(figsize=(12, 6))
    if hasattr(rolling_vol, "plot"):
        rolling_vol.plot(ax=ax, linewidth=0.8, alpha=0.8)
    else:
        ax.plot(rolling_vol, linewidth=0.8, alpha=0.8)
    ax.set_title(title, fontsize=13)
    ax.set_ylabel("Annualized volatility")
    ax.set_xlabel("Date")
    ax.legend(fontsize=8, ncol=3, loc="upper left")

    if output_path is not None:
        return save_figure(fig, output_path)
    plt.close(fig)
    return {"status": "ok", "path": None}


def plot_correlation_heatmap(
    wide_returns: "Any",
    *,
    title: str = "Return Correlation Matrix",
    max_symbols: int = 20,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Heatmap of pairwise return correlations."""
    import pandas as pd

    if isinstance(wide_returns, pd.DataFrame):
        cols = list(wide_returns.columns[:max_symbols])
        corr = wide_returns[cols].corr()
    else:
        arr = np.asarray(wide_returns)[:, :max_symbols]
        corr = np.corrcoef(arr.T)

    fig, ax = plt.subplots(figsize=(10, 8))
    if HAS_SEABORN and isinstance(corr, pd.DataFrame):
        sns.heatmap(corr, annot=len(corr) <= 12, fmt=".2f", cmap="RdBu_r",
                    center=0, vmin=-1, vmax=1, ax=ax, square=True)
    else:
        im = ax.imshow(np.asarray(corr), cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
        fig.colorbar(im, ax=ax)
        if hasattr(corr, "columns"):
            ax.set_xticks(range(len(corr.columns)))
            ax.set_xticklabels(corr.columns, rotation=45, ha="right", fontsize=7)
            ax.set_yticks(range(len(corr.columns)))
            ax.set_yticklabels(corr.columns, fontsize=7)
    ax.set_title(title, fontsize=13)

    if output_path is not None:
        return save_figure(fig, output_path)
    plt.close(fig)
    return {"status": "ok", "path": None}
