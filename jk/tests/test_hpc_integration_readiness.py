"""HPC integration-readiness tests (Slurm-first, no fake execution)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from qhpc_cache.qmc_simulation import QMCSimulationConfig, run_qmc_simulation


class TestHpcDeferredQmc(unittest.TestCase):
    def test_qmc_deferred_to_hpc_generates_submission_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "qmc_simulation"
            cfg = QMCSimulationConfig(
                output_dir=str(out_dir),
                requested_backend="bigred200_mpi_batch",
                execution_deferred_to_hpc=True,
                slurm_nodes=2,
                slurm_ntasks=64,
                slurm_cpus_per_task=1,
                slurm_walltime="02:00:00",
            )
            summary = run_qmc_simulation(cfg)

            self.assertTrue(summary["execution_deferred_to_hpc"])
            self.assertEqual(summary["requested_backend"], "bigred200_mpi_batch")
            self.assertEqual(summary["executed_backend"], "none_deferred_to_hpc")
            self.assertEqual(summary["execution_environment"], "hpc")
            self.assertTrue(summary["hpc_ready"])
            self.assertTrue(summary["mpi_ready"])
            manifest_path = Path(summary["slurm_job_manifest_path"])
            self.assertTrue(manifest_path.exists())

            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["backend"], "slurm_bigred200")
            self.assertTrue(payload["execution_deferred_to_hpc"])
            self.assertIn("submit_command", payload)


if __name__ == "__main__":
    unittest.main()

