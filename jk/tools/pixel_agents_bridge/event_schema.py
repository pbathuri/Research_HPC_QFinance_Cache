"""JSON-serializable schema for qhpc research workflow exports (versioned)."""

from __future__ import annotations

from typing import Any, Dict, List, TypedDict


SCHEMA_VERSION = "1.0"


class QhpcResearchEventV1(TypedDict, total=False):
    """One logical activity (matches ``ResearchTaskEvent`` fields)."""

    schema_version: str
    event_identifier: str
    agent_name: str
    event_type: str
    event_timestamp: str
    task_identifier: str
    active_file_path: str
    event_summary: str
    event_details: str
    status_label: str


class QhpcResearchTraceFileV1(TypedDict, total=False):
    """Full trace file wrapper."""

    schema_version: str
    trace_name: str
    generated_from: str
    workflow_state_snapshots: List[Dict[str, Any]]
    event_log: List[QhpcResearchEventV1]


def wrap_trace_payload(trace_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Attach schema version for consumers."""
    out = dict(trace_dict)
    out["schema_version"] = SCHEMA_VERSION
    return out
