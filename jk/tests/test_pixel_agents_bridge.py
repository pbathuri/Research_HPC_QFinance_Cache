"""Tests for optional Pixel Agents bridge (exporters + adapter)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "pixel_agents_bridge"))

from qhpc_cache.research_agents import build_demo_simulation_trace

import pixel_agents_adapter
import trace_exporter


class TestPixelAgentsBridge(unittest.TestCase):
    def test_export_json_roundtrip_keys(self):
        trace = build_demo_simulation_trace()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.json"
            trace_exporter.export_research_trace_to_json(path, trace)
            data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], "1.0")
        self.assertIn("event_log", data)

    def test_jsonl_line_count(self):
        trace = build_demo_simulation_trace()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "e.jsonl"
            trace_exporter.export_research_trace_to_jsonl(path, trace)
            lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        self.assertEqual(len(lines), len(trace.event_log))

    def test_pixel_shim_assistant_shape(self):
        trace = build_demo_simulation_trace()
        first = trace.event_log[0]
        row = pixel_agents_adapter.map_research_event_to_pixel_agents_event(first)
        self.assertEqual(row["type"], "assistant")
        self.assertIn("tool_use", str(row["message"]["content"]))

    def test_inspect_format_has_transcript_hint(self):
        info = pixel_agents_adapter.inspect_pixel_agents_expected_format()
        self.assertIn("transcriptParser", info["source"])

    def test_integration_module(self):
        from qhpc_cache.integrations.pixel_agents_integration import (
            compatibility_note,
            describe_visualization_integration,
        )

        d = describe_visualization_integration()
        self.assertIn("bridge_directory", d)
        self.assertTrue(len(compatibility_note()) > 20)


if __name__ == "__main__":
    unittest.main()
