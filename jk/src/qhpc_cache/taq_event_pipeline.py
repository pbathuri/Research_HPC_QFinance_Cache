"""Canonical CRSP+TAQ event pipeline: local kdb/q extraction → WRDS alignment → normalized storage.

**Entrypoint order (locked):** TAQ extraction first, then PERMNO alignment and CRSP enrichment
(see ``docs/event_alignment_design.md``). Feature panels must consume outputs from this layer.

Delegates kdb/q to ``taq_kdb_adapter``; alignment logic lives in ``event_alignment``.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

from qhpc_cache.data_models import DatasetRegistryEntry, EventAlignmentManifest, EventWindowRequest
from qhpc_cache.data_registry import register_dataset

if TYPE_CHECKING:
    import pandas as pd

from qhpc_cache.event_alignment import (
    align_taq_window_to_crsp_permno,
    attach_crsp_events_to_event_window,
    attach_crsp_security_master_to_event_window,
    build_normalized_event_window,
    fetch_canonical_wrds_alignment_frames,
)
from qhpc_cache.taq_kdb_adapter import (
    default_kdb_taq_repo,
    load_extracted_event_window,
    run_q_event_window_extraction,
)


def extract_local_taq_event_window(
    request: EventWindowRequest,
    *,
    repo_root: Optional[Path] = None,
    output_csv: Optional[Path] = None,
    timeout_seconds: float = 600.0,
) -> Tuple[Optional["pd.DataFrame"], Any]:
    """Extract a single window via local **kdb/q** (``kdb-taq`` repo).

    Returns ``(dataframe_or_none, QExtractionResult)``.
    """
    root = Path(repo_root).expanduser() if repo_root else default_kdb_taq_repo()
    q_res = run_q_event_window_extraction(
        request,
        repo_root=root,
        output_csv=output_csv,
        timeout_seconds=timeout_seconds,
    )
    if not q_res.ok or q_res.output_csv is None:
        return None, q_res
    frame = load_extracted_event_window(q_res.output_csv)
    return frame, q_res


def aligned_event_registry_note(manifest: EventAlignmentManifest) -> str:
    """Compact registry note for aligned event datasets."""
    parts = [
        f"permno_rate={manifest.permno_match_rate:.4f}",
        f"links={manifest.match_sources_used}",
        f"sm={manifest.security_master_attached}",
        f"ev={manifest.crsp_events_attached}",
    ]
    return ";".join(parts)


def register_aligned_event_window(
    *,
    data_root: str,
    manifest: EventAlignmentManifest,
    primary_path: str | Path,
    batch_identifier: str = "aligned",
) -> None:
    """Register a normalized aligned event dataset.

    Kept here instead of a tiny sidecar module so the canonical aligned-event
    pipeline owns its persistence contract end to end.
    """
    path = Path(primary_path)
    disk = path.stat().st_size if path.exists() else 0
    t0 = time.perf_counter()
    entry = DatasetRegistryEntry(
        registry_key=f"aligned_event::{manifest.event_identifier}::{manifest.deterministic_label}",
        provider="qhpc_event_alignment",
        dataset_kind="aligned_event_window",
        date_range_start=manifest.window_start_utc[:10],
        date_range_end=manifest.window_end_utc[:10],
        symbol_coverage=manifest.match_sources_used or "permno",
        schema_label="qhpc.normalized_event_window.v1",
        row_count=manifest.aligned_row_count,
        local_paths=[str(path)],
        completion_status="complete" if manifest.aligned_row_count > 0 else "empty",
        estimated_disk_usage_bytes=disk,
        realized_disk_usage_bytes=disk,
        ingestion_runtime_seconds=time.perf_counter() - t0,
        checkpoint_label="event_book_complete",
        batch_identifier=batch_identifier,
        parent_dataset_label="taq_extract",
        source_backend="kdb_taq_plus_wrds",
        notes=aligned_event_registry_note(manifest),
        wrds_source_table="crsp.stocknames+link_tables+dse+mse",
        wrds_dataset_role="canonical",
    )
    register_dataset(data_root, entry)


def run_aligned_event_pipeline(
    request: EventWindowRequest,
    *,
    data_root: str,
    wrds_db: Optional[Any] = None,
    fetch_wrds: bool = True,
    taq_symbol_col: Optional[str] = None,
    output_base: Optional[Path] = None,
    register: bool = True,
    run_id: str = "",
    record_observability: bool = True,
) -> Dict[str, Any]:
    """End-to-end: kdb TAQ extract → WRDS links/master/events → normalized panel → optional registry.

    Requires live WRDS when ``fetch_wrds`` and ``wrds_db`` are set; otherwise pass
    pre-fetched link frames via environment hook is not implemented — use synthetic tests
    or call lower-level functions with in-memory frames.
    """
    import pandas as pd

    from qhpc_cache.cache_workload_mapping import record_spine_pipeline_observation
    from qhpc_cache.workload_signatures import WORKLOAD_SPINE_EVENT_WINDOW

    t0 = time.perf_counter()
    report: Dict[str, Any] = {
        "ok": False,
        "event_identifier": request.event_identifier,
        "stages": [],
    }

    taq_df, q_res = extract_local_taq_event_window(request)
    report["extraction"] = {"ok": q_res.ok, "message": q_res.message}
    if taq_df is None or len(taq_df) == 0:
        report["error"] = "TAQ extraction produced no rows"
        return report
    report["stages"].append("taq_extracted")

    link_frames: Dict[str, Optional[pd.DataFrame]] = {
        "tclink": None,
        "taqmclink": None,
        "cusip_2010": None,
    }
    stock_df: Optional[pd.DataFrame] = None
    dse_df: Optional[pd.DataFrame] = None
    mse_df: Optional[pd.DataFrame] = None

    if fetch_wrds and wrds_db is not None:
        bundles = fetch_canonical_wrds_alignment_frames(wrds_db)
        for k in link_frames:
            if k in bundles:
                link_frames[k] = bundles[k][0]
        stock_df = bundles.get("stocknames", (None, {}))[0]
        dse_df = bundles.get("dse", (None, {}))[0]
        mse_df = bundles.get("mse", (None, {}))[0]
        report["stages"].append("wrds_frames_fetched")
    else:
        report["stages"].append("wrds_skipped_no_db")

    aligned, align_meta = align_taq_window_to_crsp_permno(
        taq_df,
        link_frames=link_frames,
        taq_symbol_col=taq_symbol_col,
    )
    report["alignment_meta"] = align_meta
    report["stages"].append("permno_aligned")

    sm_ok = False
    if stock_df is not None and len(stock_df) > 0:
        aligned, sm_meta = attach_crsp_security_master_to_event_window(aligned, stock_df)
        report["security_master_meta"] = sm_meta
        sm_ok = True
    ev_ok = False
    if (dse_df is not None and len(dse_df) > 0) or (mse_df is not None and len(mse_df) > 0):
        aligned, ev_meta = attach_crsp_events_to_event_window(aligned, dse_df, mse_df)
        report["events_meta"] = ev_meta
        ev_ok = True

    norm, norm_info = build_normalized_event_window(
        aligned,
        event_identifier=request.event_identifier,
        event_label=request.event_label,
        window_start_iso=request.start_timestamp.isoformat(),
        window_end_iso=request.end_timestamp.isoformat(),
        symbols=list(request.symbols),
    )
    report["stages"].append("normalized")

    base = Path(output_base) if output_base else Path(request.local_output_directory) / "aligned"
    base.mkdir(parents=True, exist_ok=True)
    det = norm_info["deterministic_label"]
    parquet_path = base / f"aligned__{request.event_identifier}__{det}.parquet"
    manifest_path = base / f"aligned__{request.event_identifier}__{det}.manifest.json"
    try:
        norm.to_parquet(parquet_path, index=False)
    except Exception:
        csv_path = parquet_path.with_suffix(".csv")
        norm.to_csv(csv_path, index=False)
        parquet_path = csv_path

    win_sec = int((request.end_timestamp - request.start_timestamp).total_seconds())
    created = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    manifest = EventAlignmentManifest(
        event_identifier=request.event_identifier,
        event_label=request.event_label,
        deterministic_label=det,
        taq_row_count=len(taq_df),
        aligned_row_count=len(norm),
        permno_match_rate=float(align_meta.get("permno_match_rate", 0.0)),
        match_sources_used=";".join(align_meta.get("sources_attempted", [])),
        match_confidence_note="primary=1.0 cusip_map=0.85 where applied",
        security_master_attached=sm_ok,
        crsp_events_attached=ev_ok,
        normalized_storage_path=str(parquet_path),
        manifest_storage_path=str(manifest_path),
        window_start_utc=request.start_timestamp.isoformat(),
        window_end_utc=request.end_timestamp.isoformat(),
        created_at_utc=str(norm["qhpc_aligned_at_utc"].iloc[0]) if len(norm) and "qhpc_aligned_at_utc" in norm.columns else created,
        extra={"q_stdout_tail": (q_res.stdout or "")[-500:]},
    )
    manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")

    if register:
        register_aligned_event_window(
            data_root=data_root,
            manifest=manifest,
            primary_path=parquet_path,
        )
        report["stages"].append("registry")

    report["ok"] = True
    report["normalized_path"] = str(parquet_path)
    report["manifest_path"] = str(manifest_path)
    report["elapsed_seconds"] = time.perf_counter() - t0

    if record_observability:
        reuse_hint = len(align_meta.get("sources_attempted", []))
        record_spine_pipeline_observation(
            run_id=run_id or f"evt_{det}",
            workload_spine_id=WORKLOAD_SPINE_EVENT_WINDOW,
            pipeline_phase="event_alignment",
            source_datasets="taq_kdb;wrds_tclink;wrds_taqmclink;wrds_cusip;crsp.stocknames;dse;mse",
            row_count_primary=len(taq_df),
            row_count_after_join=len(norm),
            join_width_estimate=len(norm.columns),
            event_window_seconds=win_sec,
            alignment_match_rate=float(align_meta.get("permno_match_rate", -1.0)),
            reuse_alignment_opportunities=reuse_hint,
            notes=json.dumps({"deterministic_label": det, "event": request.event_identifier})[:500],
        )

    return report
