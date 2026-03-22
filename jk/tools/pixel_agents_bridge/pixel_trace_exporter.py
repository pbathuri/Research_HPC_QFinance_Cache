"""Export data-phase ``WorkflowEvent`` logs to JSONL for Pixel Agents tooling."""

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

from pixel_mapping import workflow_events_to_jsonl_lines

from qhpc_cache.workflow_events import WorkflowEvent, WorkflowRunSummary


def export_workflow_events_jsonl(
    output_path: Union[str, Path],
    events: List[WorkflowEvent],
) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = workflow_events_to_jsonl_lines(events)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def export_workflow_run_summary_json(
    output_path: Union[str, Path],
    summary: WorkflowRunSummary,
) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = {
        "run_identifier": summary.run_identifier,
        "started_at_utc": summary.started_at_utc,
        "finished_at_utc": summary.finished_at_utc,
        "total_runtime_seconds": summary.total_runtime_seconds,
        "estimated_disk_usage_bytes": summary.estimated_disk_usage_bytes,
        "realized_disk_usage_bytes": summary.realized_disk_usage_bytes,
        "checkpoints_completed": summary.checkpoints_completed,
        "deferred_work": summary.deferred_work,
        "next_recommended_action": summary.next_recommended_action,
        "notes": summary.notes,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
