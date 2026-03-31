"""Focused control-plane truthfulness and provenance tests."""

from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestPipelineCLIContract(unittest.TestCase):
    def test_help_exits_without_running_pipeline(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / "run_full_research_pipeline.py"
        self.assertTrue(script_path.exists())

        with tempfile.TemporaryDirectory() as td:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(repo_root / "src")
            env["QHPC_OUTPUT_ROOT"] = str(Path(td) / "outputs")
            proc = subprocess.run(
                [sys.executable, str(script_path), "--help"],
                cwd=str(repo_root),
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("usage:", proc.stdout.lower())
            self.assertFalse((Path(td) / "outputs").exists())


class TestLatestRunResolver(unittest.TestCase):
    def test_resolve_latest_by_mtime_not_name(self) -> None:
        from qhpc_cache.run_artifacts import resolve_latest_output_run

        with tempfile.TemporaryDirectory() as td:
            out_root = Path(td)
            run_a = out_root / "Output_99999999_999999"
            run_b = out_root / "Output_00000000_000000"
            run_a.mkdir()
            run_b.mkdir()

            # Lexically run_a > run_b, but mtime makes run_b latest.
            os.utime(run_a, (100.0, 100.0))
            os.utime(run_b, (200.0, 200.0))
            latest = resolve_latest_output_run(out_root)
            self.assertIsNotNone(latest)
            self.assertEqual(latest, run_b)


class TestCacheTimingRowSemantics(unittest.TestCase):
    def test_cache_access_log_has_explicit_row_semantics(self) -> None:
        from qhpc_cache.cache_store import SimpleCacheStore

        store = SimpleCacheStore(enable_logging=True)
        features = {"engine": "classical_mc", "S0": 100.0, "K": 100.0, "T": 1.0}
        store.put(features, {"price": 10.0, "std_error": 0.5}, compute_time_ms=1.5)
        store.get(features, engine_name="classical_mc")

        with tempfile.TemporaryDirectory() as td:
            csv_path = store.flush_access_log_csv(Path(td) / "cache_access_log.csv")
            with csv_path.open("r", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertGreaterEqual(len(rows), 2)
        for required_col in (
            "lookup_time_ms",
            "pricing_compute_time_ms",
            "stage_elapsed_ms",
            "row_semantics",
        ):
            self.assertIn(required_col, rows[0])

        put_rows = [r for r in rows if r.get("operation") == "put"]
        lookup_rows = [r for r in rows if r.get("operation") == "lookup"]
        self.assertTrue(put_rows)
        self.assertTrue(lookup_rows)
        self.assertEqual(put_rows[0].get("row_semantics"), "put_single_compute_result")
        self.assertEqual(lookup_rows[0].get("row_semantics"), "lookup_single_attempt")


class TestFeatureCondensationStatus(unittest.TestCase):
    def test_feature_condensation_status_written_when_skipped(self) -> None:
        from qhpc_cache.qmc_simulation import QMCSimulationConfig, run_qmc_simulation

        with tempfile.TemporaryDirectory() as td:
            cfg = QMCSimulationConfig(
                budget_minutes=0.01,
                enforce_budget=False,
                output_dir=td,
                live_dashboard=False,
                trace_full_mode=False,
                gan_epochs=1,
                gan_num_days=1,
                gan_num_assets=1,
                portfolio_size=1,
                convergence_contracts=1,
                convergence_path_counts=[256],
                max_phase_contracts=1,
                max_pricings_total=1,
                engine_allowlist=["classical_mc"],
            )
            summary = run_qmc_simulation(cfg)
            cond = summary.get("feature_condensation", {})
            self.assertIn("condensation_status", cond)
            self.assertIn("condensation_reason", cond)
            self.assertIn("input_row_count", cond)
            self.assertIn("output_row_count", cond)
            self.assertIn("pyqmc_engine", summary.get("optional_capabilities", {}))

            feature_csv = Path(summary["csv_files"]["feature_condensation"])
            with feature_csv.open("r", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertGreaterEqual(len(rows), 1)
            self.assertIn("condensation_status", rows[-1])
            self.assertTrue(rows[-1].get("condensation_status"))


if __name__ == "__main__":
    unittest.main()

