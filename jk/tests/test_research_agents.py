"""Tests for research workflow simulation dataclasses (no live agents)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache.research_agents import (
    build_default_research_agent_profiles,
    build_default_research_task_set,
    build_demo_simulation_trace,
    create_research_task_event,
    simulation_trace_to_serializable,
    summarize_research_workflow_state,
)


class TestResearchAgents(unittest.TestCase):
    def test_default_profiles_have_expected_roles(self):
        profiles = build_default_research_agent_profiles()
        names = {p.agent_name for p in profiles}
        self.assertIn("FinanceModelAgent", names)
        self.assertIn("VisualizationAgent", names)
        self.assertGreaterEqual(len(profiles), 7)

    def test_default_tasks_reference_real_modules(self):
        tasks = build_default_research_task_set()
        modules = {m for t in tasks for m in t.related_module_names}
        self.assertIn("pricing.py", modules)

    def test_create_event_has_identifier(self):
        ev = create_research_task_event(
            agent_name="FinanceModelAgent",
            event_type="test",
            task_identifier="t1",
            active_file_path="x.py",
            event_summary="summary",
        )
        self.assertTrue(ev.event_identifier)
        self.assertEqual(ev.agent_name, "FinanceModelAgent")

    def test_demo_trace_serializable(self):
        trace = build_demo_simulation_trace()
        data = simulation_trace_to_serializable(trace)
        self.assertIn("event_log", data)
        self.assertGreater(len(trace.event_log), 0)
        self.assertGreater(len(trace.workflow_state_snapshots), 0)

    def test_summarize_state_non_empty(self):
        trace = build_demo_simulation_trace()
        text = summarize_research_workflow_state(trace.workflow_state_snapshots[0])
        self.assertIn("Workflow:", text)


if __name__ == "__main__":
    unittest.main()
