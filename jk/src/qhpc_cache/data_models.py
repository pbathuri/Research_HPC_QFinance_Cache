"""Dataclasses for historical data requests, metadata, event book, and registry rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class HistoricalDataRequest:
    """Generic historical pull parameters shared across providers."""

    symbols: Sequence[str]
    start_date: date
    end_date: date
    schema_label: str
    provider_name: str
    local_output_directory: str
    adjusted_prices_required: bool = True
    notes: str = ""


@dataclass
class DailyUniverseRequest:
    """Broad daily OHLCV + optional reference metadata."""

    universe_name: str
    symbols: Sequence[str]
    start_date: date
    end_date: date
    adjusted_prices_required: bool
    include_reference_data: bool
    provider_name: str
    local_output_directory: str
    notes: str = ""


@dataclass
class EventWindowRequest:
    """Single high-frequency window extraction request."""

    event_identifier: str
    event_label: str
    symbols: Sequence[str]
    start_timestamp: datetime
    end_timestamp: datetime
    data_schema_label: str
    provider_name: str
    local_input_path: str
    local_output_directory: str
    notes: str = ""


@dataclass
class RatesDataRequest:
    """Pluggable Treasury / risk-free ingestion."""

    source_name: str
    start_date: date
    end_date: date
    local_input_path: str
    use_if_available: bool = True
    notes: str = ""


@dataclass
class HistoricalDatasetMetadata:
    """Sidecar metadata saved next to partitioned files."""

    dataset_label: str
    provider_name: str
    schema_label: str
    symbol_count: int
    date_start: str
    date_end: str
    row_count: int
    storage_format: str
    created_at_utc: str
    batch_identifier: str
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EventBookEntry:
    """One stored high-risk window."""

    event_identifier: str
    event_label: str
    event_category: str
    symbols: Sequence[str]
    time_window_start: str
    time_window_end: str
    source_name: str
    local_storage_path: str
    row_count: int
    notes: str = ""


@dataclass
class EventBookSummary:
    """Aggregate view of the event book."""

    total_events: int
    completed_events: int
    pending_events: int
    total_rows: int
    total_disk_bytes: int
    entries: List[EventBookEntry]
    deferred_identifiers: List[str]


@dataclass
class DatasetRegistryEntry:
    """One registered artifact (daily, event, rates, or reference)."""

    registry_key: str
    provider: str
    dataset_kind: str
    date_range_start: str
    date_range_end: str
    symbol_coverage: str
    schema_label: str
    row_count: int
    local_paths: List[str]
    completion_status: str
    estimated_disk_usage_bytes: int
    realized_disk_usage_bytes: int
    ingestion_runtime_seconds: float
    checkpoint_label: str
    batch_identifier: str
    parent_dataset_label: str
    source_backend: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "registry_key": self.registry_key,
            "provider": self.provider,
            "dataset_kind": self.dataset_kind,
            "date_range_start": self.date_range_start,
            "date_range_end": self.date_range_end,
            "symbol_coverage": self.symbol_coverage,
            "schema_label": self.schema_label,
            "row_count": self.row_count,
            "local_paths": list(self.local_paths),
            "completion_status": self.completion_status,
            "estimated_disk_usage_bytes": self.estimated_disk_usage_bytes,
            "realized_disk_usage_bytes": self.realized_disk_usage_bytes,
            "ingestion_runtime_seconds": self.ingestion_runtime_seconds,
            "checkpoint_label": self.checkpoint_label,
            "batch_identifier": self.batch_identifier,
            "parent_dataset_label": self.parent_dataset_label,
            "source_backend": self.source_backend,
            "notes": self.notes,
        }

    @staticmethod
    def from_dict(row: Dict[str, Any]) -> "DatasetRegistryEntry":
        return DatasetRegistryEntry(
            registry_key=str(row["registry_key"]),
            provider=str(row["provider"]),
            dataset_kind=str(row["dataset_kind"]),
            date_range_start=str(row["date_range_start"]),
            date_range_end=str(row["date_range_end"]),
            symbol_coverage=str(row["symbol_coverage"]),
            schema_label=str(row["schema_label"]),
            row_count=int(row["row_count"]),
            local_paths=list(row["local_paths"]),
            completion_status=str(row["completion_status"]),
            estimated_disk_usage_bytes=int(row["estimated_disk_usage_bytes"]),
            realized_disk_usage_bytes=int(row["realized_disk_usage_bytes"]),
            ingestion_runtime_seconds=float(row["ingestion_runtime_seconds"]),
            checkpoint_label=str(row["checkpoint_label"]),
            batch_identifier=str(row["batch_identifier"]),
            parent_dataset_label=str(row.get("parent_dataset_label", "")),
            source_backend=str(row.get("source_backend", "")),
            notes=str(row.get("notes", "")),
        )
