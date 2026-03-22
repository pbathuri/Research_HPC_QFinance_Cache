"""High-risk event book: catalog, TAQ extraction, validation, manifest."""

from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

UnionPath = str | Path

from qhpc_cache.data_models import (
    DatasetRegistryEntry,
    EventBookEntry,
    EventBookSummary,
    EventWindowRequest,
    HistoricalDatasetMetadata,
)
from qhpc_cache.data_registry import register_event_window
from qhpc_cache.data_sources import NyseTaqFileProvider
from qhpc_cache.data_storage import build_storage_path, preferred_storage_format, save_event_window_dataset
from qhpc_cache.event_definitions import default_event_catalog
from qhpc_cache.taq_kdb_adapter import (
    default_kdb_taq_repo,
    kdb_backend_ready,
    load_extracted_event_window,
    run_q_event_window_extraction,
    validate_extracted_event_window,
)


def build_default_event_catalog(
    *,
    taq_root: str,
    output_root: str,
) -> List[EventWindowRequest]:
    """Wrapper around ``event_definitions.default_event_catalog``."""
    return default_event_catalog(taq_root=taq_root, output_root=output_root)


def _persist_event_window_frame(
    combined: Any,
    request: EventWindowRequest,
    *,
    data_root: str,
    register: bool,
    start_clock: float,
    provider_name: str,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Tuple[EventBookEntry, int, int]:
    """Write frame to storage, optionally registry; return entry, row_count, disk_bytes."""
    import pandas as pd

    if not isinstance(combined, pd.DataFrame) or len(combined) == 0:
        raise ValueError("combined must be a non-empty DataFrame")

    out_dir = Path(request.local_output_directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = "parquet" if preferred_storage_format() == "parquet" else "csv"
    storage_path = build_storage_path(
        out_dir,
        provider_name=provider_name,
        dataset_label=request.event_identifier,
        batch_identifier="full",
        date_start=request.start_timestamp.date().isoformat(),
        date_end=request.end_timestamp.date().isoformat(),
        extension=ext,
    )
    meta_extra = {"event_label": request.event_label, "notes": request.notes}
    if extra_meta:
        meta_extra.update(extra_meta)
    meta = HistoricalDatasetMetadata(
        dataset_label=request.event_identifier,
        provider_name=provider_name,
        schema_label=request.data_schema_label,
        symbol_count=len(request.symbols),
        date_start=request.start_timestamp.isoformat(),
        date_end=request.end_timestamp.isoformat(),
        row_count=len(combined),
        storage_format=preferred_storage_format(),
        created_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        batch_identifier="full",
        extra=meta_extra,
    )
    saved = save_event_window_dataset(combined, storage_path, metadata=meta)
    disk_bytes = saved.stat().st_size
    entry = EventBookEntry(
        event_identifier=request.event_identifier,
        event_label=request.event_label,
        event_category=_category_for_event(request.event_identifier),
        symbols=list(request.symbols),
        time_window_start=request.start_timestamp.isoformat(),
        time_window_end=request.end_timestamp.isoformat(),
        source_name=provider_name,
        local_storage_path=str(saved),
        row_count=len(combined),
        notes=request.notes,
    )
    if register:
        register_event_window(
            data_root,
            DatasetRegistryEntry(
                registry_key=f"event::{request.event_identifier}",
                provider=provider_name,
                dataset_kind="event_window",
                date_range_start=request.start_timestamp.date().isoformat(),
                date_range_end=request.end_timestamp.date().isoformat(),
                symbol_coverage=",".join(request.symbols[:20]),
                schema_label=request.data_schema_label,
                row_count=len(combined),
                local_paths=[str(saved)],
                completion_status="complete",
                estimated_disk_usage_bytes=disk_bytes,
                realized_disk_usage_bytes=disk_bytes,
                ingestion_runtime_seconds=time.perf_counter() - start_clock,
                checkpoint_label="event_book_partial_complete",
                batch_identifier="full",
                parent_dataset_label="daily_universe",
                notes=request.notes,
            ),
        )
    return entry, len(combined), disk_bytes


def extract_event_windows_from_taq(
    catalog: List[EventWindowRequest],
    *,
    data_root: str,
    time_budget_seconds: float,
    disk_budget_bytes: int,
    register: bool = True,
    prefer_kdb_extraction: bool = True,
    kdb_repo_root: Optional[str] = None,
) -> EventBookSummary:
    """Extract prioritized windows: **kdb/q backend first** (local kdb-taq), then flat files.

    Disable kdb with ``prefer_kdb_extraction=False`` or ``QHPC_PREFER_KDB_TAQ=0``.
    """
    if os.environ.get("QHPC_PREFER_KDB_TAQ", "1").strip().lower() in ("0", "false", "no"):
        prefer_kdb_extraction = False

    provider = NyseTaqFileProvider()
    if not catalog:
        return EventBookSummary(
            total_events=0,
            completed_events=0,
            pending_events=0,
            total_rows=0,
            total_disk_bytes=0,
            entries=[],
            deferred_identifiers=[],
        )

    entries: List[EventBookEntry] = []
    total_rows = 0
    total_disk = 0
    start_clock = time.perf_counter()
    disk_used = 0
    done_ids: Set[str] = set()

    kdb_root = Path(kdb_repo_root).expanduser() if kdb_repo_root else default_kdb_taq_repo()
    kdb_ready, _ = (False, "")
    if prefer_kdb_extraction:
        kdb_ready, _ = kdb_backend_ready(kdb_root)

    try:
        import pandas as pd
    except ImportError:
        done_ids = set()
        pending_left = [request.event_identifier for request in catalog]
        return EventBookSummary(
            total_events=len(catalog),
            completed_events=0,
            pending_events=len(catalog),
            total_rows=0,
            total_disk_bytes=0,
            entries=[],
            deferred_identifiers=pending_left,
        )

    if prefer_kdb_extraction and kdb_ready:
        for request in catalog:
            elapsed = time.perf_counter() - start_clock
            if elapsed > time_budget_seconds or disk_used > disk_budget_bytes:
                break
            out_csv = Path(tempfile.mkdtemp(prefix="qhpc_kdb_evt_")) / f"{request.event_identifier}.csv"
            q_result = run_q_event_window_extraction(request, repo_root=kdb_root, output_csv=out_csv)
            if not q_result.ok:
                continue
            try:
                frame = load_extracted_event_window(q_result.output_csv)  # type: ignore[arg-type]
            except Exception:
                continue
            valid, _ = validate_extracted_event_window(frame, request)
            if not valid or len(frame) == 0:
                continue
            entry, row_count, disk_bytes = _persist_event_window_frame(
                frame,
                request,
                data_root=data_root,
                register=register,
                start_clock=start_clock,
                provider_name="nyse_taq_kdb",
                extra_meta={"extraction_backend": "kdb", "q_stderr_tail": q_result.stderr[-500:]},
            )
            entries.append(entry)
            total_rows += row_count
            disk_used += disk_bytes
            total_disk += disk_bytes
            done_ids.add(request.event_identifier)
            if time.perf_counter() - start_clock > time_budget_seconds:
                break

    taq_root = Path(catalog[0].local_input_path)
    files = provider.discover_available_taq_files(taq_root) if taq_root.is_dir() else []
    for request in catalog:
        if request.event_identifier in done_ids:
            continue
        elapsed = time.perf_counter() - start_clock
        if elapsed > time_budget_seconds or disk_used > disk_budget_bytes:
            break
        combined = None
        for file_path in files:
            try:
                frame = provider.load_taq_window(file_path, chunksize=200_000)
            except Exception:
                continue
            ok, _ = provider.validate_taq_window(frame, request)
            if not ok:
                continue
            chunk = provider.extract_event_window(frame, request)
            if len(chunk) == 0:
                continue
            if combined is None:
                combined = chunk
            else:
                combined = pd.concat([combined, chunk], ignore_index=True)

        if combined is None or len(combined) == 0:
            continue

        entry, row_count, disk_bytes = _persist_event_window_frame(
            combined,
            request,
            data_root=data_root,
            register=register,
            start_clock=start_clock,
            provider_name=request.provider_name,
            extra_meta={"extraction_backend": "flat_file"},
        )
        entries.append(entry)
        total_rows += row_count
        disk_used += disk_bytes
        total_disk += disk_bytes
        done_ids.add(request.event_identifier)

        if time.perf_counter() - start_clock > time_budget_seconds:
            break

    pending_left = [request.event_identifier for request in catalog if request.event_identifier not in done_ids]
    return EventBookSummary(
        total_events=len(catalog),
        completed_events=len(entries),
        pending_events=len(pending_left),
        total_rows=total_rows,
        total_disk_bytes=total_disk,
        entries=entries,
        deferred_identifiers=pending_left,
    )


def _category_for_event(event_identifier: str) -> str:
    if "covid" in event_identifier or "march_2020" in event_identifier:
        return "pandemic_liquidity"
    if "rate" in event_identifier:
        return "rates"
    if "banking" in event_identifier:
        return "credit_banking"
    if "cpi" in event_identifier or "fomc" in event_identifier:
        return "macro_release"
    if "flash" in event_identifier:
        return "microstructure"
    if "commodity" in event_identifier:
        return "commodities"
    if "earnings" in event_identifier:
        return "single_name"
    return "other"


def summarize_event_book(summary: EventBookSummary) -> Dict[str, Any]:
    return {
        "total_events": summary.total_events,
        "completed_events": summary.completed_events,
        "pending_events": summary.pending_events,
        "total_rows": summary.total_rows,
        "total_disk_bytes": summary.total_disk_bytes,
        "deferred_identifiers": list(summary.deferred_identifiers),
    }


def validate_event_book_alignment(
    daily_universe_symbols: List[str],
    summary: EventBookSummary,
) -> Tuple[bool, List[str]]:
    """Check event symbols are subset of universe when universe is non-empty."""
    issues: List[str] = []
    universe_set = {symbol.upper() for symbol in daily_universe_symbols}
    if not universe_set:
        return True, issues
    for entry in summary.entries:
        for symbol in entry.symbols:
            if symbol.upper() not in universe_set:
                issues.append(f"{entry.event_identifier}: symbol {symbol} not in daily universe list")
    return len(issues) == 0, issues


def save_event_book_manifest(
    path: UnionPath,
    summary: EventBookSummary,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "summary": summarize_event_book(summary),
        "entries": [
            {
                "event_identifier": entry.event_identifier,
                "event_label": entry.event_label,
                "event_category": entry.event_category,
                "symbols": list(entry.symbols),
                "time_window_start": entry.time_window_start,
                "time_window_end": entry.time_window_end,
                "source_name": entry.source_name,
                "local_storage_path": entry.local_storage_path,
                "row_count": entry.row_count,
                "notes": entry.notes,
            }
            for entry in summary.entries
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
