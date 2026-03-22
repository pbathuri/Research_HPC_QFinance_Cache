#!/usr/bin/env python3
"""Simulate multi-role research workflow and export traces for optional visualization.

Writes under ``outputs/research_workflow/``:
  - ``research_workflow_trace.json`` — full trace (qhpc schema)
  - ``research_workflow_events.jsonl`` — one event per line
  - ``research_workflow_summary.txt`` — human-readable
  - ``research_workflow_pixel_shim.jsonl`` — Claude-shaped lines (see bridge README)

Requires: run from ``jk/`` with ``PYTHONPATH=src`` or rely on path inserts below.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "pixel_agents_bridge"))

from qhpc_cache.research_agents import (
    build_default_research_agent_profiles,
    build_default_research_task_set,
    build_demo_simulation_trace,
    summarize_research_workflow_state,
)

import pixel_agents_adapter
import trace_exporter


def main() -> None:
    out_dir = ROOT / "outputs" / "research_workflow"
    out_dir.mkdir(parents=True, exist_ok=True)

    agents = build_default_research_agent_profiles()
    tasks = build_default_research_task_set()
    trace = build_demo_simulation_trace()

    print("=" * 72)
    print("qhpc_cache — research workflow simulation (multi-agent model)")
    print("=" * 72)
    print(f"Agents modeled: {len(agents)}")
    for profile in agents:
        print(f"  • {profile.agent_name}: {profile.assigned_focus_area}")
    print()
    print(f"Tasks in catalog: {len(tasks)}")
    for task in tasks:
        print(f"  • [{task.task_stage}] {task.task_identifier}: {task.task_title}")
    print()
    print("Final workflow snapshot:")
    print(summarize_research_workflow_state(trace.workflow_state_snapshots[-1]))
    print()

    trace_exporter.export_research_trace_to_json(
        out_dir / "research_workflow_trace.json", trace
    )
    trace_exporter.export_research_trace_to_jsonl(
        out_dir / "research_workflow_events.jsonl", trace
    )
    trace_exporter.export_research_trace_summary(
        out_dir / "research_workflow_summary.txt", trace
    )
    pixel_agents_adapter.export_pixel_agents_compatible_trace(
        out_dir / "research_workflow_pixel_shim.jsonl", trace
    )

    print("Wrote:")
    for name in (
        "research_workflow_trace.json",
        "research_workflow_events.jsonl",
        "research_workflow_summary.txt",
        "research_workflow_pixel_shim.jsonl",
    ):
        print(f"  {out_dir / name}")
    print()
    print(pixel_agents_adapter.explain_pixel_agents_mapping())


if __name__ == "__main__":
    main()
