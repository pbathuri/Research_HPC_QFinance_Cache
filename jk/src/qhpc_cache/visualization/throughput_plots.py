"""Throughput and runtime metric plots from CSV logs."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np

from qhpc_cache.visualization.plot_utils import HAS_SEABORN, save_figure

if HAS_SEABORN:
    import seaborn as sns


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def plot_stage_durations(
    metrics_csv: Path,
    *,
    title: str = "Stage Durations",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Bar chart of per-stage wall-clock durations from runtime_metrics.csv."""
    rows = _read_csv_rows(metrics_csv)
    if not rows:
        return {"status": "no_data", "path": None}

    stages = [r.get("stage", "?") for r in rows]
    durations = [float(r.get("duration_seconds", 0)) for r in rows]

    fig, ax = plt.subplots(figsize=(max(6, len(stages) * 1.2), 5))
    colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(stages)))
    ax.barh(range(len(stages)), durations, color=colors, edgecolor="white")
    ax.set_yticks(range(len(stages)))
    ax.set_yticklabels(stages, fontsize=9)
    ax.set_xlabel("Duration (seconds)")
    ax.set_title(title, fontsize=13)
    ax.invert_yaxis()

    if output_path:
        return save_figure(fig, output_path)
    plt.close(fig)
    return {"status": "ok", "path": None}


def plot_cache_metrics_over_runs(
    metrics_csv: Path,
    *,
    title: str = "Cache Metrics Across Runs",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Line plot of hit rate and efficiency across runs from cache_metrics.csv."""
    rows = _read_csv_rows(metrics_csv)
    if not rows:
        return {"status": "no_data", "path": None}

    run_ids = [r.get("run_id", str(i)) for i, r in enumerate(rows)]
    exact = [int(r.get("exact_hits", 0)) for r in rows]
    misses = [int(r.get("misses", 0)) for r in rows]
    efficiency = [float(r.get("cache_efficiency", 0)) for r in rows]
    hit_rates = [e / max(1, e + m) for e, m in zip(exact, misses)]

    fig, ax1 = plt.subplots(figsize=(10, 5))
    x = range(len(run_ids))
    ax1.bar(x, hit_rates, alpha=0.5, color="#2E86AB", label="Hit Rate")
    ax1.set_ylabel("Hit Rate", color="#2E86AB")
    ax1.set_ylim(0, 1.05)

    ax2 = ax1.twinx()
    ax2.plot(x, efficiency, "o-", color="#F18F01", label="Efficiency", linewidth=1.5)
    ax2.set_ylabel("Efficiency", color="#F18F01")
    ax2.set_ylim(0, 1.05)

    ax1.set_xticks(list(x))
    ax1.set_xticklabels(run_ids, rotation=45, ha="right", fontsize=7)
    ax1.set_title(title, fontsize=13)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    if output_path:
        return save_figure(fig, output_path)
    plt.close(fig)
    return {"status": "ok", "path": None}
