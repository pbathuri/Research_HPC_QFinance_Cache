"""Write ``ResearchSimulationTrace`` to JSON, JSONL, and plain-text summary."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Union

_BRIDGE_DIR = Path(__file__).resolve().parent
_JK_ROOT = _BRIDGE_DIR.parent.parent
_SRC = _JK_ROOT / "src"
for path in (_BRIDGE_DIR, _SRC):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from event_schema import SCHEMA_VERSION, wrap_trace_payload

from qhpc_cache.research_agents import (
    ResearchSimulationTrace,
    simulation_trace_to_serializable,
    summarize_research_workflow_state,
)


def export_research_trace_to_json(
    output_path: Union[str, Path],
    trace: ResearchSimulationTrace,
    *,
    indent: int = 2,
) -> None:
    """Write full trace (snapshots + events) as JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = wrap_trace_payload(simulation_trace_to_serializable(trace))
    path.write_text(json.dumps(payload, indent=indent), encoding="utf-8")


def export_research_trace_to_jsonl(
    output_path: Union[str, Path],
    trace: ResearchSimulationTrace,
) -> None:
    """Write one JSON object per line: ``event_log`` entries with schema version."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    for event in trace.event_log:
        row: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "trace_name": trace.trace_name,
            "generated_from": trace.generated_from,
            "event_identifier": event.event_identifier,
            "agent_name": event.agent_name,
            "event_type": event.event_type,
            "event_timestamp": event.event_timestamp,
            "task_identifier": event.task_identifier,
            "active_file_path": event.active_file_path,
            "event_summary": event.event_summary,
            "event_details": event.event_details,
            "status_label": event.status_label,
        }
        lines.append(json.dumps(row, ensure_ascii=False))
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def export_research_trace_summary(
    output_path: Union[str, Path],
    trace: ResearchSimulationTrace,
) -> None:
    """Human-readable summary: trace meta + each workflow snapshot + event count."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    blocks = [
        f"Trace: {trace.trace_name}",
        f"Generated from: {trace.generated_from}",
        f"Events: {len(trace.event_log)}",
        f"Snapshots: {len(trace.workflow_state_snapshots)}",
        "",
        "--- Workflow snapshots ---",
    ]
    for index, snap in enumerate(trace.workflow_state_snapshots):
        blocks.append(f"[{index + 1}]")
        blocks.append(summarize_research_workflow_state(snap))
        blocks.append("")
    blocks.append("--- Event summaries (chronological) ---")
    for event in trace.event_log:
        blocks.append(
            f"- {event.event_timestamp} | {event.agent_name} | {event.event_type} | "
            f"{event.task_identifier} | {event.event_summary}"
        )
    path.write_text("\n".join(blocks), encoding="utf-8")
