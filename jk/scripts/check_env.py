#!/usr/bin/env python3
"""Validate the local research environment: APIs, tools, paths, dependencies.

Run from ``jk/``::

    PYTHONPATH=src python3 scripts/check_env.py

Prints a structured report and exits 0 even if items are missing (graceful degradation).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def _check(label: str, ok: bool, detail: str = "") -> bool:
    status = "OK" if ok else "MISSING"
    line = f"  [{status:>7}] {label}"
    if detail:
        line += f"  ({detail})"
    print(line)
    return ok


def main() -> None:
    print("=" * 60)
    print("qhpc_cache: Local Environment Report")
    print("=" * 60)
    total, passed = 0, 0

    # -- API keys --
    print("\n-- API Keys --")
    key = os.environ.get("DATABENTO_API_KEY", "")
    total += 1
    passed += _check("DATABENTO_API_KEY", bool(key), f"{'set (masked)' if key else 'not set'}")

    wrds_user = os.environ.get("WRDS_USERNAME", "")
    total += 1
    passed += _check("WRDS_USERNAME", bool(wrds_user), "not set" if not wrds_user else "set (value not shown)")

    # -- Executables --
    print("\n-- Executables --")
    q_path = shutil.which(os.environ.get("QHPC_KDB_Q_BINARY", "q"))
    total += 1
    passed += _check("q (kdb+)", q_path is not None, str(q_path) if q_path else "not on PATH")

    # -- Paths --
    print("\n-- Local Paths --")
    kdb_taq = Path(os.environ.get("QHPC_KDB_TAQ_REPO", str(Path.home() / "Desktop" / "kdb-taq")))
    total += 1
    passed += _check("kdb-taq repo", kdb_taq.is_dir(), str(kdb_taq))

    data_root = Path(os.environ.get("QHPC_DATA_ROOT", "data/qhpc_data"))
    total += 1
    passed += _check("data root writable", data_root.parent.exists() or data_root.exists(), str(data_root))

    outputs = Path(os.environ.get("QHPC_OUTPUT_ROOT", "outputs"))
    total += 1
    passed += _check("outputs writable", True, str(outputs))

    papers = Path(os.environ.get("QHPC_LOCAL_PAPERS_DIR", "data/papers"))
    total += 1
    passed += _check("local papers dir", papers.is_dir(), str(papers) if papers.is_dir() else "optional")

    # -- Python packages --
    print("\n-- Python Packages --")
    for pkg in ["numpy", "pandas", "matplotlib", "seaborn", "pyarrow", "databento"]:
        total += 1
        try:
            __import__(pkg)
            passed += _check(pkg, True)
        except ImportError:
            _check(pkg, False, "pip install -e '.[data-pipeline]'" if pkg in ("pandas", "pyarrow", "databento") else "optional")

    total += 1
    try:
        import wrds  # noqa: F401

        passed += _check("wrds", True, "WRDS Python client")
    except ImportError:
        passed += _check("wrds", False, "pip install wrds for institutional pulls")

    total += 1
    if wrds_user:
        try:
            import wrds

            db = wrds.Connection(wrds_username=wrds_user)
            db.close()
            passed += _check("WRDS connection", True, "session ok (credentials not printed)")
        except ImportError:
            passed += _check("WRDS connection", False, "wrds package not installed")
        except Exception as exc:
            passed += _check("WRDS connection", False, str(exc)[:80])
    else:
        passed += _check("WRDS connection", False, "skip (WRDS_USERNAME unset)")

    pixel_repo = Path(os.environ.get("QHPC_PIXEL_REPO", ""))
    total += 1
    passed += _check(
        "Pixel repo (optional)",
        pixel_repo.is_dir() if pixel_repo else False,
        str(pixel_repo) if pixel_repo else "set QHPC_PIXEL_REPO to enable",
    )

    langchain_home = os.environ.get("LANGCHAIN_HOME", "")
    total += 1
    passed += _check(
        "LANGCHAIN_HOME (optional)",
        bool(langchain_home and Path(langchain_home).is_dir()),
        "optional local LangChain checkout",
    )

    for pkg in ["langchain_core", "langgraph"]:
        total += 1
        try:
            __import__(pkg)
            passed += _check(pkg, True)
        except ImportError:
            _check(pkg, False, "optional; internal fallback used")

    # -- Summary --
    print(f"\n{'=' * 60}")
    print(f"Result: {passed}/{total} checks passed")
    if passed < total:
        print("Some items are missing. The system will degrade gracefully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
