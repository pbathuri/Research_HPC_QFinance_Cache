"""Registry helpers for cache-study analysis outputs."""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Iterable, Sequence

from qhpc_cache.data_models import DatasetRegistryEntry
from qhpc_cache.data_registry import register_dataset


def _disk_usage(paths: Iterable[Path]) -> int:
    total = 0
    for p in paths:
        if p.exists():
            total += p.stat().st_size
    return total


def register_cache_study_analysis(
    *,
    data_root: str,
    analysis_run_id: str,
    output_files: Sequence[str | Path],
    date_range_start: str,
    date_range_end: str,
    notes: str = "",
) -> None:
    """Register cache-study analysis artifacts as canonical research dataset."""
    pths = [Path(p) for p in output_files]
    disk = _disk_usage(pths)
    t0 = time.perf_counter()
    entry = DatasetRegistryEntry(
        registry_key=f"cache_study_analysis::{analysis_run_id}",
        provider="qhpc_cache_study",
        dataset_kind="cache_study_analysis",
        date_range_start=(date_range_start or "unknown")[:10],
        date_range_end=(date_range_end or "unknown")[:10],
        symbol_coverage="permno+symbol",
        schema_label="qhpc.cache_study_analysis.v1",
        row_count=0,
        local_paths=[str(p) for p in pths],
        completion_status="complete",
        estimated_disk_usage_bytes=disk,
        realized_disk_usage_bytes=disk,
        ingestion_runtime_seconds=time.perf_counter() - t0,
        checkpoint_label="analytics_ready",
        batch_identifier="cache_study_analysis",
        parent_dataset_label="event_library_comparison",
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


def register_cache_study_manifest(
    *,
    data_root: str,
    manifest_path: str | Path,
    analysis_run_id: str,
) -> None:
    """Register manifest JSON for cache-study analysis."""
    path = Path(manifest_path)
    notes = ""
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            notes = json.dumps(
                {
                    "schema_version": payload.get("schema_version", ""),
                    "primary_csv_outputs": len(payload.get("primary_csv_outputs", [])),
                }
            )
        except Exception:
            notes = "manifest_parse_failed"
    register_cache_study_analysis(
        data_root=data_root,
        analysis_run_id=analysis_run_id,
        output_files=[path],
        date_range_start="unknown",
        date_range_end="unknown",
        notes=notes,
    )
