"""Registry helpers for unified workload-family observability outputs."""

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


def register_unified_workload_observability(
    *,
    data_root: str,
    run_id: str,
    output_files: Sequence[str | Path],
    date_range_start: str = "unknown",
    date_range_end: str = "unknown",
    notes: str = "",
) -> None:
    """Register unified observability artifacts as canonical research dataset."""
    pths = [Path(p) for p in output_files]
    disk = _disk_usage(pths)
    t0 = time.perf_counter()
    entry = DatasetRegistryEntry(
        registry_key=f"unified_workload_observability::{run_id}",
        provider="qhpc_unified_observability",
        dataset_kind="unified_workload_observability",
        date_range_start=(date_range_start or "unknown")[:10],
        date_range_end=(date_range_end or "unknown")[:10],
        symbol_coverage="cross_family",
        schema_label="qhpc.unified_observability.v1",
        row_count=0,
        local_paths=[str(p) for p in pths],
        completion_status="complete",
        estimated_disk_usage_bytes=disk,
        realized_disk_usage_bytes=disk,
        ingestion_runtime_seconds=time.perf_counter() - t0,
        checkpoint_label="analytics_ready",
        batch_identifier="unified_observability",
        parent_dataset_label="event_library+feature_panel+portfolio_risk+pricing",
        source_backend="pandas_pipeline",
        notes=notes[:1800],
        wrds_source_table=(
            "crsp.stocknames+crsp.dsf+crsp.dse+crsp.mse+crsp.tfz_dly+crsp.tfz_mth+"
            "wrdsapps_link_crsp_taq.tclink+wrdsapps_link_crsp_taqm.taqmclink+"
            "wrdsapps_link_crsp_taqm.taqmclink_cusip_2010"
        ),
        wrds_dataset_role="canonical",
    )
    register_dataset(data_root, entry)


def register_unified_workload_manifest(
    *,
    data_root: str,
    manifest_path: str | Path,
    run_id: str,
) -> None:
    """Register manifest JSON for unified observability."""
    path = Path(manifest_path)
    notes = ""
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            notes = json.dumps(
                {
                    "run_id": payload.get("run_id", ""),
                    "family_count": payload.get("family_count", 0),
                    "row_count": payload.get("row_count", 0),
                }
            )
        except Exception:
            notes = "manifest_parse_failed"
    register_unified_workload_observability(
        data_root=data_root,
        run_id=run_id,
        output_files=[path],
        notes=notes,
    )

