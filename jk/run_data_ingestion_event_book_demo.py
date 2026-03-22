#!/usr/bin/env python3
"""Data ingestion + event-book demo: budgets, checkpoints, analytics, Pixel trace export.

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
sys.path.insert(0, str(ROOT / "tools" / "pixel_agents_bridge"))

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
from qhpc_cache.rates_data import load_pluggable_risk_free_rate_series, summarize_rates_source  # noqa: E402
from qhpc_cache.universe_analysis import analyze_large_universe_daily_layer  # noqa: E402
from qhpc_cache.universe_builder import build_large_us_equity_etf_universe_request  # noqa: E402
from qhpc_cache.workflow_events import WorkflowRunSummary, append_event, workflow_event_now  # noqa: E402
from qhpc_cache.workflow_events import WorkflowStage  # noqa: E402
from qhpc_cache.taq_kdb_adapter import (  # noqa: E402
    default_kdb_taq_repo,
    discover_local_taq_datasets,
    inspect_kdb_taq_repo,
    kdb_backend_ready,
)
from qhpc_cache.research_memory import critical_window_with_modules  # noqa: E402
from qhpc_cache.wrds_placeholder import default_wrds_state  # noqa: E402

import pixel_trace_exporter  # noqa: E402


def main() -> None:
    started = time.perf_counter()
    started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    events = []

    data_root = os.environ.get("QHPC_DATA_ROOT", str(ROOT / "data" / "qhpc_data"))
    out_dir = ROOT / "outputs" / "data_ingestion_event_book"
    out_dir.mkdir(parents=True, exist_ok=True)

    append_event(
        events,
        workflow_event_now(
            event_identifier="evt-provider-check",
            stage=WorkflowStage.ENVIRONMENT,
            event_type="provider_check_started",
            active_module_name="run_data_ingestion_event_book_demo",
            summary="Starting environment and provider checks",
        ),
    )

    initialize_dataset_registry(data_root)
    set_checkpoint(data_root, "environment_verified", status="complete")

    has_db = DatabentoProvider.api_key_present()
    db_key = os.environ.get("DATABENTO_API_KEY", "").strip()
    if has_db:
        append_event(
            events,
            workflow_event_now(
                event_identifier="evt-db-cred",
                stage=WorkflowStage.CREDENTIALS,
                event_type="databento_credentials_found",
                active_module_name="qhpc_cache.data_sources",
                summary=f"DATABENTO_API_KEY is set (length={len(db_key)}); value not logged",
            ),
        )
    else:
        append_event(
            events,
            workflow_event_now(
                event_identifier="evt-db-cred",
                stage=WorkflowStage.CREDENTIALS,
                event_type="databento_credentials_missing",
                active_module_name="qhpc_cache.data_sources",
                summary="DATABENTO_API_KEY missing — will use synthetic daily panel if allowed",
                status_label="degraded",
            ),
        )

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

    append_event(
        events,
        workflow_event_now(
            event_identifier="evt-broad-start",
            stage=WorkflowStage.BROAD_UNIVERSE,
            event_type="broad_universe_download_started",
            active_module_name="qhpc_cache.data_ingestion",
            active_dataset_label=daily_request.universe_name,
            summary=f"Universe symbols (count={len(daily_request.symbols)})",
        ),
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

    for batch_label in daily_result.get("batches_completed", []):
        append_event(
            events,
            workflow_event_now(
                event_identifier=f"evt-batch-{batch_label}",
                stage=WorkflowStage.BROAD_UNIVERSE,
                event_type="broad_universe_batch_completed",
                active_module_name="qhpc_cache.data_ingestion",
                active_dataset_label=daily_request.universe_name,
                active_symbol_batch=batch_label,
                summary=json.dumps(daily_result)[:500],
            ),
        )
        append_event(
            events,
            workflow_event_now(
                event_identifier=f"evt-ckpt-{batch_label}",
                stage=WorkflowStage.BROAD_UNIVERSE,
                event_type="broad_universe_checkpoint_saved",
                active_module_name="qhpc_cache.data_registry",
                active_dataset_label=daily_request.universe_name,
                active_symbol_batch=batch_label,
                summary="Registry updated after batch",
            ),
        )

    append_event(
        events,
        workflow_event_now(
            event_identifier="evt-ref",
            stage=WorkflowStage.REFERENCE,
            event_type="reference_data_ingestion_completed",
            active_module_name="qhpc_cache.data_ingestion",
            summary="Skipped in demo (include_reference_data=False for speed)",
            status_label="skipped",
        ),
    )

    kdb_repo = default_kdb_taq_repo()
    append_event(
        events,
        workflow_event_now(
            event_identifier="evt-kdb-inspect-start",
            stage=WorkflowStage.KDB_TAQ,
            event_type="kdb_taq_repo_inspection_started",
            active_module_name="qhpc_cache.taq_kdb_adapter",
            summary=str(kdb_repo),
        ),
    )
    kdb_inspect = inspect_kdb_taq_repo(kdb_repo)
    kdb_discover = discover_local_taq_datasets(kdb_repo)
    append_event(
        events,
        workflow_event_now(
            event_identifier="evt-kdb-inspect-done",
            stage=WorkflowStage.KDB_TAQ,
            event_type="kdb_taq_repo_inspection_completed",
            active_module_name="qhpc_cache.taq_kdb_adapter",
            summary=json.dumps(
                {
                    "exists": kdb_inspect.get("exists"),
                    "q_file_count": kdb_inspect.get("q_file_count"),
                    "q_available": kdb_inspect.get("q_available"),
                    "candidate_scripts": kdb_discover.get("candidate_q_scripts", [])[:12],
                    "flat_candidates": len(kdb_discover.get("flat_data_candidates", [])),
                }
            )[:1800],
        ),
    )

    taq_root = os.environ.get("QHPC_TAQ_ROOT", str(Path(data_root) / "taq_incoming"))
    event_out = str(Path(data_root) / "event_book")
    catalog = build_default_event_catalog(taq_root=taq_root, output_root=event_out)

    append_event(
        events,
        workflow_event_now(
            event_identifier="evt-taq-start",
            stage=WorkflowStage.EVENT_BOOK,
            event_type="taq_event_window_ingestion_started",
            active_module_name="qhpc_cache.event_book",
            summary=f"TAQ root={taq_root}",
        ),
    )

    time_budget = float(os.environ.get("QHPC_PIPELINE_TIME_BUDGET_SEC", "6480")) * 0.2
    disk_budget = min(int(os.environ.get("QHPC_PIPELINE_DISK_BUDGET_BYTES", str(30 * 1024**3))), 30 * 1024**3)

    kdb_ready, kdb_ready_msg = kdb_backend_ready(kdb_repo)
    append_event(
        events,
        workflow_event_now(
            event_identifier="evt-q-extract-start",
            stage=WorkflowStage.KDB_TAQ,
            event_type="q_event_window_extraction_started",
            active_module_name="qhpc_cache.event_book",
            summary=f"kdb_ready={kdb_ready} ({kdb_ready_msg})",
        ),
    )

    book_summary = extract_event_windows_from_taq(
        catalog,
        data_root=data_root,
        time_budget_seconds=time_budget,
        disk_budget_bytes=disk_budget,
        register=True,
        prefer_kdb_extraction=True,
        kdb_repo_root=str(kdb_repo),
    )

    append_event(
        events,
        workflow_event_now(
            event_identifier="evt-q-extract-done",
            stage=WorkflowStage.KDB_TAQ,
            event_type="q_event_window_extraction_completed",
            active_module_name="qhpc_cache.event_book",
            summary=f"completed={book_summary.completed_events} kdb_rows={sum(entry.row_count for entry in book_summary.entries if entry.source_name == 'nyse_taq_kdb')}",
        ),
    )
    if kdb_ready and catalog and not any(entry.source_name == "nyse_taq_kdb" for entry in book_summary.entries):
        append_event(
            events,
            workflow_event_now(
                event_identifier="evt-q-extract-fail",
                stage=WorkflowStage.KDB_TAQ,
                event_type="q_event_window_extraction_failed",
                active_module_name="qhpc_cache.taq_kdb_adapter",
                summary="kdb backend ready but no windows materialized — check QHPC_KDB_EXTRACTION_COMMAND or scripts/qhpc_export_window.q",
                details=kdb_ready_msg[:1200],
                status_label="degraded",
            ),
        )

    append_event(
        events,
        workflow_event_now(
            event_identifier="evt-taq-done",
            stage=WorkflowStage.EVENT_BOOK,
            event_type="taq_event_window_ingestion_completed",
            active_module_name="qhpc_cache.event_book",
            summary=f"completed={book_summary.completed_events} pending={len(book_summary.deferred_identifiers)}",
        ),
    )

    manifest_path = out_dir / "event_book_manifest.json"
    save_event_book_manifest(manifest_path, book_summary)

    (out_dir / "wrds_future_state.json").write_text(
        json.dumps(default_wrds_state().to_dict(), indent=2),
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
    if rates_out.get("status") == "ok":
        append_event(
            events,
            workflow_event_now(
                event_identifier="evt-rates",
                stage=WorkflowStage.RATES,
                event_type="rates_layer_loaded",
                active_module_name="qhpc_cache.data_ingestion",
                summary=rates_out.get("path", ""),
            ),
        )
    else:
        calendar_guess = [
            daily_request.start_date.isoformat(),
            daily_request.end_date.isoformat(),
        ]
        _, rate_summary = load_pluggable_risk_free_rate_series(
            crsp_path=None,
            calendar_dates=calendar_guess,
            fallback_annual_rate=0.03,
        )
        append_event(
            events,
            workflow_event_now(
                event_identifier="evt-rates",
                stage=WorkflowStage.RATES,
                event_type="rates_layer_loaded",
                active_module_name="qhpc_cache.rates_data",
                summary=json.dumps(summarize_rates_source(rate_summary)),
                details="fallback_constant_rate",
                status_label="fallback",
            ),
        )

    registry_entries = load_dataset_registry(data_root)
    ok, issues = validate_universe_alignment(
        registry_entries,
        expected_universe_name=daily_request.universe_name,
    )
    append_event(
        events,
        workflow_event_now(
            event_identifier="evt-val-daily",
            stage=WorkflowStage.VALIDATION,
            event_type="daily_universe_validation_completed",
            active_module_name="qhpc_cache.data_ingestion",
            summary="ok" if ok else "issues",
            details="; ".join(issues),
            status_label="ok" if ok else "warning",
        ),
    )

    align_ok, align_issues = validate_event_book_alignment(list(daily_request.symbols), book_summary)
    append_event(
        events,
        workflow_event_now(
            event_identifier="evt-val-events",
            stage=WorkflowStage.VALIDATION,
            event_type="event_book_validation_completed",
            active_module_name="qhpc_cache.event_book",
            details="; ".join(align_issues) if align_issues else "ok",
            status_label="ok" if align_ok else "warning",
        ),
    )

    manifest_ok, manifest_reason = validate_event_book(manifest_path)
    if not manifest_ok:
        append_event(
            events,
            workflow_event_now(
                event_identifier="evt-val-manifest",
                stage=WorkflowStage.VALIDATION,
                event_type="event_book_validation_completed",
                active_module_name="qhpc_cache.event_book",
                summary=manifest_reason,
                status_label="warning",
            ),
        )

    analysis = analyze_large_universe_daily_layer(data_root, max_rows_per_file=50_000)
    append_event(
        events,
        workflow_event_now(
            event_identifier="evt-risk",
            stage=WorkflowStage.ANALYTICS,
            event_type="historical_risk_analysis_completed",
            active_module_name="qhpc_cache.universe_analysis",
            summary=json.dumps({key: analysis[key] for key in analysis if key != "historical_risk_keys"})[:800],
        ),
    )

    cache_blob = critical_window_with_modules()
    (out_dir / "critical_cache_window.json").write_text(
        json.dumps(cache_blob, indent=2),
        encoding="utf-8",
    )
    append_event(
        events,
        workflow_event_now(
            event_identifier="evt-critical-cache",
            stage=WorkflowStage.KNOWLEDGE,
            event_type="critical_cache_window_built",
            active_module_name="qhpc_cache.knowledge_cache",
            summary=f"concepts={cache_blob['summary']['concept_count']}",
            details=str(out_dir / "critical_cache_window.json"),
        ),
    )
    set_checkpoint(data_root, "critical_cache_window_built", status="complete")

    set_checkpoint(data_root, "analytics_ready", status="complete")

    trace_path = out_dir / "data_phase_workflow.jsonl"
    append_event(
        events,
        workflow_event_now(
            event_identifier="evt-pixel",
            stage=WorkflowStage.EXPORT,
            event_type="pixel_trace_exported",
            active_module_name="tools.pixel_agents_bridge.pixel_trace_exporter",
            summary=str(trace_path),
        ),
    )
    pixel_trace_exporter.export_workflow_events_jsonl(trace_path, events)
    set_checkpoint(data_root, "pixel_trace_exported", status="complete")

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

    run_summary = WorkflowRunSummary(
        run_identifier="data_ingestion_event_book_demo",
        started_at_utc=started_utc,
        finished_at_utc=finished_utc,
        total_runtime_seconds=elapsed,
        estimated_disk_usage_bytes=int(os.environ.get("QHPC_PIPELINE_DISK_BUDGET_BYTES", str(45 * 1024**3))),
        realized_disk_usage_bytes=disk_used,
        checkpoints_completed=completed_ck,
        deferred_work=deferred,
        next_recommended_action=next_action,
        notes=json.dumps(daily_result),
    )
    pixel_trace_exporter.export_workflow_run_summary_json(out_dir / "data_phase_run_summary.json", run_summary)

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
    print(f"Wrote: {trace_path}")
    print(f"Wrote: {out_dir / 'data_phase_run_summary.json'}")
    print(f"Wrote: {manifest_path}")
    print(f"Wrote: {out_dir / 'critical_cache_window.json'}")
    print(f"Wrote: {out_dir / 'wrds_future_state.json'}")


if __name__ == "__main__":
    main()
