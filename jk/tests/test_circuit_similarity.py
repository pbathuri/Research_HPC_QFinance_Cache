"""Explainable similarity scoring."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache.circuit_similarity import compute_basic_circuit_similarity
from qhpc_cache.quantum_mapping import (
    build_finance_problem_descriptor_from_pricing_request,
    build_quantum_circuit_request,
    build_quantum_estimation_task,
)


class TestCircuitSimilarity(unittest.TestCase):
    def test_identical_requests_score_one(self):
        finance = build_finance_problem_descriptor_from_pricing_request(
            "x",
            "european_call",
            "gbm",
            1.0,
            100.0,
            0.2,
            0.05,
            1000,
            False,
        )
        task = build_quantum_estimation_task(finance)
        req = build_quantum_circuit_request(finance, task, "id")
        score, breakdown = compute_basic_circuit_similarity(req, req)
        self.assertAlmostEqual(score, 1.0, places=3)
        self.assertIn("circuit_family_match", breakdown.component_scores)


if __name__ == "__main__":
    unittest.main()
