"""Orchestration: daily universe, reference, event book hooks, rates, validation, dataset stack."""

from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from qhpc_cache.data_models import (
    DailyUniverseRequest,
    DatasetRegistryEntry,
    HistoricalDatasetMetadata,
    RatesDataRequest,
)
from qhpc_cache.data_registry import (
    initialize_dataset_registry,
    load_dataset_registry,
    register_dataset,
    set_checkpoint,
    summarize_registry,
)
from qhpc_cache.data_sources import CrspTreasuryFileProvider, DatabentoProvider
from qhpc_cache.data_storage import (
    build_storage_path,
    preferred_storage_format,
    save_dataframe_or_records,
    save_reference_dataset,
)
from qhpc_cache.universe_builder import recommend_batch_size_for_budget, split_universe_into_batches


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def directory_size_bytes(root: Path) -> int:
    total = 0
    if not root.exists():
        return 0
    for path in root.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                pass
    return total


def _time_budget_seconds() -> float:
    raw = os.environ.get("QHPC_PIPELINE_TIME_BUDGET_SEC", "6480")
    return max(60.0, float(raw))


def _disk_budget_bytes() -> int:
    raw = os.environ.get("QHPC_PIPELINE_DISK_BUDGET_BYTES", str(45 * 1024**3))
    return max(10**9, int(float(raw)))


def load_or_download_daily_universe(
    request: DailyUniverseRequest,
    data_root: str,
    *,
    allow_synthetic_fallback: bool = False,
) -> Dict[str, Any]:
    """Download daily OHLCV in deterministic batches, or load from registry paths.

    Respects time/disk budgets. Skips batches already marked ``complete`` in registry.
    """
    initialize_dataset_registry(data_root)
    set_checkpoint(data_root, "registry_initialized", status="complete")
    paths_root = Path(request.local_output_directory)
    paths_root.mkdir(parents=True, exist_ok=True)

    provider = DatabentoProvider()
    time_budget = _time_budget_seconds()
    disk_budget = _disk_budget_bytes()
    start_clock = time.perf_counter()
    batches_completed: List[str] = []
    errors: List[str] = []

    if not DatabentoProvider.api_key_present():
        if allow_synthetic_fallback:
            return write_synthetic_daily_universe(request, data_root)
        return {
            "status": "skipped_no_credentials",
            "message": "Set DATABENTO_API_KEY or pass allow_synthetic_fallback=True for demo panel.",
            "batches_completed": [],
        }

    scope = DatabentoProvider.estimate_request_scope(
        request.symbols,
        request.start_date,
        request.end_date,
    )
    batch_size = recommend_batch_size_for_budget(
        request.symbols,
        request.start_date,
        request.end_date,
        disk_budget_bytes=min(disk_budget, 15 * 1024**3),
        time_budget_seconds=time_budget * 0.5,
    )
    batches = split_universe_into_batches(request.symbols, batch_size)
    existing = {entry.registry_key for entry in load_dataset_registry(data_root)}

    for batch_index, batch_symbols in enumerate(batches):
        elapsed = time.perf_counter() - start_clock
        if elapsed > time_budget:
            errors.append("time_budget_exhausted")
            break
        batch_id = f"batch_{batch_index:04d}"
        registry_key = f"daily_ohlcv::{request.universe_name}::{batch_id}"
        if registry_key in existing:
            batches_completed.append(batch_id)
            continue

        t0 = time.perf_counter()
        try:
            frame = provider.fetch_daily_ohlcv_data(request, batch_symbols)
        except Exception as exc:  # pragma: no cover - network
            errors.append(str(exc))
            register_dataset(
                data_root,
                DatasetRegistryEntry(
                    registry_key=registry_key,
                    provider=provider.name,
                    dataset_kind="daily_ohlcv",
                    date_range_start=request.start_date.isoformat(),
                    date_range_end=request.end_date.isoformat(),
                    symbol_coverage=",".join(batch_symbols),
                    schema_label=provider.schema_daily,
                    row_count=0,
                    local_paths=[],
                    completion_status="partial",
                    estimated_disk_usage_bytes=int(scope["estimated_disk_bytes"] / max(1, len(batches))),
                    realized_disk_usage_bytes=0,
                    ingestion_runtime_seconds=time.perf_counter() - t0,
                    checkpoint_label="broad_universe_partial_complete",
                    batch_identifier=batch_id,
                    parent_dataset_label=request.universe_name,
                    notes=f"fetch_failed: {exc}",
                ),
            )
            break

        ext = "parquet" if preferred_storage_format() == "parquet" else "csv"
        out_path = build_storage_path(
            paths_root,
            provider_name=provider.name,
            dataset_label=request.universe_name,
            batch_identifier=batch_id,
            date_start=request.start_date.isoformat(),
            date_end=request.end_date.isoformat(),
            extension=ext,
        )
        meta = HistoricalDatasetMetadata(
            dataset_label=request.universe_name,
            provider_name=provider.name,
            schema_label=provider.schema_daily,
            symbol_count=len(batch_symbols),
            date_start=request.start_date.isoformat(),
            date_end=request.end_date.isoformat(),
            row_count=len(frame),
            storage_format=preferred_storage_format(),
            created_at_utc=_utc_now_iso(),
            batch_identifier=batch_id,
            extra={"batch_symbols": batch_symbols},
        )
        saved = save_dataframe_or_records(frame, out_path, metadata=meta)
        disk_bytes = saved.stat().st_size
        runtime = time.perf_counter() - t0
        register_dataset(
            data_root,
            DatasetRegistryEntry(
                registry_key=registry_key,
                provider=provider.name,
                dataset_kind="daily_ohlcv",
                date_range_start=request.start_date.isoformat(),
                date_range_end=request.end_date.isoformat(),
                symbol_coverage=",".join(batch_symbols),
                schema_label=provider.schema_daily,
                row_count=len(frame),
                local_paths=[str(saved)],
                completion_status="complete",
                estimated_disk_usage_bytes=int(scope["estimated_disk_bytes"] / max(1, len(batches))),
                realized_disk_usage_bytes=disk_bytes,
                ingestion_runtime_seconds=runtime,
                checkpoint_label="broad_universe_partial_complete",
                batch_identifier=batch_id,
                parent_dataset_label=request.universe_name,
                notes="",
            ),
        )
        batches_completed.append(batch_id)
        set_checkpoint(data_root, "broad_universe_partial_complete", status="complete")
        if directory_size_bytes(Path(data_root)) > disk_budget:
            errors.append("disk_budget_exhausted")
            break

    if len(batches_completed) == len(batches) and not errors:
        set_checkpoint(data_root, "broad_universe_complete", status="complete")

    return {
        "status": "ok" if batches_completed else "partial",
        "batches_completed": batches_completed,
        "batch_count_planned": len(batches),
        "errors": errors,
        "elapsed_seconds": time.perf_counter() - start_clock,
    }


