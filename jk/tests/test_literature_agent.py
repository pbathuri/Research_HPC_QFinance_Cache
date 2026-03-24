"""Tests for the literature agent and research expansion system."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from qhpc_cache.literature_agent import (
    Hypothesis,
    PaperEntry,
    ResearchQueue,
    export_hypothesis_map,
    export_module_literature_links,
    export_paper_index,
    get_hypothesis_map,
    get_paper_index,
    register_hypothesis,
    register_paper,
    run_literature_expansion,
    seed_core_hypotheses,
    seed_core_references,
)


class TestPaperIndex(unittest.TestCase):

    def test_seed_core_references(self) -> None:
        seed_core_references()
        papers = get_paper_index()
        self.assertGreater(len(papers), 5)
        ids = {p.paper_id for p in papers}
        self.assertIn("glasserman2003", ids)
        self.assertIn("frigo1999", ids)

    def test_register_paper(self) -> None:
        register_paper(PaperEntry("test001", "Test Paper", ["Author A"], 2024))
        self.assertTrue(any(p.paper_id == "test001" for p in get_paper_index()))


class TestHypotheses(unittest.TestCase):

    def test_seed_core_hypotheses(self) -> None:
        seed_core_hypotheses()
        hyps = get_hypothesis_map()
        self.assertGreater(len(hyps), 0)
        self.assertTrue(any(h.hypothesis_id == "H1" for h in hyps))


class TestResearchQueue(unittest.TestCase):

    def test_add_and_pending(self) -> None:
        q = ResearchQueue()
        q.add(item_type="paper", item_id="p1", priority=3, reason="test")
        q.add(item_type="experiment", item_id="e1", priority=1, reason="urgent")
        pending = q.pending()
        self.assertEqual(len(pending), 2)
        self.assertEqual(pending[0]["item_id"], "e1")


class TestExport(unittest.TestCase):

    def test_run_literature_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_literature_expansion(Path(tmp))
            self.assertTrue(Path(paths["paper_index"]).exists())
            self.assertTrue(Path(paths["hypothesis_map"]).exists())
            self.assertTrue(Path(paths["research_queue"]).exists())
            self.assertTrue(Path(paths["module_literature_links"]).exists())
            data = json.loads(Path(paths["paper_index"]).read_text())
            self.assertIsInstance(data, list)
            self.assertGreater(len(data), 5)


if __name__ == "__main__":
    unittest.main()
