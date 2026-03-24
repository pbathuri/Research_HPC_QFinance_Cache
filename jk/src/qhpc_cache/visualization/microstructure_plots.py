"""Microstructure diagnostics: intraday spread, volume profile, event-window response."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np

from qhpc_cache.visualization.plot_utils import save_figure


def plot_intraday_spread(
    timestamps: "Any",
    spread_values: "Any",
    *,
    title: str = "Intraday Spread Proxy",
    ylabel: str = "Spread",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Spread (or spread proxy) over intraday timestamps."""
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(timestamps, spread_values, linewidth=0.6, color="#2176AE", alpha=0.8)
    ax.set_title(title, fontsize=13)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Time")
    if output_path is not None:
        return save_figure(fig, output_path)
    plt.close(fig)
    return {"status": "ok", "path": None}


def plot_intraday_volume_profile(
    timestamps: "Any",
    volume_values: "Any",
    *,
    title: str = "Intraday Volume / Message Intensity",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Bar or step plot of intraday volume bins."""
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.fill_between(range(len(volume_values)), volume_values, alpha=0.5, color="#57B8FF")
    ax.plot(volume_values, linewidth=0.7, color="#2176AE")
    ax.set_title(title, fontsize=13)
    ax.set_ylabel("Volume / count")
    ax.set_xlabel("Bin index")
    if output_path is not None:
        return save_figure(fig, output_path)
    plt.close(fig)
    return {"status": "ok", "path": None}


def plot_event_window_response(
    timestamps: "Any",
    price_series: "Any",
    volume_series: "Any",
    *,
    event_label: str = "Event Window",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Dual-axis plot: price and volume during an event window."""
    fig, ax1 = plt.subplots(figsize=(12, 5))
    color_price = "#333333"
    ax1.plot(timestamps, price_series, linewidth=1.0, color=color_price, label="Price")
    ax1.set_ylabel("Price", color=color_price)
    ax1.set_xlabel("Time")
    ax1.set_title(f"{event_label}: Price & Volume", fontsize=13)

    ax2 = ax1.twinx()
    color_vol = "#57B8FF"
    ax2.fill_between(range(len(volume_series)), volume_series, alpha=0.3, color=color_vol)
    ax2.set_ylabel("Volume", color=color_vol)

    if output_path is not None:
        return save_figure(fig, output_path)
    plt.close(fig)
    return {"status": "ok", "path": None}