def write_synthetic_daily_universe(
    request: DailyUniverseRequest,
    data_root: str,
) -> Dict[str, Any]:
    """Create a **tiny** synthetic daily panel for offline demos (clearly labeled)."""
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("pandas required for synthetic universe") from exc

    initialize_dataset_registry(data_root)
    paths_root = Path(request.local_output_directory)
    paths_root.mkdir(parents=True, exist_ok=True)
    rows = []
    price = 100.0
    day = request.start_date
    symbols = list(request.symbols)[:12] if request.symbols else ["SYNTH_A", "SYNTH_B"]
    while day <= request.end_date and len(rows) < 5000:
        for symbol in symbols:
            price *= 1.0 + (hash((symbol, day.isoformat())) % 7 - 3) * 0.001
            rows.append(
                {
                    "date": day.isoformat(),
                    "symbol": symbol,
                    "open": price,
                    "high": price * 1.01,
                    "low": price * 0.99,
                    "close": price,
                    "volume": 1_000_000,
                }
            )
        day = date.fromordinal(day.toordinal() + 1)

    frame = pd.DataFrame(rows)
    out_base = paths_root / f"synthetic__{request.universe_name}"
    meta = HistoricalDatasetMetadata(
        dataset_label=request.universe_name,
        provider_name="synthetic_demo",
        schema_label="synthetic_ohlcv",
        symbol_count=len(symbols),
        date_start=request.start_date.isoformat(),
        date_end=request.end_date.isoformat(),
        row_count=len(frame),
        storage_format="csv",
        created_at_utc=_utc_now_iso(),
        batch_identifier="synthetic_batch_0",
        extra={"warning": "SYNTHETIC_FALLBACK_NOT_MARKET_DATA"},
    )
    saved = save_dataframe_or_records(frame, out_base, metadata=meta)
    saved_size = saved.stat().st_size
    register_dataset(
        data_root,
        DatasetRegistryEntry(
            registry_key=f"daily_ohlcv::synthetic::{request.universe_name}",
            provider="synthetic_demo",
            dataset_kind="daily_ohlcv",
            date_range_start=request.start_date.isoformat(),
            date_range_end=request.end_date.isoformat(),
            symbol_coverage=",".join(symbols),
            schema_label="synthetic_ohlcv",
            row_count=len(frame),
            local_paths=[str(saved)],
            completion_status="complete",
            estimated_disk_usage_bytes=saved_size,
            realized_disk_usage_bytes=saved_size,
            ingestion_runtime_seconds=0.0,
            checkpoint_label="broad_universe_complete",
            batch_identifier="synthetic_batch_0",
            parent_dataset_label=request.universe_name,
            notes="SYNTHETIC_FALLBACK — not Databento data.",
        ),
    )
    set_checkpoint(data_root, "broad_universe_complete", status="complete")
    return {"status": "synthetic_fallback", "batches_completed": ["synthetic_batch_0"], "errors": []}


