"""Tests for the QMC simulation harness and CSV writer."""

import tempfile
import unittest
from pathlib import Path

from qhpc_cache.qmc_simulation import (
    QMCSimulationConfig,
    QMCSimulationCSVWriter,
    SimulationBudget,
    _detect_pattern,
    _generate_contracts,
)
import numpy as np


class TestSimulationBudget(unittest.TestCase):
    def test_budget_tracking(self):
        b = SimulationBudget(10.0)
        self.assertFalse(b.exhausted)
        self.assertGreater(b.remaining, 9.0)
        self.assertGreater(b.phase_budget("gan"), 0)

    def test_phase_budgets_sum_to_one(self):
        b = SimulationBudget(100.0)
        total = sum(b.phase_budgets.values())
        self.assertAlmostEqual(total, 1.0, delta=0.01)


class TestCSVWriter(unittest.TestCase):
    def test_creates_files(self):
        with tempfile.TemporaryDirectory() as td:
            w = QMCSimulationCSVWriter(Path(td))
            self.assertTrue(w.sim_log_path.exists())
            self.assertTrue(w.cache_pattern_path.exists())
            self.assertTrue(w.feature_path.exists())

    def test_log_simulation(self):
        with tempfile.TemporaryDirectory() as td:
            w = QMCSimulationCSVWriter(Path(td))
            w.log_simulation({"timestamp": 123, "engine": "test", "price": 10.0})
            lines = w.sim_log_path.read_text().strip().split("\n")
            self.assertEqual(len(lines), 2)

    def test_log_cache_pattern(self):
        with tempfile.TemporaryDirectory() as td:
            w = QMCSimulationCSVWriter(Path(td))
            w.log_cache_pattern({"timestamp": 1, "window_id": 1, "exact_hit_rate": 0.5})
            lines = w.cache_pattern_path.read_text().strip().split("\n")
            self.assertEqual(len(lines), 2)


class TestContractGeneration(unittest.TestCase):
    def test_generates_correct_count(self):
        rng = np.random.default_rng(42)
        contracts = _generate_contracts(rng, 20)
        self.assertEqual(len(contracts), 20)
        self.assertIn("S0", contracts[0])
        self.assertIn("contract_id", contracts[0])

    def test_parameter_ranges(self):
        rng = np.random.default_rng(0)
        contracts = _generate_contracts(rng, 100)
        for c in contracts:
            self.assertGreater(c["S0"], 0)
            self.assertGreater(c["K"], 0)
            self.assertGreater(c["sigma"], 0)


class TestPatternDetection(unittest.TestCase):
    def test_insufficient_data(self):
        result = _detect_pattern([True, False], window=50)
        self.assertEqual(result["pattern_type"], "insufficient")

    def test_high_reuse(self):
        hits = [True] * 100
        result = _detect_pattern(hits, window=50)
        self.assertIn(result["pattern_type"], ("high_reuse", "burst"))

    def test_random_pattern(self):
        rng = np.random.default_rng(42)
        hits = [rng.random() < 0.2 for _ in range(200)]
        result = _detect_pattern(hits, window=50)
        self.assertIn(result["pattern_type"], ("random", "burst", "periodic"))


if __name__ == "__main__":
    unittest.main()
