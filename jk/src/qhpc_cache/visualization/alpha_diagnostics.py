"""Alpha / feature diagnostics: distributions, correlation, signal vs forward return."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np

from qhpc_cache.visualization.plot_utils import HAS_SEABORN, save_figure

if HAS_SEABORN:
    import seaborn as sns


def plot_feature_distributions(
    feature_frame: "Any",
    *,
    feature_columns: Optional[List[str]] = None,
    title: str = "Feature Distributions",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Histogram panel for each feature column."""
    import pandas as pd

    if feature_columns is None:
        feature_columns = [c for c in feature_frame.columns if feature_frame[c].dtype.kind == "f"]
    n_features = len(feature_columns)
    if n_features == 0:
        return {"status": "no_features", "path": None}

    ncols = min(3, n_features)
    nrows = (n_features + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows), squeeze=False)
    fig.suptitle(title, fontsize=14, y=1.02)

    for idx, col in enumerate(feature_columns):
        row_idx, col_idx = divmod(idx, ncols)
        ax = axes[row_idx][col_idx]
        values = feature_frame[col].dropna().values
        if HAS_SEABORN:
            sns.histplot(values, kde=True, ax=ax, color="#4A90D9", bins=40)
        else:
            ax.hist(values, bins=40, color="#4A90D9", alpha=0.7, edgecolor="white")
        ax.set_title(col, fontsize=10)
        ax.set_xlabel("")

    for idx in range(n_features, nrows * ncols):
        row_idx, col_idx = divmod(idx, ncols)
        axes[row_idx][col_idx].set_visible(False)
    fig.tight_layout()

    if output_path is not None:
        return save_figure(fig, output_path)
    plt.close(fig)
    return {"status": "ok", "path": None}


def plot_feature_correlation_heatmap(
    feature_frame: "Any",
    *,
    feature_columns: Optional[List[str]] = None,
    title: str = "Feature Correlation",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Heatmap of feature-to-feature correlations."""
    import pandas as pd

    if feature_columns is None:
        feature_columns = [c for c in feature_frame.columns if feature_frame[c].dtype.kind == "f"]
    corr = feature_frame[feature_columns].corr()

    fig, ax = plt.subplots(figsize=(8, 7))
    if HAS_SEABORN:
        sns.heatmap(corr, annot=len(corr) <= 10, fmt=".2f", cmap="coolwarm",
                    center=0, ax=ax, square=True)
    else:
        im = ax.imshow(corr.values, cmap="coolwarm", vmin=-1, vmax=1, aspect="auto")
        fig.colorbar(im, ax=ax)
        ax.set_xticks(range(len(corr.columns)))
        ax.set_xticklabels(corr.columns, rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(len(corr.columns)))
        ax.set_yticklabels(corr.columns, fontsize=8)
    ax.set_title(title, fontsize=13)

    if output_path is not None:
        return save_figure(fig, output_path)
    plt.close(fig)
    return {"status": "ok", "path": None}


def plot_signal_quantile_returns(
    signal_values: "Any",
    forward_returns: "Any",
    *,
    n_quantiles: int = 5,
    signal_name: str = "Signal",
    title: str = "Signal Quantile vs Forward Return",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Bar chart of mean forward return per signal quantile bucket."""
    import pandas as pd

    df = pd.DataFrame({"signal": signal_values, "fwd_ret": forward_returns}).dropna()
    if len(df) < n_quantiles * 2:
        return {"status": "insufficient_data", "path": None}

    df["quantile"] = pd.qcut(df["signal"], q=n_quantiles, labels=False, duplicates="drop")
    grouped = df.groupby("quantile")["fwd_ret"].mean()

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = plt.cm.RdYlGn(np.linspace(0.15, 0.85, len(grouped)))
    ax.bar(grouped.index.astype(str), grouped.values, color=colors, edgecolor="white")
    ax.set_xlabel(f"{signal_name} quantile (0=low)")
    ax.set_ylabel("Mean forward return")
    ax.set_title(title, fontsize=13)
    ax.axhline(0, color="gray", linewidth=0.8, linestyle="--")

    if output_path is not None:
        return save_figure(fig, output_path)
    plt.close(fig)
    return {"status": "ok", "path": None}
