"""Structured workflow events for data-ingestion runs (JSON-serializable audit trail).

Not tied to any external visualization product; prefer CSV/markdown for inspection.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List


class WorkflowStage(str, Enum):
    """Named pipeline stages for filtering and traces."""

    ENVIRONMENT = "environment"
    CREDENTIALS = "credentials"
    BROAD_UNIVERSE = "broad_universe"
    REFERENCE = "reference"
    EVENT_BOOK = "event_book"
    RATES = "rates"
    VALIDATION = "validation"
    ANALYTICS = "analytics"
    EXPORT = "export"
    KDB_TAQ = "kdb_taq"
    KNOWLEDGE = "knowledge"


@dataclass
class WorkflowEvent:
    """One emission point in the ingestion/analytics pipeline."""

    event_identifier: str
    stage_name: str
    event_type: str
    timestamp_label: str
    active_module_name: str
    active_dataset_label: str
    active_symbol_batch: str
    summary: str
    details: str
    status_label: str

    def to_dict(self) -> Dict[str, Any]:
        row = asdict(self)
        row["stage_name"] = self.stage_name
        return row


@dataclass
class WorkflowRunSummary:
    """Aggregate counters for a single demo/orchestration run."""

    run_identifier: str
    started_at_utc: str
    finished_at_utc: str
    total_runtime_seconds: float
    estimated_disk_usage_bytes: int
    realized_disk_usage_bytes: int
    checkpoints_completed: List[str]
    deferred_work: List[str]
    next_recommended_action: str
    notes: str = ""


def workflow_event_now(
    *,
    event_identifier: str,
    stage: WorkflowStage,
    event_type: str,
    active_module_name: str,
    active_dataset_label: str = "",
    active_symbol_batch: str = "",
    summary: str = "",
    details: str = "",
    status_label: str = "ok",
) -> WorkflowEvent:
    """Factory with UTC timestamp."""
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return WorkflowEvent(
        event_identifier=event_identifier,
        stage_name=stage.value,
        event_type=event_type,
        timestamp_label=timestamp,
        active_module_name=active_module_name,
        active_dataset_label=active_dataset_label,
        active_symbol_batch=active_symbol_batch,
        summary=summary,
        details=details,
        status_label=status_label,
    )


def append_event(
    log: List[WorkflowEvent],
    event: WorkflowEvent,
) -> None:
    log.append(event)
