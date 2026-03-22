"""Map qhpc research events to Claude Code–shaped JSONL lines (compatibility shim).

Pixel Agents parses **live** Claude Code transcripts (see ``pixel-agents/src/transcriptParser.ts``).
These helpers produce **similar** object shapes for offline tooling and future adapters.
They do **not** register agents with the Pixel Agents VS Code extension.
"""

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

from qhpc_cache.research_agents import ResearchSimulationTrace, ResearchTaskEvent


def inspect_pixel_agents_expected_format() -> Dict[str, Any]:
    """Document what the Pixel Agents backend parser expects (summary, not exhaustive)."""
    return {
        "source": "pixel-agents/src/transcriptParser.ts",
        "line_format": "single JSON object per line (JSONL)",
        "record_types_observed": [
            "assistant (message.content[] with tool_use blocks)",
            "user (tool_result blocks)",
            "progress (sub-agent tools)",
            "system subtype turn_duration",
        ],
        "tool_use_shape": {
            "type": "tool_use",
            "id": "string tool instance id",
            "name": "Read | Write | Edit | Bash | ...",
            "input": "object e.g. file_path or command",
        },
        "limitation": "Extension watches ~/.claude/projects/.../*.jsonl for Claude Code sessions.",
    }


def map_research_event_to_pixel_agents_event(
    event: ResearchTaskEvent,
) -> Dict[str, Any]:
    """Map one ``ResearchTaskEvent`` to a minimal ``assistant`` + ``tool_use`` record.

    Adds ``_qhpc_bridge`` metadata so qhpc events are distinguishable from real Claude lines.
    """
    path = event.active_file_path or ""
    if path.endswith((".py", ".md", ".json", ".toml", ".txt")):
        tool_name = "Read"
        tool_input: Dict[str, Any] = {"file_path": path}
    else:
        tool_name = "Bash"
        tool_input = {"command": event.event_summary[:200]}
    tool_id = f"qhpc-{event.event_identifier[:12]}"
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_id,
                    "name": tool_name,
                    "input": tool_input,
                }
            ]
        },
        "_qhpc_bridge": {
            "agent_name": event.agent_name,
            "task_identifier": event.task_identifier,
            "event_type": event.event_type,
            "qhpc_event_id": event.event_identifier,
            "status_label": event.status_label,
        },
    }


def export_pixel_agents_compatible_trace(
    output_path: Union[str, Path],
    trace: ResearchSimulationTrace,
) -> None:
    """Write JSONL: one Claude-shaped line per research event (shim only)."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(map_research_event_to_pixel_agents_event(ev), ensure_ascii=False)
        for ev in trace.event_log
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def explain_pixel_agents_mapping() -> str:
    """Short markdown explanation for docs and CLI help."""
    return """## qhpc → Pixel Agents (shim)

- **Native Pixel Agents**: watches **Claude Code** JSONL under `~/.claude/projects/...` while you work in VS Code.
- **This bridge**: exports research workflow events as **separate** files under `outputs/research_workflow/` (see `run_research_workflow_demo.py`):
  - `research_workflow_trace.json` — full trace (qhpc schema v1)
  - `research_workflow_events.jsonl` — qhpc event rows
  - `research_workflow_pixel_shim.jsonl` — lines shaped like `assistant` + `tool_use` (for comparison or future tooling)
- **Manual step**: opening those files in Pixel Agents is **not** built-in; use them for review, custom scripts, or a future adapter.

See `docs/pixel_agents_audit.md` and `docs/pixel_agents_integration_decision.md`.
"""
