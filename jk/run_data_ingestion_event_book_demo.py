#!/usr/bin/env python3
"""Data ingestion + event-book demo: budgets, checkpoints, analytics.

Run from ``jk/``::

    pip install -e ".[data-pipeline]"
    PYTHONPATH=src python3 run_data_ingestion_event_book_demo.py

Outputs under ``outputs/data_ingestion_event_book/``. Data under ``QHPC_DATA_ROOT`` (default ``data/qhpc_data``).
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from qhpc_cache.data_ingestion import (  # noqa: E402
    directory_size_bytes,
    load_or_download_daily_universe,
    load_or_ingest_rates_data,
    validate_event_book,
)
from qhpc_cache.data_models import DailyUniverseRequest, RatesDataRequest  # noqa: E402
from qhpc_cache.data_registry import (  # noqa: E402
    initialize_dataset_registry,
    load_checkpoints,
    set_checkpoint,
)
from qhpc_cache.data_sources import DatabentoProvider  # noqa: E402
from qhpc_cache.event_book import (  # noqa: E402
    build_default_event_catalog,
    extract_event_windows_from_taq,
    save_event_book_manifest,
    validate_event_book_alignment,
)
from qhpc_cache.data_ingestion import validate_universe_alignment  # noqa: E402
from qhpc_cache.data_registry import load_dataset_registry  # noqa: E402
from qhpc_cache.rates_data import load_risk_free_rate_series_priority  # noqa: E402
from qhpc_cache.universe_analysis import analyze_large_universe_daily_layer  # noqa: E402
from qhpc_cache.universe_builder import build_large_us_equity_etf_universe_request  # noqa: E402
from qhpc_cache.taq_kdb_adapter import (  # noqa: E402
    default_kdb_taq_repo,
    discover_local_taq_datasets,
    inspect_kdb_taq_repo,
    kdb_backend_ready,
)
from qhpc_cache.research_memory import critical_window_with_modules  # noqa: E402
from qhpc_cache.wrds_placeholder import (  # noqa: E402
    WRDS_ACCESS_ACTIVE,
    WRDS_ACCESS_UNAVAILABLE,
    default_wrds_state,
)
from qhpc_cache.wrds_provider import check_wrds_connection  # noqa: E402
from qhpc_cache.wrds_queries import roadmap_dict  # noqa: E402


def main() -> None:
    started = time.perf_counter()
    started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    data_root = os.environ.get("QHPC_DATA_ROOT", str(ROOT / "data" / "qhpc_data"))
    out_dir = ROOT / "outputs" / "data_ingestion_event_book"
    out_dir.mkdir(parents=True, exist_ok=True)

    initialize_dataset_registry(data_root)
    set_checkpoint(data_root, "environment_verified", status="complete")

    has_db = DatabentoProvider.api_key_present()
    daily_dir = str(Path(data_root) / "daily_universe")
    daily_request = build_large_us_equity_etf_universe_request(
        start_date=date(2019, 1, 2),
        end_date=date(2020, 12, 31),
        local_output_directory=daily_dir,
        include_reference_data=False,
    )

    synthetic_allowed = os.environ.get("QHPC_ALLOW_SYNTHETIC_DEMO", "1").strip() not in (
        "0",
        "false",
        "no",
    )

    if has_db:
        daily_result = load_or_download_daily_universe(
            daily_request,
            data_root,
            allow_synthetic_fallback=False,
        )
    else:
        daily_result = load_or_download_daily_universe(
            daily_request,
            data_root,
            allow_synthetic_fallback=synthetic_allowed,
        )

    kdb_repo = default_kdb_taq_repo()
    kdb_inspect = inspect_kdb_taq_repo(kdb_repo)
    kdb_discover = discover_local_taq_datasets(kdb_repo)

    taq_root = os.environ.get("QHPC_TAQ_ROOT", str(Path(data_root) / "taq_incoming"))
    event_out = str(Path(data_root) / "event_book")
    catalog = build_default_event_catalog(taq_root=taq_root, output_root=event_out)

    time_budget = float(os.environ.get("QHPC_PIPELINE_TIME_BUDGET_SEC", "6480")) * 0.2
    disk_budget = min(int(os.environ.get("QHPC_PIPELINE_DISK_BUDGET_BYTES", str(30 * 1024**3))), 30 * 1024**3)

    kdb_ready, kdb_ready_msg = kdb_backend_ready(kdb_repo)

    book_summary = extract_event_windows_from_taq(
        catalog,
        data_root=data_root,
        time_budget_seconds=time_budget,
        disk_budget_bytes=disk_budget,
        register=True,
        prefer_kdb_extraction=True,
        kdb_repo_root=str(kdb_repo),
    )

    manifest_path = out_dir / "event_book_manifest.json"
    save_event_book_manifest(manifest_path, book_summary)

    _wrds_st = default_wrds_state()
    _w_ok, _w_msg, _ = check_wrds_connection()
    _wrds_st.access_status = WRDS_ACCESS_ACTIVE if _w_ok else WRDS_ACCESS_UNAVAILABLE
    _wrds_st.account_notes = (_w_msg or "")[:240]
    _wrds_blob = {**_wrds_st.to_dict(), "wrds_integration_roadmap": roadmap_dict()["roadmap"]}
    (out_dir / "wrds_future_state.json").write_text(
        json.dumps(_wrds_blob, indent=2, default=str),
        encoding="utf-8",
    )

    crsp_path = os.environ.get("QHPC_CRSP_TREASURY_PATH", "").strip()
    rates_req = RatesDataRequest(
        source_name="crsp_or_wrds",
        start_date=daily_request.start_date,
        end_date=daily_request.end_date,
        local_input_path=crsp_path or str(Path(data_root) / "rates" / "placeholder.csv"),
        use_if_available=bool(crsp_path),
    )
    rates_out = load_or_ingest_rates_data(rates_req, data_root)
    if rates_out.get("status") != "ok":
        calendar_guess = [
            daily_request.start_date.isoformat(),
            daily_request.end_date.isoformat(),
        ]
        try_wrds = os.environ.get("QHPC_RATES_TRY_WRDS", "1").lower() in ("1", "true", "yes")
        _, rate_summary = load_risk_free_rate_series_priority(
            calendar_dates=calendar_guess,
            crsp_path=crsp_path if crsp_path else None,
            fallback_annual_rate=0.03,
            try_wrds=try_wrds,
        )

    registry_entries = load_dataset_registry(data_root)
    ok, issues = validate_universe_alignment(
        registry_entries,
        expected_universe_name=daily_request.universe_name,
    )

    align_ok, align_issues = validate_event_book_alignment(list(daily_request.symbols), book_summary)

    manifest_ok, manifest_reason = validate_event_book(manifest_path)

    analysis = analyze_large_universe_daily_layer(data_root, max_rows_per_file=50_000)

    cache_blob = critical_window_with_modules()
    (out_dir / "critical_cache_window.json").write_text(
        json.dumps(cache_blob, indent=2),
        encoding="utf-8",
    )
    set_checkpoint(data_root, "critical_cache_window_built", status="complete")

    set_checkpoint(data_root, "analytics_ready", status="complete")

    elapsed = time.perf_counter() - started
    finished_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    disk_used = directory_size_bytes(Path(data_root))
    checkpoints = load_checkpoints(data_root)
    completed_ck = [name for name, row in checkpoints.items() if row.get("status") == "complete"]

    deferred = []
    if daily_result.get("status") == "skipped_no_credentials" and not synthetic_allowed:
        deferred.append("daily_universe_needs_DATABENTO_API_KEY_or_QHPC_ALLOW_SYNTHETIC_DEMO=1")
    deferred.extend(book_summary.deferred_identifiers)
    if rates_out.get("status") != "ok":
        deferred.append("optional_Treasury_file: set QHPC_CRSP_TREASURY_PATH (constant fallback used otherwise)")

    next_action = (
        "Wire kdb-taq: set QHPC_KDB_TAQ_REPO and QHPC_KDB_EXTRACTION_COMMAND or add scripts/qhpc_export_window.q; "
        "keep TAQ CSV under QHPC_TAQ_ROOT for flat fallback; ensure DATABENTO_API_KEY for live daily data."
    )

    run_summary = {
        "run_identifier": "data_ingestion_event_book_demo",
        "started_at_utc": started_utc,
        "finished_at_utc": finished_utc,
        "total_runtime_seconds": elapsed,
        "realized_disk_usage_bytes": disk_used,
        "checkpoints_completed": completed_ck,
        "deferred_work": deferred,
        "next_recommended_action": next_action,
    }
    summary_path = out_dir / "data_phase_run_summary.json"
    summary_path.write_text(json.dumps(run_summary, indent=2, default=str), encoding="utf-8")

    print("=" * 72)
    print("qhpc_cache — data ingestion + event book demo")
    print("=" * 72)
    print(f"Total runtime (s): {elapsed:.2f}")
    print(f"Realized data root disk usage (bytes): {disk_used}")
    print(f"Checkpoints complete: {completed_ck}")
    print(f"Deferred work: {deferred}")
    print(f"Daily ingestion result: {daily_result}")
    print(f"Event book: completed={book_summary.completed_events} rows={book_summary.total_rows}")
    print(f"Next recommended action: {next_action}")
    print()
    print(f"Wrote: {summary_path}")
    print(f"Wrote: {manifest_path}")
    print(f"Wrote: {out_dir / 'critical_cache_window.json'}")
    print(f"Wrote: {out_dir / 'wrds_future_state.json'}")


if __name__ == "__main__":
    main()
