#!/usr/bin/env python3
"""Deep validation of local research resources with structured JSON output.

Run from ``jk/``::

    PYTHONPATH=src python3 scripts/validate_local_resources.py

Writes ``outputs/manifests/local_resources.json`` and prints a summary.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def _probe_kdb() -> dict:
    from qhpc_cache.taq_kdb_adapter import default_kdb_taq_repo, kdb_backend_ready, inspect_kdb_taq_repo
    ready, msg = kdb_backend_ready()
    info = inspect_kdb_taq_repo()
    return {
        "ready": ready,
        "message": msg,
        "repo_root": info["repo_root"],
        "exists": info["exists"],
        "q_available": info["q_available"],
        "q_file_count": info["q_file_count"],
    }


def _probe_backends() -> list:
    from qhpc_cache.backends.cpu_local import CpuLocalBackend
    from qhpc_cache.backends.cuda_placeholder import CudaPlaceholderBackend
    from qhpc_cache.backends.mpi_placeholder import MpiPlaceholderBackend
    from qhpc_cache.backends.slurm_bigred200 import SlurmBigRed200Backend
    results = []
    for cls in [CpuLocalBackend, CudaPlaceholderBackend, MpiPlaceholderBackend, SlurmBigRed200Backend]:
        b = cls()
        cap = b.capabilities()
        results.append({**cap.__dict__, "validates": b.validate()})
    return results


def main() -> None:
    from qhpc_cache.data_sources import DatabentoProvider

    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "databento_api_key": DatabentoProvider.api_key_present(),
        "kdb_taq": _probe_kdb(),
        "pixel_agents_path": str(Path(os.environ.get("QHPC_PIXEL_AGENTS_REPO", "/Users/prady/Desktop/pixel-agents"))),
        "pixel_agents_exists": Path(os.environ.get("QHPC_PIXEL_AGENTS_REPO", "/Users/prady/Desktop/pixel-agents")).is_dir(),
        "backends": _probe_backends(),
        "python_packages": {},
    }

    for pkg in ["numpy", "pandas", "matplotlib", "seaborn", "pyarrow", "databento", "langchain_core", "langgraph"]:
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", "installed")
            report["python_packages"][pkg] = {"available": True, "version": str(ver)}
        except ImportError:
            report["python_packages"][pkg] = {"available": False}

    out_dir = Path(os.environ.get("QHPC_OUTPUT_ROOT", "outputs")) / "manifests"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "local_resources.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("Local Resource Validation")
    print("=" * 50)
    print(f"  Databento API key: {'present' if report['databento_api_key'] else 'missing'}")
    print(f"  kdb-taq ready: {report['kdb_taq']['ready']}")
    print(f"  Pixel Agents: {'found' if report['pixel_agents_exists'] else 'not found'}")
    for b in report["backends"]:
        print(f"  Backend {b['name']}: {'ready' if b['can_execute'] else 'scaffold'}")
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
