"""Circuit cache store tests."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qhpc_cache.circuit_cache import CircuitCacheEntry, CircuitCacheStore
from qhpc_cache.quantum_mapping import (
    build_finance_problem_descriptor_from_pricing_request,
    build_quantum_circuit_request,
    build_quantum_estimation_task,
    estimate_quantum_resources_placeholder,
)


class TestCircuitCache(unittest.TestCase):
    def test_put_get_roundtrip(self):
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
        req = build_quantum_circuit_request(finance, task, "rid")
        res = estimate_quantum_resources_placeholder(req, task)
        store = CircuitCacheStore()
        key = store.build_exact_cache_key(req, finance)
        entry = CircuitCacheEntry(
            cache_key=key,
            circuit_request=req,
            compiled_representation_placeholder="placeholder",
            resource_estimate=res,
            reuse_count=0,
            last_access_step=0,
            source_label="test",
        )
        store.put_exact_match(entry)
        self.assertTrue(store.has_exact_match(key))
        fetched = store.get_exact_match(key)
        self.assertEqual(fetched.cache_key, key)


if __name__ == "__main__":
    unittest.main()
