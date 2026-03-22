"""Pixel Agents visualization — **optional** pointers (no VS Code / Node dependency).

The finance library does not import ``tools/pixel_agents_bridge`` from here.
Use this module for discoverability and docstrings in IDEs.

**Live** Pixel Agents still requires Claude Code + the extension (see local
``pixel-agents`` repo). **Supplemental** traces: run ``run_research_workflow_demo.py``.
"""

from __future__ import annotations

from typing import Any, Dict

# Repository-relative locations (jk/ as cwd)
BRIDGE_DIRECTORY = "tools/pixel_agents_bridge"
WORKFLOW_DEMO_SCRIPT = "run_research_workflow_demo.py"
DEFAULT_OUTPUT_DIR = "outputs/research_workflow"


def describe_visualization_integration() -> Dict[str, Any]:
    """Structured summary for notebooks or CLI help text."""
    return {
        "workflow_model_module": "qhpc_cache.research_agents",
        "bridge_directory": BRIDGE_DIRECTORY,
        "demo_script": WORKFLOW_DEMO_SCRIPT,
        "default_output_dir": DEFAULT_OUTPUT_DIR,
        "docs": [
            "docs/pixel_agents_audit.md",
            "docs/pixel_agents_integration_decision.md",
            "docs/multiagent_visualization_workflow.md",
            "docs/local_resource_to_agent_mapping.md",
        ],
        "pixel_agents_live_requirement": "Claude Code CLI + VS Code extension (see ~/Desktop/pixel-agents/README.md)",
        "qhpc_export_role": "Event trace + optional Claude-shaped shim JSONL for human review or future adapters",
    }


def compatibility_note() -> str:
    """One paragraph for README-style copy."""
    return (
        "qhpc_cache exports research workflow JSON/JSONL via run_research_workflow_demo.py; "
        "Pixel Agents consumes live Claude Code transcripts by default. "
        "Treat bridge output as a parallel trace for reasoning, not an automatic Pixel Agents feed."
    )
