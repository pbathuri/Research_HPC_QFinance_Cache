"""Tests for kdb-taq adapter (no live q required)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from qhpc_cache.taq_kdb_adapter import (
    discover_local_taq_datasets,
    inspect_kdb_taq_repo,
    kdb_backend_ready,
)


class TestInspectKdbRepo(unittest.TestCase):
    def test_inspect_missing_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope"
            report = inspect_kdb_taq_repo(missing)
            self.assertFalse(report["exists"])

    def test_inspect_temp_with_q_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lib").mkdir()
            (root / "lib" / "load_taq.q").write_text("/ stub\n", encoding="utf-8")
            report = inspect_kdb_taq_repo(root)
            self.assertTrue(report["exists"])
            self.assertGreaterEqual(report["q_file_count"], 1)

    def test_discover_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "nyse_taq_loader.q").write_text("", encoding="utf-8")
            disc = discover_local_taq_datasets(root)
            self.assertTrue(any("nyse" in name for name in disc["candidate_q_scripts"]))


class TestKdbBackendReady(unittest.TestCase):
    def test_not_ready_without_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok, msg = kdb_backend_ready(Path(tmp) / "missing")
            self.assertFalse(ok)
            self.assertIn("not found", msg)


if __name__ == "__main__":
    unittest.main()
