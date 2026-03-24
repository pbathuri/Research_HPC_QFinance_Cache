"""Export ``ResearchSimulationTrace`` to JSON / JSONL / text (in-package).

Replaces the removed ``tools/pixel_agents_bridge/trace_exporter.py``. No Pixel
runtime or external bridge is required.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qhpc_cache.research_agents import ResearchSimulationTrace


def export_research_trace_to_json(path: Path, trace: "ResearchSimulationTrace") -> None:
    """Write the full trace as pretty-printed JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "trace_name": trace.trace_name,
        "generated_from": trace.generated_from,
        "workflow_state_snapshots": [asdict(s) for s in trace.workflow_state_snapshots],
        "event_log": [asdict(e) for e in trace.event_log],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def export_research_trace_to_jsonl(path: Path, trace: "ResearchSimulationTrace") -> None:
    """Write one JSON object per line for the event log (qhpc schema)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for ev in trace.event_log:
            row = {
                "schema_version": "1.0",
                "trace_name": trace.trace_name,
                "generated_from": trace.generated_from,
                **asdict(ev),
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def export_research_trace_summary(path: Path, trace: "ResearchSimulationTrace") -> None:
    """Human-readable summary for logs and markdown appendices."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"Trace: {trace.trace_name}",
        f"Generated from: {trace.generated_from}",
        f"Snapshots: {len(trace.workflow_state_snapshots)}",
        f"Events: {len(trace.event_log)}",
        "",
        "Final snapshot:",
    ]
    if trace.workflow_state_snapshots:
        last = trace.workflow_state_snapshots[-1]
        lines.extend(
            [
                f"  workflow_name={last.workflow_name}",
                f"  active_agents={last.active_agents}",
                f"  queued_tasks={last.queued_tasks}",
                f"  completed_tasks={last.completed_tasks}",
                f"  notes={last.notes}",
            ]
        )
    lines.append("")
    lines.append("Recent events:")
    for ev in trace.event_log[-12:]:
        lines.append(
            f"  [{ev.event_timestamp}] {ev.agent_name} / {ev.event_type}: {ev.event_summary}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
