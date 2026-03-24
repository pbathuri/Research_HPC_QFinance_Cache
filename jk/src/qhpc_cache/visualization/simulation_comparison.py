"""Simulation vs historical comparison: distribution overlay, QQ, tail diagnostic."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import matplotlib.pyplot as plt
import numpy as np

from qhpc_cache.visualization.plot_utils import HAS_SEABORN, save_figure

if HAS_SEABORN:
    import seaborn as sns


def plot_distribution_comparison(
    historical_returns: "Any",
    simulated_returns: "Any",
    *,
    title: str = "Historical vs Simulated Returns",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Overlaid histogram / KDE of historical and simulated return distributions."""
    hist_arr = np.asarray(historical_returns).ravel()
    sim_arr = np.asarray(simulated_returns).ravel()
    hist_arr = hist_arr[np.isfinite(hist_arr)]
    sim_arr = sim_arr[np.isfinite(sim_arr)]

    fig, ax = plt.subplots(figsize=(10, 6))
    if HAS_SEABORN:
        sns.kdeplot(hist_arr, ax=ax, label="Historical", color="#2176AE", fill=True, alpha=0.3)
        sns.kdeplot(sim_arr, ax=ax, label="Simulated (MC)", color="#D64045", fill=True, alpha=0.3)
    else:
        ax.hist(hist_arr, bins=60, density=True, alpha=0.5, color="#2176AE", label="Historical")
        ax.hist(sim_arr, bins=60, density=True, alpha=0.5, color="#D64045", label="Simulated (MC)")
    ax.set_title(title, fontsize=13)
    ax.set_xlabel("Return")
    ax.set_ylabel("Density")
    ax.legend()

    if output_path is not None:
        return save_figure(fig, output_path)
    plt.close(fig)
    return {"status": "ok", "path": None}


def plot_qq_comparison(
    historical_returns: "Any",
    simulated_returns: "Any",
    *,
    title: str = "QQ: Historical vs Simulated",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Quantile-quantile plot of historical vs simulated returns."""
    hist_arr = np.sort(np.asarray(historical_returns).ravel())
    sim_arr = np.sort(np.asarray(simulated_returns).ravel())
    hist_arr = hist_arr[np.isfinite(hist_arr)]
    sim_arr = sim_arr[np.isfinite(sim_arr)]

    n_points = min(len(hist_arr), len(sim_arr), 500)
    if n_points < 5:
        return {"status": "insufficient_data", "path": None}
    q_levels = np.linspace(0, 1, n_points)
    hist_q = np.quantile(hist_arr, q_levels)
    sim_q = np.quantile(sim_arr, q_levels)

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(hist_q, sim_q, s=8, alpha=0.6, color="#4A90D9")
    bounds = [min(hist_q.min(), sim_q.min()), max(hist_q.max(), sim_q.max())]
    ax.plot(bounds, bounds, "k--", linewidth=0.8, label="45-degree line")
    ax.set_xlabel("Historical quantiles")
    ax.set_ylabel("Simulated quantiles")
    ax.set_title(title, fontsize=13)
    ax.legend()

    if output_path is not None:
        return save_figure(fig, output_path)
    plt.close(fig)
    return {"status": "ok", "path": None}


def plot_tail_comparison(
    historical_returns: "Any",
    simulated_returns: "Any",
    *,
    tail_pct: float = 5.0,
    title: str = "Left Tail Comparison (Worst 5%)",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Focus on the left tail of both distributions."""
    hist_arr = np.sort(np.asarray(historical_returns).ravel())
    sim_arr = np.sort(np.asarray(simulated_returns).ravel())
    hist_arr = hist_arr[np.isfinite(hist_arr)]
    sim_arr = sim_arr[np.isfinite(sim_arr)]

    cutoff_h = int(len(hist_arr) * tail_pct / 100.0)
    cutoff_s = int(len(sim_arr) * tail_pct / 100.0)
    if cutoff_h < 3 or cutoff_s < 3:
        return {"status": "insufficient_tail_data", "path": None}

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(hist_arr[:cutoff_h], bins=30, density=True, alpha=0.6, color="#2176AE", label="Historical tail")
    ax.hist(sim_arr[:cutoff_s], bins=30, density=True, alpha=0.6, color="#D64045", label="Simulated tail")
    ax.set_title(title, fontsize=13)
    ax.set_xlabel("Return (left tail)")
    ax.set_ylabel("Density")
    ax.legend()

    if output_path is not None:
        return save_figure(fig, output_path)
    plt.close(fig)
    return {"status": "ok", "path": None}