def ingest_reference_data_for_universe(
    request: DailyUniverseRequest,
    data_root: str,
    *,
    batch_size: int = 40,
) -> Dict[str, Any]:
    """Best-effort definition/reference pull per symbol batch."""
    if not DatabentoProvider.api_key_present():
        return {"status": "skipped_no_credentials", "paths": []}
    provider = DatabentoProvider()
    paths_root = Path(data_root) / "reference"
    paths_root.mkdir(parents=True, exist_ok=True)
    saved_paths: List[str] = []
    batches = split_universe_into_batches(request.symbols, batch_size)
    for batch_index, batch_symbols in enumerate(batches):
        try:
            frame = provider.fetch_reference_data(request, batch_symbols)
        except Exception:
            continue
        if frame is None or len(frame) == 0:
            continue
        batch_id = f"ref_{batch_index:04d}"
        ext = "parquet" if preferred_storage_format() == "parquet" else "csv"
        out_path = build_storage_path(
            paths_root,
            provider_name=provider.name,
            dataset_label=f"{request.universe_name}_reference",
            batch_identifier=batch_id,
            date_start=request.start_date.isoformat(),
            date_end=request.end_date.isoformat(),
            extension=ext,
        )
        meta = HistoricalDatasetMetadata(
            dataset_label=f"{request.universe_name}_reference",
            provider_name=provider.name,
            schema_label="definition",
            symbol_count=len(batch_symbols),
            date_start=request.start_date.isoformat(),
            date_end=request.end_date.isoformat(),
            row_count=len(frame),
            storage_format=preferred_storage_format(),
            created_at_utc=_utc_now_iso(),
            batch_identifier=batch_id,
            extra={},
        )
        saved = save_reference_dataset(frame, out_path, metadata=meta)
        saved_paths.append(str(saved))
        register_dataset(
            data_root,
            DatasetRegistryEntry(
                registry_key=f"reference::{request.universe_name}::{batch_id}",
                provider=provider.name,
                dataset_kind="reference",
                date_range_start=request.start_date.isoformat(),
                date_range_end=request.end_date.isoformat(),
                symbol_coverage=",".join(batch_symbols),
                schema_label="definition",
                row_count=len(frame),
                local_paths=[str(saved)],
                completion_status="complete",
                estimated_disk_usage_bytes=saved.stat().st_size,
                realized_disk_usage_bytes=saved.stat().st_size,
                ingestion_runtime_seconds=0.0,
                checkpoint_label="reference_data_complete",
                batch_identifier=batch_id,
                parent_dataset_label=request.universe_name,
                notes="",
            ),
        )
    if saved_paths:
        set_checkpoint(data_root, "reference_data_complete", status="complete")
    return {"status": "ok", "paths": saved_paths}


def ingest_event_book_from_local_taq(*args: Any, **kwargs: Any) -> Any:
    """Delegate to ``qhpc_cache.event_book.extract_event_windows_from_taq`` (avoid circular import)."""
    from qhpc_cache.event_book import extract_event_windows_from_taq

    return extract_event_windows_from_taq(*args, **kwargs)


