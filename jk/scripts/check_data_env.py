#!/usr/bin/env python3
"""Verify data-phase environment: API keys (masked), kdb-taq, q, TAQ paths, writability."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _count_taq_like_files(root: Path, limit: int = 5000) -> int:
    if not root.is_dir():
        return 0
    count = 0
    keywords = ("taq", "trade", "quote", "nyse", "nbbo")
    try:
        for path in root.rglob("*"):
            if path.is_file():
                lower = str(path).lower()
                if path.suffix.lower() in (".csv", ".txt", ".parquet", ".bin", ".gz"):
                    if any(keyword in lower for keyword in keywords):
                        count += 1
                        if count >= limit:
                            return count
    except OSError:
        return count
    return count


def main() -> int:
    issues: list[str] = []
    ok: list[str] = []

    key = os.environ.get("DATABENTO_API_KEY", "").strip()
    if key:
        ok.append(f"DATABENTO_API_KEY is set (length={len(key)}); secret not printed")
    else:
        issues.append(
            "DATABENTO_API_KEY is missing — export it for live Databento pulls, "
            "or set QHPC_ALLOW_SYNTHETIC_DEMO=1 when running the demo."
        )

    try:
        import databento  # noqa: F401

        ok.append("databento Python package import OK")
    except ImportError:
        issues.append("databento not installed — pip install -e '.[data-pipeline]' for live API")

    kdb_repo = os.environ.get("QHPC_KDB_TAQ_REPO", "").strip()
    if not kdb_repo:
        home = Path.home()
        for candidate in (
            "/Users/prady/desktop/kdb-taq",
            "/Users/prady/Desktop/kdb-taq",
            home / "desktop" / "kdb-taq",
            home / "Desktop" / "kdb-taq",
        ):
            path = Path(candidate)
            if path.is_dir():
                kdb_repo = str(path)
                break
    if kdb_repo:
        kpath = Path(kdb_repo).expanduser()
        if kpath.is_dir():
            ok.append(f"kdb-taq repo found: {kpath}")
            q_count = 0
            try:
                for _ in kpath.rglob("*.q"):
                    q_count += 1
                    if q_count >= 50000:
                        break
            except OSError:
                pass
            ok.append(f"  *.q files counted (cap 50000): {q_count}")
        else:
            issues.append(f"QHPC_KDB_TAQ_REPO path is not a directory: {kpath}")
    else:
        issues.append(
            "kdb-taq repo not found at default paths — set QHPC_KDB_TAQ_REPO to your checkout"
        )

    q_bin = os.environ.get("QHPC_KDB_Q_BINARY", "q").strip() or "q"
    q_path = shutil.which(q_bin)
    if q_path:
        ok.append(f"q executable on PATH: {q_path}")
    else:
        issues.append(
            f"q/kdb executable not found ({q_bin}) — install kdb+ or set QHPC_KDB_Q_BINARY"
        )

    taq = os.environ.get("QHPC_TAQ_ROOT", "").strip()
    if not taq:
        taq = str(ROOT / "data" / "qhpc_data" / "taq_incoming")
    tpath = Path(taq).expanduser()
    n_taqish = _count_taq_like_files(tpath)
    if tpath.is_dir():
        ok.append(f"QHPC_TAQ_ROOT (or default) exists: {tpath}; taq-like files ~{n_taqish}")
    else:
        issues.append(f"TAQ directory missing: {tpath} — create or set QHPC_TAQ_ROOT")

    if kdb_repo and Path(kdb_repo).expanduser().is_dir():
        n_kdb = _count_taq_like_files(Path(kdb_repo).expanduser())
        ok.append(f"taq-like files under kdb-taq tree (approx): {n_kdb}")

    pixel = Path("/Users/prady/Desktop/pixel-agents")
    if pixel.is_dir():
        ok.append(f"Pixel Agents repo present: {pixel}")
    else:
        issues.append("Optional: Pixel Agents repo not at ~/Desktop/pixel-agents (bridge still exports JSONL here)")

    crsp = os.environ.get("QHPC_CRSP_TREASURY_PATH", "").strip()
    if crsp:
        path = Path(crsp)
        if path.exists():
            ok.append(f"QHPC_CRSP_TREASURY_PATH exists: {path}")
        else:
            issues.append(f"QHPC_CRSP_TREASURY_PATH does not exist: {path}")
    else:
        issues.append(
            "QHPC_CRSP_TREASURY_PATH not set — rates use fallback until WRDS/CRSP file is wired"
        )

    data_root = Path(os.environ.get("QHPC_DATA_ROOT", str(ROOT / "data" / "qhpc_data")))
    try:
        data_root.mkdir(parents=True, exist_ok=True)
        probe = data_root / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        ok.append(f"QHPC_DATA_ROOT writable: {data_root}")
    except OSError as exc:
        issues.append(f"Cannot write QHPC_DATA_ROOT ({data_root}): {exc}")

    out_dir = ROOT / "outputs" / "data_ingestion_event_book"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        ok.append(f"outputs dir ready: {out_dir}")
    except OSError as exc:
        issues.append(f"Cannot create outputs dir: {exc}")

    try:
        import pandas  # noqa: F401

        ok.append("pandas import OK")
    except ImportError:
        issues.append("pandas not installed — run: pip install -e '.[data-pipeline]'")

    print("--- qhpc data environment check ---")
    for line in ok:
        print(f"[ok] {line}")
    for line in issues:
        print(f"[action] {line}")

    critical = any("Cannot write QHPC_DATA_ROOT" in item for item in issues)
    critical = critical or any("Cannot create outputs dir" in item for item in issues)
    strict = os.environ.get("QHPC_STRICT_DATA_ENV", "").strip() in ("1", "true", "yes")
    if strict and issues:
        critical = True
    return 1 if critical else 0


if __name__ == "__main__":
    sys.exit(main())
