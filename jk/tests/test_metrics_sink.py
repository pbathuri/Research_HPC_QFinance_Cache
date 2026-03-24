"""Tests for the CSV metrics sink infrastructure."""

from __future__ import annotations

import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


class TestMetricsSink(unittest.TestCase):

    def test_runtime_metric_row_defaults(self) -> None:
        from qhpc_cache.metrics_sink import RuntimeMetricRow
        row = RuntimeMetricRow(run_id="test", stage="pricing")
        self.assertTrue(row.timestamp)
        self.assertEqual(row.status, "ok")

    def test_append_creates_file_with_header(self) -> None:
        from qhpc_cache.metrics_sink import RuntimeMetricRow, append_metric_row
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["QHPC_METRICS_DIR"] = tmp
            try:
                row = RuntimeMetricRow(run_id="t1", stage="test_stage", duration_seconds=1.5)
                path = append_metric_row("test_runtime.csv", row)
                self.assertTrue(path.exists())
                with path.open("r") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["run_id"], "t1")
                self.assertEqual(rows[0]["stage"], "test_stage")
            finally:
                os.environ.pop("QHPC_METRICS_DIR", None)

    def test_append_multiple_rows(self) -> None:
        from qhpc_cache.metrics_sink import CacheMetricRow, append_metric_row
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["QHPC_METRICS_DIR"] = tmp
            try:
                for i in range(3):
                    append_metric_row("cache.csv", CacheMetricRow(run_id=f"r{i}", policy_name="test"))
                path = Path(tmp) / "cache.csv"
                with path.open("r") as f:
                    rows = list(csv.DictReader(f))
                self.assertEqual(len(rows), 3)
            finally:
                os.environ.pop("QHPC_METRICS_DIR", None)

    def test_stage_timer(self) -> None:
        from qhpc_cache.metrics_sink import StageTimer
        import time
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["QHPC_METRICS_DIR"] = tmp
            try:
                with StageTimer(run_id="t", stage="sleep_test") as timer:
                    time.sleep(0.01)
                self.assertGreater(timer.elapsed, 0.005)
                self.assertIsNotNone(timer.row)
                self.assertEqual(timer.row.status, "ok")
            finally:
                os.environ.pop("QHPC_METRICS_DIR", None)


if __name__ == "__main__":
    unittest.main()
