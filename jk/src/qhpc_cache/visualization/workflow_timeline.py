"""Agent workflow timeline: Gantt-style chart of stage execution with bot labels."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from qhpc_cache.visualization.plot_utils import save_figure

_AGENT_COLORS = {
    "EnvironmentAgent": "#2E86AB",
    "DataIngestionAgent": "#A23B72",
    "CacheResearchAgent": "#F18F01",
    "LiteratureReviewAgent": "#C73E1D",
    "ExperimentAgent": "#3B1F2B",
    "VisualizationAgent": "#44BBA4",
    "ReportAgent": "#E94F37",
    "QuantumPlanningAgent": "#6A0572",
    "RiskMetricsAgent": "#1B998B",
    "EventBookAgent": "#FF6B6B",
}

_BOT_NAMES = {
    "EnvironmentAgent": "EnvBot",
    "DataIngestionAgent": "DataBot",
    "CacheResearchAgent": "CacheBot",
    "LiteratureReviewAgent": "LitBot",
    "ExperimentAgent": "ExpBot",
    "VisualizationAgent": "VizBot",
    "ReportAgent": "ReportBot",
    "QuantumPlanningAgent": "QuantumBot",
    "RiskMetricsAgent": "RiskBot",
    "EventBookAgent": "EventBot",
}


def plot_agent_timeline(
    agent_records: Sequence[Dict[str, Any]],
    *,
    title: str = "Research Pipeline: Agent Workflow Timeline",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Horizontal Gantt chart of agent execution.

    Each record should have: agent_name, task_id, duration_seconds, status.
    """
    if not agent_records:
        return {"status": "no_data", "path": None}

    fig, ax = plt.subplots(figsize=(14, max(4, len(agent_records) * 0.6)))

    y_labels = []
    start_offset = 0.0
    for i, rec in enumerate(agent_records):
        agent = rec.get("agent_name", "unknown")
        task = rec.get("task_id", "task")
        dur = float(rec.get("duration_seconds", 0.1))
        status = rec.get("status", "ok")
        color = _AGENT_COLORS.get(agent, "#888888")
        bot = _BOT_NAMES.get(agent, agent)

        if status == "error":
            color = "#CC0000"
            hatch = "///"
        else:
            hatch = ""

        ax.barh(i, dur, left=start_offset, height=0.6, color=color, alpha=0.85,
                edgecolor="white", linewidth=0.5, hatch=hatch)
        ax.text(start_offset + dur / 2, i, f"{bot}: {dur:.2f}s",
                ha="center", va="center", fontsize=8, color="white", fontweight="bold")
        y_labels.append(f"{task}")
        start_offset += dur

    ax.set_yticks(range(len(y_labels)))
    ax.set_yticklabels(y_labels, fontsize=9)
    ax.set_xlabel("Cumulative time (seconds)")
    ax.set_title(title, fontsize=13)
    ax.invert_yaxis()

    if output_path:
        return save_figure(fig, output_path)
    plt.close(fig)
    return {"status": "ok", "path": None}


def plot_backend_readiness_matrix(
    backends: Sequence[Dict[str, Any]],
    *,
    title: str = "Backend Readiness Matrix",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Grid showing which backends can execute, have GPU, MPI, etc."""
    if not backends:
        return {"status": "no_data", "path": None}

    names = [b["name"] for b in backends]
    flags = ["can_execute", "supports_gpu", "supports_mpi", "supports_batch_scheduler"]
    matrix = np.array([[1 if b.get(f, False) else 0 for f in flags] for b in backends])

    fig, ax = plt.subplots(figsize=(8, max(3, len(names) * 0.7)))
    colors = np.where(matrix == 1, 0.3, 0.9)
    ax.imshow(colors, cmap="RdYlGn_r", aspect="auto", vmin=0, vmax=1)

    for i in range(len(names)):
        for j in range(len(flags)):
            label = "Ready" if matrix[i, j] else "Pending"
            color = "#1a6b1a" if matrix[i, j] else "#aa3333"
            ax.text(j, i, label, ha="center", va="center", fontsize=9, color=color, fontweight="bold")

    ax.set_xticks(range(len(flags)))
    ax.set_xticklabels([f.replace("_", "\n") for f in flags], fontsize=9)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=10)
    ax.set_title(title, fontsize=13)

    if output_path:
        return save_figure(fig, output_path)
    plt.close(fig)
    return {"status": "ok", "path": None}
