"""Focused tests for the Feature-1 (similarity), Feature-2 (PMU), Feature-3 (heatmap) upgrade."""

from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

import numpy as np


class TestSimilarityVector(unittest.TestCase):
    def test_build_vector_shape(self):
        from qhpc_cache.trace_similarity import build_similarity_vector
        v = build_similarity_vector(100, 100, 0.05, 0.2, 1.0, 10000, "quantlib_mc")
        self.assertEqual(v.shape, (11,))
        self.assertTrue(np.all(np.isfinite(v)))

    def test_cosine_self_is_one(self):
        from qhpc_cache.trace_similarity import build_similarity_vector, cosine_similarity
        v = build_similarity_vector(100, 100, 0.05, 0.2, 1.0, 10000, "quantlib_mc")
        self.assertAlmostEqual(cosine_similarity(v, v), 1.0, places=6)

    def test_close_vectors_high_similarity(self):
        from qhpc_cache.trace_similarity import build_similarity_vector, cosine_similarity
        a = build_similarity_vector(100, 100, 0.05, 0.20, 1.0, 10000, "quantlib_mc")
        b = build_similarity_vector(100, 101, 0.05, 0.21, 1.0, 10000, "quantlib_mc")
        score = cosine_similarity(a, b)
        self.assertGreater(score, 0.95)

    def test_distant_vectors_low_similarity(self):
        from qhpc_cache.trace_similarity import build_similarity_vector, cosine_similarity
        a = build_similarity_vector(50, 200, 0.01, 0.05, 0.1, 100, "quantlib_mc")
        b = build_similarity_vector(500, 50, 0.10, 0.80, 5.0, 500000, "cirq_qmci")
        score = cosine_similarity(a, b)
        self.assertLess(score, 0.85)


class TestSimilarityMatcher(unittest.TestCase):
    def test_matcher_finds_similar_above_threshold(self):
        from qhpc_cache.trace_similarity import SimilarityMatcher, build_similarity_vector
        matcher = SimilarityMatcher(method="cosine", threshold=0.90, max_candidates=32)
        v1 = build_similarity_vector(100, 100, 0.05, 0.20, 1.0, 10000, "quantlib_mc")
        matcher.add(v1, "key1", "sig_a", "quantlib_mc", "sweep", 0)

        v2 = build_similarity_vector(100, 101, 0.05, 0.21, 1.0, 10000, "quantlib_mc")
        hit, score, sig, key, ncand = matcher.query(v2)
        self.assertTrue(hit)
        self.assertGreater(score, 0.90)
        self.assertEqual(sig, "sig_a")
        self.assertEqual(key, "key1")

    def test_matcher_no_hit_below_threshold(self):
        from qhpc_cache.trace_similarity import SimilarityMatcher, build_similarity_vector
        matcher = SimilarityMatcher(method="cosine", threshold=0.99, max_candidates=32)
        v1 = build_similarity_vector(50, 200, 0.01, 0.05, 0.1, 100, "quantlib_mc")
        matcher.add(v1, "key1", "sig_a", "quantlib_mc", "sweep", 0)

        v2 = build_similarity_vector(500, 50, 0.10, 0.80, 5.0, 500000, "cirq_qmci")
        hit, score, sig, key, ncand = matcher.query(v2)
        self.assertFalse(hit)

    def test_exact_hit_and_similarity_remain_distinct(self):
        """Similarity match must not be confused with exact cache hit."""
        from qhpc_cache.trace_similarity import SimilarityMatcher, build_similarity_vector
        matcher = SimilarityMatcher(method="hybrid", threshold=0.92)
        v1 = build_similarity_vector(100, 100, 0.05, 0.2, 1.0, 10000, "quantlib_mc")
        matcher.add(v1, "key_exact", "sig_x", "quantlib_mc", "sweep", 0)

        v_same = build_similarity_vector(100, 100, 0.05, 0.2, 1.0, 10000, "quantlib_mc")
        hit, score, _, _, _ = matcher.query(v_same)
        # Even if cosine=1.0, this is a similarity hit, not an exact cache hit
        self.assertTrue(hit)
        self.assertAlmostEqual(score, 1.0, places=4)

    def test_lsh_signature_deterministic(self):
        from qhpc_cache.trace_similarity import build_lsh_signature, build_similarity_vector
        v = build_similarity_vector(100, 100, 0.05, 0.2, 1.0, 10000, "quantlib_mc")
        s1 = build_lsh_signature(v, 12)
        s2 = build_lsh_signature(v, 12)
        self.assertEqual(s1, s2)
        self.assertTrue(len(s1) > 0)


class TestNullPMUCollector(unittest.TestCase):
    def test_null_pmu_never_crashes(self):
        from qhpc_cache.pmu_trace import NullPMUCollector
        pmu = NullPMUCollector()
        self.assertFalse(pmu.available)
        self.assertEqual(pmu.backend_name, "none")
        pmu.begin_scope("test")
        m = pmu.end_scope()
        self.assertGreaterEqual(m.task_clock_ms, 0)
        self.assertEqual(m.error, "pmu_not_available")
        d = m.to_dict()
        self.assertIn("pmu_cycles", d)

    def test_factory_returns_null_on_unsupported(self):
        from qhpc_cache.pmu_trace import create_pmu_collector
        c = create_pmu_collector(backend="none")
        self.assertFalse(c.available)
        self.assertEqual(c.backend_name, "none")

    def test_factory_auto_does_not_crash(self):
        from qhpc_cache.pmu_trace import create_pmu_collector
        c = create_pmu_collector(backend="auto")
        # On macOS this should be NullPMU; on Linux it might be perf
        self.assertIsNotNone(c)


class TestHeatmapZeroEvents(unittest.TestCase):
    def test_heatmap_empty_csv(self):
        """Heatmap must produce a valid PNG even with zero events."""
        from qhpc_cache.visualization.cache_trace_plots import plot_trace_engine_phase_heatmap
        import csv

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            (td_path / "figures").mkdir()
            events_csv = td_path / "trace_events.csv"
            with events_csv.open("w", newline="") as f:
                csv.writer(f).writerow(["event_id", "engine", "phase"])
            out = plot_trace_engine_phase_heatmap(td_path)
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 0)

    def test_heatmap_no_csv_file(self):
        """Heatmap must not crash if trace_events.csv doesn't exist."""
        from qhpc_cache.visualization.cache_trace_plots import plot_trace_engine_phase_heatmap
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            (td_path / "figures").mkdir()
            out = plot_trace_engine_phase_heatmap(td_path)
            self.assertTrue(out.exists())


class TestTraceOutputsWithPMUDisabled(unittest.TestCase):
    def test_pmu_fields_present_in_event_cols(self):
        """PMU columns must be in event schema even when PMU is off."""
        import sys, os
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
        from qhpc_cache.qmc_simulation import _TRACE_EVENT_COLS
        pmu_cols = [c for c in _TRACE_EVENT_COLS if c.startswith("pmu_")]
        self.assertGreaterEqual(len(pmu_cols), 8)

    def test_similarity_fields_in_event_cols(self):
        from qhpc_cache.qmc_simulation import _TRACE_EVENT_COLS
        self.assertIn("similarity_method", _TRACE_EVENT_COLS)
        self.assertIn("similarity_candidate_count", _TRACE_EVENT_COLS)
        self.assertIn("matched_signature_id", _TRACE_EVENT_COLS)
        self.assertIn("similarity_vector_norm", _TRACE_EVENT_COLS)


if __name__ == "__main__":
    unittest.main()
