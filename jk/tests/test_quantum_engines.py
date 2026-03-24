"""Tests for quantum simulation engines."""

import unittest
import math

from qhpc_cache.quantum_engines.base_engine import SimulationEngine, SimulationResult


class TestSimulationResult(unittest.TestCase):
    def test_result_fields(self):
        r = SimulationResult(
            price=10.0, std_error=0.5, paths_used=1000, wall_clock_ms=50.0,
            engine_name="test", engine_type="classical_mc",
            cache_key="abc123",
        )
        self.assertEqual(r.price, 10.0)
        self.assertEqual(r.engine_type, "classical_mc")
        self.assertIsInstance(r.metadata, dict)


class TestQuantLibEngine(unittest.TestCase):
    def test_available(self):
        from qhpc_cache.quantum_engines.quantlib_engine import QuantLibEngine
        self.assertTrue(QuantLibEngine.available())

    def test_price_european_call(self):
        from qhpc_cache.quantum_engines.quantlib_engine import QuantLibEngine
        eng = QuantLibEngine()
        r = eng.price(S0=100, K=100, r=0.05, sigma=0.2, T=1.0, num_paths=10_000, seed=42)
        self.assertFalse(math.isnan(r.price))
        self.assertGreater(r.price, 0)
        self.assertGreater(r.wall_clock_ms, 0)
        self.assertEqual(r.engine_type, "quantlib_mc")

    def test_analytic_price(self):
        from qhpc_cache.quantum_engines.quantlib_engine import QuantLibEngine
        eng = QuantLibEngine()
        p = eng.analytic_price(S0=100, K=100, r=0.05, sigma=0.2, T=1.0)
        self.assertAlmostEqual(p, 10.45, delta=0.5)

    def test_cache_key_deterministic(self):
        from qhpc_cache.quantum_engines.base_engine import build_cache_key
        k1 = build_cache_key("quantlib_mc", 100, 100, 0.05, 0.2, 1.0, 10000)
        k2 = build_cache_key("quantlib_mc", 100, 100, 0.05, 0.2, 1.0, 10000)
        self.assertEqual(k1, k2)


class TestCirqEngine(unittest.TestCase):
    def test_available(self):
        from qhpc_cache.quantum_engines.cirq_engine import CirqEngine
        self.assertTrue(CirqEngine.available())

    def test_price(self):
        from qhpc_cache.quantum_engines.cirq_engine import CirqEngine
        eng = CirqEngine(n_qubits=4)
        r = eng.price(S0=100, K=100, r=0.05, sigma=0.2, T=1.0, num_paths=500)
        self.assertFalse(math.isnan(r.price))
        self.assertEqual(r.engine_type, "cirq_qmci")
        self.assertIn("gate_count", r.metadata)
        self.assertIn("circuit_depth", r.metadata)


class TestMonacoEngine(unittest.TestCase):
    def test_available(self):
        from qhpc_cache.quantum_engines.monaco_engine import MonacoEngine
        self.assertTrue(MonacoEngine.available())

    def test_price(self):
        from qhpc_cache.quantum_engines.monaco_engine import MonacoEngine
        eng = MonacoEngine()
        r = eng.price(S0=100, K=100, r=0.05, sigma=0.2, T=1.0, num_paths=500)
        self.assertFalse(math.isnan(r.price))
        self.assertEqual(r.engine_type, "monaco_mc")


class TestPyQMCEngine(unittest.TestCase):
    def test_available(self):
        from qhpc_cache.quantum_engines.pyqmc_engine import PyQMCEngine
        self.assertTrue(PyQMCEngine.available())


if __name__ == "__main__":
    unittest.main()
