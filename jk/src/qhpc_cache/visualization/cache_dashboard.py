"""Cache research dashboards: hit/miss/reuse plots, policy comparison, locality heatmaps."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import matplotlib.pyplot as plt
import numpy as np

from qhpc_cache.visualization.plot_utils import HAS_SEABORN, save_figure

if HAS_SEABORN:
    import seaborn as sns


def plot_hit_miss_breakdown(
    summaries: Sequence[Dict[str, Any]],
    *,
    title: str = "Cache Hit / Miss Breakdown by Policy",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Stacked bar chart of exact hits, similarity hits, and misses per policy."""
    names = [s["policy_name"] for s in summaries]
    exact = [s.get("exact_hits", 0) for s in summaries]
    sim = [s.get("similarity_hits", 0) for s in summaries]
    misses = [s.get("misses", 0) for s in summaries]

    x = np.arange(len(names))
    width = 0.5
    fig, ax = plt.subplots(figsize=(max(6, len(names) * 2), 5))
    ax.bar(x, exact, width, label="Exact hits", color="#2E86AB")
    ax.bar(x, sim, width, bottom=exact, label="Similarity hits", color="#A23B72")
    ax.bar(x, misses, width, bottom=[e + s for e, s in zip(exact, sim)], label="Misses", color="#F18F01")
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=9)
    ax.set_ylabel("Count")
    ax.set_title(title, fontsize=13)
    ax.legend()

    if output_path:
        return save_figure(fig, output_path)
    plt.close(fig)
    return {"status": "ok", "path": None}


def plot_cache_efficiency_comparison(
    summaries: Sequence[Dict[str, Any]],
    *,
    title: str = "Cache Efficiency & Locality Score",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Grouped bar chart comparing efficiency and locality across policies."""
    names = [s["policy_name"] for s in summaries]
    efficiency = [s.get("cache_efficiency", 0) for s in summaries]
    locality = [s.get("locality_score", 0) for s in summaries]

    x = np.arange(len(names))
    width = 0.35
    fig, ax = plt.subplots(figsize=(max(6, len(names) * 2), 5))
    ax.bar(x - width / 2, efficiency, width, label="Cache Efficiency", color="#2E86AB")
    ax.bar(x + width / 2, locality, width, label="Locality Score", color="#A23B72")
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=9)
    ax.set_ylabel("Score (0-1)")
    ax.set_ylim(0, 1.05)
    ax.set_title(title, fontsize=13)
    ax.legend()

    if output_path:
        return save_figure(fig, output_path)
    plt.close(fig)
    return {"status": "ok", "path": None}


def plot_reuse_distance_histogram(
    reuse_distances: Sequence[int],
    *,
    policy_name: str = "",
    title: str = "Reuse Distance Distribution",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Histogram of reuse distances (lower = higher temporal locality)."""
    arr = np.array(reuse_distances)
    fig, ax = plt.subplots(figsize=(8, 5))
    if HAS_SEABORN:
        sns.histplot(arr, kde=True, ax=ax, color="#2E86AB", bins=30)
    else:
        ax.hist(arr, bins=30, color="#2E86AB", alpha=0.7, edgecolor="white")
    full_title = f"{title} ({policy_name})" if policy_name else title
    ax.set_title(full_title, fontsize=13)
    ax.set_xlabel("Reuse distance (distinct keys between repeat accesses)")
    ax.set_ylabel("Frequency")

    if output_path:
        return save_figure(fig, output_path)
    plt.close(fig)
    return {"status": "ok", "path": None}
