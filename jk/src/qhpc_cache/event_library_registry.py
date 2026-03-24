"""Registry helpers for event-library comparison outputs."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from qhpc_cache.data_models import DatasetRegistryEntry
from qhpc_cache.data_registry import register_dataset


def _bytes(paths: Iterable[Path]) -> int:
    total = 0
    for p in paths:
        if p.exists():
            total += p.stat().st_size
    return total


def register_event_library_comparison(
    *,
    data_root: str,
    comparison_run_id: str,
    output_files: Sequence[str | Path],
    date_range_start: str,
    date_range_end: str,
    notes: str = "",
) -> None:
    """Register event-library comparison artifacts as a canonical reference dataset."""
    pths = [Path(p) for p in output_files]
    disk = _bytes(pths)
    t0 = time.perf_counter()
    entry = DatasetRegistryEntry(
        registry_key=f"event_library_comparison::{comparison_run_id}",
        provider="qhpc_event_library",
        dataset_kind="event_library_comparison",
        date_range_start=(date_range_start or "unknown")[:10],
        date_range_end=(date_range_end or "unknown")[:10],
        symbol_coverage="permno+symbol",
        schema_label="qhpc.event_library_comparison.v1",
        row_count=0,
        local_paths=[str(p) for p in pths],
        completion_status="complete",
        estimated_disk_usage_bytes=disk,
        realized_disk_usage_bytes=disk,
        ingestion_runtime_seconds=time.perf_counter() - t0,
        checkpoint_label="analytics_ready",
        batch_identifier="event_library_compare",
        parent_dataset_label="aligned_event_window",
        source_backend="pandas_pipeline",
        notes=notes[:1800],
        wrds_source_table=(
            "crsp.stocknames+crsp.dse+crsp.mse+"
            "wrdsapps_link_crsp_taq.tclink+wrdsapps_link_crsp_taqm.taqmclink+"
            "wrdsapps_link_crsp_taqm.taqmclink_cusip_2010"
        ),
        wrds_dataset_role="canonical",
    )
    register_dataset(data_root, entry)


def register_event_library_manifest(
    *,
    data_root: str,
    manifest_path: str | Path,
    comparison_run_id: str,
) -> None:
    """Register manifest JSON alone when full comparison outputs are deferred."""
    path = Path(manifest_path)
    notes = ""
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            notes = json.dumps(
                {
                    "schema_version": payload.get("schema_version", ""),
                    "event_set_count": len(payload.get("event_sets", [])),
                }
            )
        except Exception:
            notes = "manifest_parse_failed"
    register_event_library_comparison(
        data_root=data_root,
        comparison_run_id=comparison_run_id,
        output_files=[path],
        date_range_start="unknown",
        date_range_end="unknown",
        notes=notes,
    )
