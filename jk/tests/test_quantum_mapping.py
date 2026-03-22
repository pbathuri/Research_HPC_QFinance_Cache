"""Quantum mapping abstractions."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache.pricing import MonteCarloPricer
from qhpc_cache.quantum_workflow import run_quantum_mapping_workflow


class TestQuantumMapping(unittest.TestCase):
    def test_bundle_shapes(self):
        pricer = MonteCarloPricer(
            S0=100.0,
            K=100.0,
            r=0.05,
            sigma=0.2,
            T=1.0,
            num_paths=100,
            payoff_type="european_call",
        )
        bundle = run_quantum_mapping_workflow(pricer, request_identifier="t")
        self.assertEqual(bundle.finance_problem.payoff_type, "european_call")
        self.assertTrue(bundle.circuit_request.finance_problem_key.startswith("monte_carlo_option"))


if __name__ == "__main__":
    unittest.main()
