#!/usr/bin/env python3
"""Bootstrap the local workspace: create directories, registry, validate resources.

Run from ``jk/``::

    PYTHONPATH=src python3 scripts/bootstrap_local_workspace.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    print("Bootstrapping qhpc_cache local workspace...")

    data_root = Path(os.environ.get("QHPC_DATA_ROOT", "data/qhpc_data"))
    output_root = Path(os.environ.get("QHPC_OUTPUT_ROOT", "outputs"))

    dirs = [
        data_root,
        data_root / "daily",
        data_root / "events",
        data_root / "rates",
        data_root / "reference",
        output_root / "metrics",
        output_root / "figures",
        output_root / "reports",
        output_root / "research",
        output_root / "research_visualization",
        output_root / "traces",
        output_root / "manifests",
        output_root / "logs",
        Path("data/papers"),
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  [ok] {d}")

    from qhpc_cache.data_registry import initialize_dataset_registry
    initialize_dataset_registry(str(data_root))
    print(f"  [ok] registry initialized at {data_root}")

    env_example = ROOT / ".env.example"
    env_file = ROOT / ".env"
    if not env_file.exists() and env_example.exists():
        import shutil
        shutil.copy2(env_example, env_file)
        print(f"  [ok] copied .env.example -> .env (edit with your keys)")
    elif env_file.exists():
        print(f"  [ok] .env already exists")

    print("\nDone. Run 'PYTHONPATH=src python3 scripts/check_env.py' for full status.")


if __name__ == "__main__":
    main()
