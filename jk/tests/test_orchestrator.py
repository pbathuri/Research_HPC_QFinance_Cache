"""Tests for the agentic orchestrator."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from qhpc_cache.orchestrator import (
    AgentNode,
    LANGGRAPH_AVAILABLE,
    PipelineState,
    ResearchOrchestrator,
    RunMode,
    build_default_pipeline,
    build_langgraph_pipeline,
)


def _ok_agent(state: PipelineState) -> PipelineState:
    state.metrics["test_ran"] = True
    return state


def _fail_agent(state: PipelineState) -> PipelineState:
    raise RuntimeError("deliberate test failure")


class TestPipelineState(unittest.TestCase):

    def test_mark_done(self) -> None:
        s = PipelineState(run_id="t1")
        s.mark_done("stage_a", ["/tmp/a.txt"])
        self.assertTrue(s.is_done("stage_a"))
        self.assertEqual(s.artifacts["stage_a"], ["/tmp/a.txt"])

    def test_mark_failed(self) -> None:
        s = PipelineState(run_id="t1")
        s.mark_failed("stage_b", "test error")
        self.assertIn("stage_b", s.failed_stages)


class TestOrchestrator(unittest.TestCase):

    def test_simple_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["QHPC_METRICS_DIR"] = os.path.join(tmp, "metrics")
            try:
                orch = ResearchOrchestrator(run_id="test_simple")
                orch.add_agent(AgentNode("step_a", "TestAgent", _ok_agent))
                state = orch.run()
                self.assertIn("step_a", state.completed_stages)
                self.assertTrue(state.metrics.get("test_ran"))
            finally:
                os.environ.pop("QHPC_METRICS_DIR", None)

    def test_failure_handling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["QHPC_METRICS_DIR"] = os.path.join(tmp, "metrics")
            try:
                orch = ResearchOrchestrator(run_id="test_fail")
                orch.add_agent(AgentNode("bad_step", "FailAgent", _fail_agent, retry_limit=0))
                orch.add_agent(AgentNode("next_step", "TestAgent", _ok_agent))
                state = orch.run()
                self.assertIn("bad_step", state.failed_stages)
                self.assertIn("next_step", state.completed_stages)
            finally:
                os.environ.pop("QHPC_METRICS_DIR", None)

    def test_selected_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["QHPC_METRICS_DIR"] = os.path.join(tmp, "metrics")
            try:
                orch = ResearchOrchestrator(run_id="test_select")
                orch.add_agent(AgentNode("a", "A", _ok_agent))
                orch.add_agent(AgentNode("b", "B", _ok_agent))
                state = orch.run(selected_stages={"b"})
                self.assertNotIn("a", state.completed_stages)
                self.assertIn("b", state.completed_stages)
            finally:
                os.environ.pop("QHPC_METRICS_DIR", None)

    def test_metrics_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["QHPC_METRICS_DIR"] = os.path.join(tmp, "metrics")
            try:
                orch = ResearchOrchestrator(run_id="test_metrics")
                orch.add_agent(AgentNode("x", "X", _ok_agent))
                state = orch.run()
                self.assertIn("x", state.completed_stages)
                self.assertTrue(state.metrics.get("test_ran"))
            finally:
                os.environ.pop("QHPC_METRICS_DIR", None)


class TestBuildDefaultPipeline(unittest.TestCase):

    def test_default_has_nodes(self) -> None:
        orch = build_default_pipeline(run_id="test_default")
        self.assertGreater(len(orch._nodes), 3)
        names = {n.name for n in orch._nodes}
        self.assertIn("environment_check", names)
        self.assertIn("reporting", names)


class TestLangGraphIntegration(unittest.TestCase):

    def test_langgraph_detection(self) -> None:
        self.assertIsInstance(LANGGRAPH_AVAILABLE, bool)

    @unittest.skipUnless(LANGGRAPH_AVAILABLE, "langgraph not installed")
    def test_langgraph_pipeline_builds(self) -> None:
        orch = build_langgraph_pipeline(mode=RunMode.FULL)
        self.assertEqual(type(orch).__name__, "LangGraphOrchestrator")
        self.assertTrue(hasattr(orch, "state"))
        self.assertTrue(hasattr(orch, "run"))

    @unittest.skipUnless(LANGGRAPH_AVAILABLE, "langgraph not installed")
    def test_langgraph_pipeline_runs_env_check(self) -> None:
        """Run only the fast environment_check stage to verify LangGraph wiring."""
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["QHPC_METRICS_DIR"] = os.path.join(tmp, "metrics")
            os.environ["QHPC_OUTPUT_ROOT"] = os.path.join(tmp, "outputs")
            try:
                orch = build_langgraph_pipeline(mode=RunMode.FULL)
                state = orch.run(selected_stages={"environment_check", "reporting"})
                self.assertIn("environment_check", state.completed_stages)
            finally:
                os.environ.pop("QHPC_METRICS_DIR", None)
                os.environ.pop("QHPC_OUTPUT_ROOT", None)

    def test_fallback_without_langgraph(self) -> None:
        orch = build_default_pipeline(mode=RunMode.FULL)
        self.assertIsInstance(orch, ResearchOrchestrator)


if __name__ == "__main__":
    unittest.main()
