"""Tests for backend interface templates."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from qhpc_cache.backends.base import BackendCapabilities, ExecutionPlan
from qhpc_cache.backends.cpu_local import CpuLocalBackend
from qhpc_cache.backends.cuda_placeholder import CudaPlaceholderBackend
from qhpc_cache.backends.mpi_placeholder import MpiPlaceholderBackend
from qhpc_cache.backends.slurm_bigred200 import SlurmBigRed200Backend


class TestCpuLocal(unittest.TestCase):
    def test_capabilities(self) -> None:
        b = CpuLocalBackend()
        cap = b.capabilities()
        self.assertTrue(cap.can_execute)
        self.assertEqual(cap.name, "cpu_local")
        self.assertGreater(cap.max_parallel_paths, 0)

    def test_validate(self) -> None:
        self.assertTrue(CpuLocalBackend().validate())

    def test_build_and_execute(self) -> None:
        b = CpuLocalBackend()
        plan = b.build_plan("monte_carlo", {"num_paths": 1000})
        self.assertEqual(plan.backend_name, "cpu_local")
        result = b.execute(plan)
        self.assertEqual(result["status"], "ok")

    def test_dry_run(self) -> None:
        b = CpuLocalBackend()
        plan = b.build_plan("monte_carlo", {"num_paths": 5000}, dry_run=True)
        result = b.execute(plan)
        self.assertEqual(result["status"], "dry_run")


class TestCudaPlaceholder(unittest.TestCase):
    def test_cannot_execute(self) -> None:
        b = CudaPlaceholderBackend()
        self.assertFalse(b.capabilities().can_execute)
        self.assertTrue(b.capabilities().supports_gpu)

    def test_execute_returns_not_implemented(self) -> None:
        b = CudaPlaceholderBackend()
        plan = b.build_plan("monte_carlo", {"num_paths": 100_000})
        result = b.execute(plan)
        self.assertEqual(result["status"], "not_implemented")

    def test_dry_run_summary(self) -> None:
        b = CudaPlaceholderBackend()
        plan = b.build_plan("pricing", {"num_paths": 1_000_000})
        summary = b.dry_run_summary(plan)
        self.assertIn("cuda_placeholder", summary)
        self.assertIn("GPU", summary)


class TestMpiPlaceholder(unittest.TestCase):
    def test_cannot_execute(self) -> None:
        self.assertFalse(MpiPlaceholderBackend().capabilities().can_execute)
        self.assertTrue(MpiPlaceholderBackend().capabilities().supports_mpi)

    def test_execute_returns_not_implemented(self) -> None:
        result = MpiPlaceholderBackend().execute(
            MpiPlaceholderBackend().build_plan("mc", {"num_paths": 100})
        )
        self.assertEqual(result["status"], "not_implemented")


class TestSlurmBigRed200(unittest.TestCase):
    def test_capabilities(self) -> None:
        cap = SlurmBigRed200Backend().capabilities()
        self.assertFalse(cap.can_execute)
        self.assertTrue(cap.supports_batch_scheduler)

    def test_template_generation(self) -> None:
        b = SlurmBigRed200Backend()
        plan = b.build_plan("monte_carlo", {"num_paths": 1_000_000, "nodes": 4})
        result = b.execute(plan)
        self.assertEqual(result["status"], "template_generated")
        self.assertIn("SBATCH", result["sbatch_script"])
        self.assertIn("qhpc", result["sbatch_script"])


if __name__ == "__main__":
    unittest.main()