def load_or_ingest_rates_data(
    request: RatesDataRequest,
    data_root: str,
) -> Dict[str, Any]:
    """Load CRSP-style Treasury file if path exists; otherwise return skipped."""
    if not request.use_if_available:
        return {"status": "skipped_disabled", "source": request.source_name}
    path = Path(request.local_input_path)
    if not path.exists():
        return {"status": "skipped_no_file", "source": request.source_name, "path": str(path)}
    provider = CrspTreasuryFileProvider()
    t0 = time.perf_counter()
    try:
        raw = provider.load_treasury_rates(request)
        series = provider.build_risk_free_rate_series(raw)
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
    out_dir = Path(data_root) / "rates"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"treasury_{request.source_name}.csv"
    meta = HistoricalDatasetMetadata(
        dataset_label="treasury_rates",
        provider_name=provider.name,
        schema_label="risk_free_daily",
        symbol_count=0,
        date_start=request.start_date.isoformat(),
        date_end=request.end_date.isoformat(),
        row_count=len(series),
        storage_format="csv",
        created_at_utc=_utc_now_iso(),
        batch_identifier="rates_full",
        extra={"source_name": request.source_name},
    )
    save_dataframe_or_records(series, out_path, metadata=meta)
    register_dataset(
        data_root,
        DatasetRegistryEntry(
            registry_key=f"rates::{request.source_name}",
            provider=provider.name,
            dataset_kind="rates",
            date_range_start=request.start_date.isoformat(),
            date_range_end=request.end_date.isoformat(),
            symbol_coverage="",
            schema_label="risk_free_daily",
            row_count=len(series),
            local_paths=[str(out_path)],
            completion_status="complete",
            estimated_disk_usage_bytes=out_path.stat().st_size,
            realized_disk_usage_bytes=out_path.stat().st_size,
            ingestion_runtime_seconds=time.perf_counter() - t0,
            checkpoint_label="rates_layer_complete",
            batch_identifier="rates_full",
            parent_dataset_label="",
            notes="",
        ),
    )
    set_checkpoint(data_root, "rates_layer_complete", status="complete")
    return {"status": "ok", "path": str(out_path), "rows": len(series)}


def validate_universe_alignment(
    registry_entries: Sequence[DatasetRegistryEntry],
    *,
    expected_universe_name: str,
) -> Tuple[bool, List[str]]:
    """Sanity-check registry contains expected daily OHLCV parent label."""
    issues: List[str] = []
    daily = [entry for entry in registry_entries if entry.dataset_kind == "daily_ohlcv"]
    if not daily:
        issues.append("no_daily_ohlcv_entries")
        return False, issues
    for entry in daily:
        if entry.parent_dataset_label != expected_universe_name and "synthetic" not in entry.provider:
            issues.append(f"unexpected_parent: {entry.registry_key}")
    return len(issues) == 0, issues


def validate_event_book(summary_path: Path) -> Tuple[bool, str]:
    """Validate manifest JSON exists and has expected keys."""
    if not summary_path.is_file():
        return False, "manifest_missing"
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    if "summary" not in data or "entries" not in data:
        return False, "invalid_manifest_shape"
    return True, "ok"


def build_initial_dataset_stack(
    daily_request: DailyUniverseRequest,
    data_root: str,
    *,
    rates_request: Optional[RatesDataRequest] = None,
    event_catalog: Optional[Any] = None,
    allow_synthetic_fallback: bool = False,
) -> Dict[str, Any]:
    """Run ordered ingestion: daily → reference → rates; event book optional."""
    initialize_dataset_registry(data_root)
    set_checkpoint(data_root, "environment_verified", status="complete")
    out: Dict[str, Any] = {"daily": {}, "reference": {}, "rates": {}, "event_book": None}
    out["daily"] = load_or_download_daily_universe(
        daily_request,
        data_root,
        allow_synthetic_fallback=allow_synthetic_fallback,
    )
    if daily_request.include_reference_data:
        out["reference"] = ingest_reference_data_for_universe(daily_request, data_root)
    if rates_request is not None:
        out["rates"] = load_or_ingest_rates_data(rates_request, data_root)
    if event_catalog is not None:
        from qhpc_cache.event_book import extract_event_windows_from_taq, summarize_event_book

        summary = extract_event_windows_from_taq(
            event_catalog,
            data_root=data_root,
            time_budget_seconds=_time_budget_seconds() * 0.25,
            disk_budget_bytes=min(_disk_budget_bytes(), 30 * 1024**3),
        )
        out["event_book"] = summarize_event_book(summary)
    return out
