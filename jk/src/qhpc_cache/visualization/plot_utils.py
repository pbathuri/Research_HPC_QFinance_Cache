"""Shared plotting helpers: figure creation, save, style, optional seaborn guard."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    sns = None  # type: ignore
    HAS_SEABORN = False


def apply_research_style() -> None:
    """Set a clean matplotlib style for research figures."""
    plt.rcParams.update({
        "figure.figsize": (10, 6),
        "axes.grid": True,
        "grid.alpha": 0.3,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "font.size": 11,
    })
    if HAS_SEABORN:
        sns.set_theme(style="whitegrid", font_scale=1.05)


def save_figure(
    fig: plt.Figure,
    output_path: Path,
    *,
    dpi: int = 150,
    close: bool = True,
) -> Dict[str, Any]:
    """Save figure to disk and return metadata dict."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight")
    meta = {
        "path": str(output_path),
        "filename": output_path.name,
        "dpi": dpi,
        "status": "ok",
    }
    if close:
        plt.close(fig)
    return meta


def ensure_output_dirs(base: Path) -> Dict[str, Path]:
    """Create the standard output directory tree and return path map."""
    dirs = {
        "root": base,
        "market": base / "figures" / "market",
        "microstructure": base / "figures" / "microstructure",
        "alpha": base / "figures" / "alpha",
        "simulation": base / "figures" / "simulation",
        # Optional non-matplotlib artifacts (legacy Pixel traces, etc.); not spine-critical.
        "optional_traces": base / "optional_traces",
        "summaries": base / "summaries",
    }
    for directory in dirs.values():
        directory.mkdir(parents=True, exist_ok=True)
    return dirs
