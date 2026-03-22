"""Local partitioned storage: Parquet preferred, CSV fallback, deterministic paths + metadata."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from qhpc_cache.data_models import HistoricalDatasetMetadata

try:
    import pandas as pd
except ImportError:  # pragma: no cover - optional dependency
    pd = None  # type: ignore

try:
    import pyarrow  # noqa: F401 — presence enables parquet in pandas
except ImportError:
    pyarrow = None  # type: ignore


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def preferred_storage_format() -> str:
    if pd is not None and pyarrow is not None:
        return "parquet"
    return "csv"


def build_storage_path(
    base_directory: Union[str, Path],
    *,
    provider_name: str,
    dataset_label: str,
    batch_identifier: str,
    date_start: str,
    date_end: str,
    extension: str,
) -> Path:
    """Build a deterministic filename under ``base_directory``."""
    safe_provider = provider_name.replace(os.sep, "_").replace(" ", "_")
    safe_label = dataset_label.replace(os.sep, "_").replace(" ", "_")
    safe_batch = batch_identifier.replace(os.sep, "_").replace(" ", "_")
    name = f"{safe_provider}__{safe_label}__{safe_batch}__{date_start}__{date_end}.{extension}"
    return Path(base_directory) / name


def save_dataframe_or_records(
    data: Union["pd.DataFrame", Sequence[Mapping[str, Any]]],
    output_path: Union[str, Path],
    *,
    metadata: HistoricalDatasetMetadata,
    metadata_path: Optional[Union[str, Path]] = None,
) -> Path:
    """Save a DataFrame or sequence of record dicts; write sidecar JSON metadata."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = preferred_storage_format()
    if fmt == "parquet":
        if pd is None:
            raise RuntimeError("pandas + pyarrow required for Parquet; install data-pipeline extras.")
        frame = data if hasattr(data, "to_parquet") else pd.DataFrame(list(data))
        path = path.with_suffix(".parquet")
        frame.to_parquet(path, index=False)
    else:
        path = path.with_suffix(".csv")
        if pd is not None and hasattr(data, "to_csv"):
            data.to_csv(path, index=False)  # type: ignore[union-attr]
        elif pd is not None:
            rows = list(data)
            if not rows:
                path.write_text("", encoding="utf-8")
            else:
                fieldnames = list(rows[0].keys())
                with path.open("w", encoding="utf-8", newline="") as file_handle:
                    writer = csv.DictWriter(file_handle, fieldnames=fieldnames)
                    writer.writeheader()
                    for row in rows:
                        writer.writerow({key: row.get(key, "") for key in fieldnames})
        else:
            raise RuntimeError("pandas required for CSV export; pip install -e '.[data-pipeline]'")

    meta_path = Path(metadata_path) if metadata_path else path.with_suffix(path.suffix + ".metadata.json")
    meta = metadata
    if meta.storage_format != fmt:
        meta = HistoricalDatasetMetadata(
            dataset_label=metadata.dataset_label,
            provider_name=metadata.provider_name,
            schema_label=metadata.schema_label,
            symbol_count=metadata.symbol_count,
            date_start=metadata.date_start,
            date_end=metadata.date_end,
            row_count=metadata.row_count,
            storage_format=fmt,
            created_at_utc=metadata.created_at_utc,
            batch_identifier=metadata.batch_identifier,
            extra=dict(metadata.extra),
        )
    meta_path.write_text(
        json.dumps(
            {
                "dataset_label": meta.dataset_label,
                "provider_name": meta.provider_name,
                "schema_label": meta.schema_label,
                "symbol_count": meta.symbol_count,
                "date_start": meta.date_start,
                "date_end": meta.date_end,
                "row_count": meta.row_count,
                "storage_format": meta.storage_format,
                "created_at_utc": meta.created_at_utc,
                "batch_identifier": meta.batch_identifier,
                "extra": meta.extra,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def load_saved_dataset(path: Union[str, Path]) -> "pd.DataFrame":
    """Load Parquet or CSV from ``path``."""
    if pd is None:
        raise RuntimeError("pandas is required to load_saved_dataset; pip install -e '.[data-pipeline]'")
    path = Path(path)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def save_event_window_dataset(
    data: Union["pd.DataFrame", Sequence[Mapping[str, Any]]],
    output_path: Union[str, Path],
    *,
    metadata: HistoricalDatasetMetadata,
) -> Path:
    """Persist an extracted event window (same storage rules as ``save_dataframe_or_records``)."""
    return save_dataframe_or_records(data, output_path, metadata=metadata)


def save_reference_dataset(
    data: Union["pd.DataFrame", Sequence[Mapping[str, Any]]],
    output_path: Union[str, Path],
    *,
    metadata: HistoricalDatasetMetadata,
) -> Path:
    """Persist reference / definition-style metadata table."""
    return save_dataframe_or_records(data, output_path, metadata=metadata)


def summarize_saved_dataset(path: Union[str, Path]) -> Dict[str, Any]:
    """Return row count, byte size, and metadata path if present."""
    path = Path(path)
    meta_path = path.with_suffix(path.suffix + ".metadata.json")
    row_count = 0
    columns: List[str] = []
    if path.exists() and pd is not None:
        if path.suffix.lower() == ".parquet":
            frame = pd.read_parquet(path)
        else:
            frame = pd.read_csv(path)
        row_count = len(frame)
        columns = list(frame.columns)
    meta: Dict[str, Any] = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return {
        "path": str(path),
        "bytes": path.stat().st_size if path.exists() else 0,
        "row_count": row_count,
        "columns": columns,
        "metadata": meta,
    }


def dataframe_from_records(records: Sequence[Mapping[str, Any]]) -> "pd.DataFrame":
    if pd is None:
        raise RuntimeError("pandas required; pip install -e '.[data-pipeline]'")
    return pd.DataFrame(list(records))
