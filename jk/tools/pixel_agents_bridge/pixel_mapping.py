"""Map ``WorkflowEvent`` rows to Pixel Agents–friendly JSONL records."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from qhpc_cache.workflow_events import WorkflowEvent


def workflow_event_to_pixel_row(event: WorkflowEvent) -> Dict[str, Any]:
    """Shape similar to research bridge: assistant + tool_use + qhpc metadata."""
    tool_id = f"qhpc-data-{event.event_identifier[:16]}"
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_id,
                    "name": "Bash",
                    "input": {
                        "command": f"{event.event_type}: {event.summary}"[:400],
                    },
                }
            ]
        },
        "_qhpc_data_phase": {
            "event_identifier": event.event_identifier,
            "stage_name": event.stage_name,
            "event_type": event.event_type,
            "timestamp_label": event.timestamp_label,
            "active_module_name": event.active_module_name,
            "active_dataset_label": event.active_dataset_label,
            "active_symbol_batch": event.active_symbol_batch,
            "status_label": event.status_label,
            "details": event.details,
        },
    }


def workflow_events_to_jsonl_lines(events: List[WorkflowEvent]) -> List[str]:
    return [json.dumps(workflow_event_to_pixel_row(event), ensure_ascii=False) for event in events]
