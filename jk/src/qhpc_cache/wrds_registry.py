"""Persist WRDS pull artifacts and register them in the shared dataset registry."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from qhpc_cache.data_models import DatasetRegistryEntry
from qhpc_cache.data_registry import default_registry_paths, register_dataset


def infer_wrds_identifier_coverage(df: Any) -> str:
    """Short tag for registry ``symbol_coverage`` / notes from common CRSP/TAQ columns."""
    if df is None:
        return "n/a"
    try:
        n = len(df)
    except Exception:
        return "n/a"
    if n == 0:
        return "n/a"
    try:
        cols = {str(c).lower() for c in df.columns}
    except Exception:
        return "unreadable_columns"
    tags: List[str] = []
    if "permno" in cols or "permco" in cols:
        tags.append("permno")
    if "cusip" in cols or "ncusip" in cols:
        tags.append("cusip")
    if "ticker" in cols or "tic" in cols or "symbol" in cols:
        tags.append("ticker_or_symbol")
    return ",".join(tags) if tags else "see_column_list"


def wrds_local_dir(data_root: Optional[str] = None) -> Path:
    root = Path(data_root or os.environ.get("QHPC_DATA_ROOT", "data/qhpc_data"))
    p = root / "wrds"
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_wrds_dataset(
    df: Any,
    *,
    registry_key: str,
    data_root: Optional[str] = None,
    fmt: str = "parquet",
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Path:
    """Write DataFrame to ``<data_root>/wrds/<registry_key>/`` and return path."""
    if df is None:
        raise ValueError("save_wrds_dataset: df is None")
    base = wrds_local_dir(data_root) / registry_key.replace("/", "_")
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if fmt == "parquet":
        path = base / f"{stamp}.parquet"
        try:
            df.to_parquet(path, index=False)
        except Exception:
            path = base / f"{stamp}.csv"
            df.to_csv(path, index=False)
            fmt = "csv"
    else:
        path = base / f"{stamp}.csv"
        df.to_csv(path, index=False)
    meta_path = base / f"{stamp}_meta.json"
    meta: Dict[str, Any] = {
        "registry_key": registry_key,
        "row_count": int(len(df)),
        "columns": list(df.columns),
        "written_at_utc": datetime.now(timezone.utc).isoformat(),
        "format": fmt,
        "artifact": str(path),
    }
    if extra_meta:
        meta.update(extra_meta)
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return path


def _dataset_kind_for_wrds_role(role: str) -> str:
    r = (role or "enrichment").strip().lower()
    if r == "canonical":
        return "wrds_canonical"
    if r == "optional":
        return "wrds_optional"
    return "wrds_enrichment"


def register_wrds_dataset(
    *,
    data_root: str,
    registry_key: str,
    local_paths: List[str],
    row_count: int,
    date_range_start: str,
    date_range_end: str,
    schema_label: str,
    batch_identifier: str,
    ingestion_seconds: float,
    notes: str = "",
    parent_dataset_label: str = "",
    wrds_source_table: str = "",
    wrds_dataset_role: str = "enrichment",
    identifier_coverage: str = "",
) -> None:
    """Append/replace a ``DatasetRegistryEntry`` with provider ``wrds``.

    ``wrds_dataset_role`` should be one of: ``canonical``, ``enrichment``, ``optional``.
    """
    disk_bytes = sum(Path(p).stat().st_size for p in local_paths if Path(p).exists())
    sym_cov = identifier_coverage if identifier_coverage else "n/a"
    entry = DatasetRegistryEntry(
        registry_key=registry_key,
        provider="wrds",
        dataset_kind=_dataset_kind_for_wrds_role(wrds_dataset_role),
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        symbol_coverage=sym_cov,
        schema_label=schema_label,
        row_count=row_count,
        local_paths=list(local_paths),
        completion_status="complete" if row_count > 0 else "empty_or_failed",
        estimated_disk_usage_bytes=disk_bytes,
        realized_disk_usage_bytes=disk_bytes,
        ingestion_runtime_seconds=ingestion_seconds,
        checkpoint_label="reference_data_complete",
        batch_identifier=batch_identifier,
        parent_dataset_label=parent_dataset_label,
        source_backend="wrds_sql",
        notes=notes,
        wrds_source_table=wrds_source_table or schema_label,
        wrds_dataset_role=wrds_dataset_role or "enrichment",
    )
    register_dataset(data_root, entry)


def pull_and_register_crsp_treasury(
    *,
    data_root: Optional[str] = None,
    wrds_username: Optional[str] = None,
    limit: int = 200_000,
) -> Dict[str, Any]:
    """End-to-end: connect, load ``tfz_dly`` then ``tfz_mth``, save, register."""
    from qhpc_cache.wrds_provider import (
        check_wrds_connection,
        load_crsp_treasury_daily,
        load_crsp_treasury_monthly,
    )

    dr = data_root or os.environ.get("QHPC_DATA_ROOT", "data/qhpc_data")
    paths = default_registry_paths(dr)
    paths["registry_dir"].mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    report: Dict[str, Any] = {"ok": False, "registry_key": "wrds_crsp_treasury_context"}

    ok, msg, db = check_wrds_connection(wrds_username=wrds_username)
    report["connection"] = msg
    if not ok or db is None:
        report["error"] = msg
        return report

    df, meta = load_crsp_treasury_daily(db, limit=limit)
    if df is None or len(df) == 0:
        df, meta = load_crsp_treasury_monthly(db, limit=limit)
    elapsed = time.perf_counter() - t0
    report["query_meta"] = meta
    if df is None or len(df) == 0:
        report["error"] = meta.get("error", "no rows")
        return report

    src_table = str(meta.get("wrds_source_table") or f'{meta.get("schema")}.{meta.get("table")}')
    id_cov = infer_wrds_identifier_coverage(df)
    try:
        p = save_wrds_dataset(
            df,
            registry_key=report["registry_key"],
            data_root=dr,
            extra_meta={
                "wrds_source_table": src_table,
                "identifier_coverage": id_cov,
                "wrds_dataset_role": "canonical",
            },
        )
    except Exception as exc:
        report["error"] = f"save failed: {exc}"
        return report

    # crude date bounds from common column names
    d0, d1 = "", ""
    for col in ("date", "caldt", "time_avail_m", "yyyymm"):
        if col in df.columns:
            try:
                s = df[col].min()
                e = df[col].max()
                d0, d1 = str(s)[:10], str(e)[:10]
            except Exception:
                pass
            break

    register_wrds_dataset(
        data_root=dr,
        registry_key=report["registry_key"],
        local_paths=[str(p)],
        row_count=len(df),
        date_range_start=d0 or "unknown",
        date_range_end=d1 or "unknown",
        schema_label=src_table,
        batch_identifier=f"wrds_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        ingestion_seconds=elapsed,
        notes="Canonical CRSP Treasury: crsp.tfz_dly preferred, else crsp.tfz_mth",
        wrds_source_table=src_table,
        wrds_dataset_role="canonical",
        identifier_coverage=id_cov,
    )
    report["ok"] = True
    report["local_path"] = str(p)
    return report
