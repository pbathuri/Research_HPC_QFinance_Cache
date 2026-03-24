"""Centralized run-scoped output directory creation.

Every pipeline invocation gets a unique timestamped folder under ``outputs/``.
Format: ``outputs/Output_YYYYMMDD_HHMMSS/``

Collision safety: if the directory already exists (two runs within the same
second), ``_01``, ``_02``, … suffixes are appended.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def create_run_output_root(base: Path | str = "outputs") -> Path:
    """Create and return a unique timestamped run output directory.

    Parameters
    ----------
    base : Path or str
        Parent directory that holds all run folders (default ``outputs/``).

    Returns
    -------
    Path
        Absolute path to the newly-created run directory,
        e.g. ``<base>/Output_20260322_141122/``.
    """
    base = Path(base)
    base.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = base / f"Output_{stamp}"

    if not candidate.exists():
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate.resolve()

    for seq in range(1, 100):
        suffixed = base / f"Output_{stamp}_{seq:02d}"
        if not suffixed.exists():
            suffixed.mkdir(parents=True, exist_ok=True)
            return suffixed.resolve()

    raise RuntimeError(f"Could not create unique run directory under {base}")
