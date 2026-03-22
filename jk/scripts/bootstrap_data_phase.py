#!/usr/bin/env python3
"""Create data root, registry, and standard subdirectories; print status."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from qhpc_cache.data_registry import initialize_dataset_registry, load_checkpoints  # noqa: E402


def main() -> int:
    data_root = os.environ.get("QHPC_DATA_ROOT", str(ROOT / "data" / "qhpc_data"))
    root_path = Path(data_root)
    for sub in (
        root_path / "daily_universe",
        root_path / "event_book",
        root_path / "rates",
        root_path / "taq_incoming",
        root_path / "registry",
    ):
        sub.mkdir(parents=True, exist_ok=True)
    initialize_dataset_registry(str(root_path))
    checkpoints = load_checkpoints(str(root_path))
    print("qhpc data phase bootstrap")
    print(f"  QHPC_DATA_ROOT = {root_path.resolve()}")
    print(f"  registry checkpoints initialized: {len(checkpoints)} keys")
    print("Next: export DATABENTO_API_KEY and/or place TAQ files under taq_incoming (or set QHPC_TAQ_ROOT).")
    print("See docs/data_source_setup.md and docs/manual_setup_steps.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
