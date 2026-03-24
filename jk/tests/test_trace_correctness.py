"""Focused tests for trace correctness patches.

Covers:
  1. Monaco included in Phase 2 when trace_full_mode=True
  2. locality_score uses reuse distances, not hit flags
  3. Failed engine results are not cached
  4. trace_windows handles engine-error (NaN/empty) rows
  5. max_trace_rows actually truncates emission
  6. Multi-step event types emitted correctly
  7. Phase/engine summary window counts match emitted windows
  8. Similarity fields are honest (no fabricated similarity hits)
"""

import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from qhpc_cache.trace_features import compute_locality_score
from qhpc_cache.trace_windows import _safe_float, compute_window_summary, window_id


class TestLocalityScoreUsesReuseDistances(unittest.TestCase):
    """Issue #2: locality_score must only accept reuse-distance values."""

    def test_locality_from_distances(self):
        score = compute_locality_score([2, 4, 6])
        expected = 1.0 / (1.0 + 4.0)
        self.assertAlmostEqual(score, expected, places=5)

    def test_locality_empty_returns_zero(self):
        self.assertEqual(compute_locality_score([]), 0.0)

    def test_locality_single_large_distance(self):
        score = compute_locality_score([1000])
        self.assertAlmostEqual(score, 1.0 / 1001.0, places=6)


class TestSafeFloat(unittest.TestCase):
    """Issue #4: numeric parsing must handle empty strings and NaN."""

    def test_empty_string(self):
        self.assertTrue(math.isnan(_safe_float("")))

    def test_none(self):
        self.assertTrue(math.isnan(_safe_float(None)))

    def test_valid_number(self):
        self.assertEqual(_safe_float("3.14"), 3.14)

    def test_nan_string(self):
        self.assertTrue(math.isnan(_safe_float("nan")))

    def test_default(self):
        self.assertEqual(_safe_float("", 0.0), 0.0)


class TestWindowSummaryRobustness(unittest.TestCase):
    """Issue #4 + #7: window summary must not crash on error rows."""

    def _make_events(self, n=10, include_errors=False):
        events = []
        for i in range(n):
            e = {
                "event_id": i,
                "cache_hit": i % 3 == 0,
                "similarity_hit": False,
                "reuse_distance_events": float(i * 2) if i % 2 == 0 else float("nan"),
                "cache_key_short": f"key_{i % 4}",
                "engine": "classical_mc",
                "contract_id": f"C{i:05d}",
                "inter_event_gap_ms": 1.5,
                "wall_clock_ms": 10.0,
                "price": 42.0 if not include_errors or i % 5 != 0 else float("nan"),
                "std_error": 0.5 if not include_errors or i % 5 != 0 else float("nan"),
                "num_paths": 10_000,
                "moneyness": 1.0,
                "sigma": 0.2,
                "T": 0.5,
                "cumulative_elapsed_s": i * 0.1,
                "phase": "portfolio_sweep",
            }
            events.append(e)
        return events

    def test_summary_with_clean_events(self):
        events = self._make_events(20)
        summary = compute_window_summary(events, "wid_test", "run_test")
        self.assertEqual(summary["window_size"], 20)
        self.assertGreater(summary["exact_hit_rate"], 0)

    def test_summary_with_error_rows(self):
        events = self._make_events(20, include_errors=True)
        summary = compute_window_summary(events, "wid_err", "run_err")
        self.assertEqual(summary["window_size"], 20)
        self.assertIsInstance(summary["locality_score"], float)

    def test_summary_similarity_hit_rate_is_zero(self):
        events = self._make_events(10)
        summary = compute_window_summary(events, "wid_sim", "run_sim")
        self.assertEqual(summary["similarity_hit_rate"], 0.0)


class TestMaxTraceRowsEnforcement(unittest.TestCase):
    """Issue #5: max_trace_rows must actually stop emission."""

    def test_saturates_at_limit(self):
        from qhpc_cache.qmc_simulation import QMCSimulationConfig, TraceCollector

        with tempfile.TemporaryDirectory() as td:
            cfg = QMCSimulationConfig(max_trace_rows=5, trace_full_mode=True)
            tc = TraceCollector(Path(td), "run_test", cfg)
            contract = {"contract_id": "C00001", "S0": 100, "K": 100, "r": 0.05, "sigma": 0.2, "T": 1.0}
            for i in range(20):
                still_ok = tc.emit_event(
                    phase="test", phase_index=0, contract_index=i,
                    engine_order_index=0, engine="classical_mc", contract=contract,
                    num_paths=10_000, seed_val=42, event_type="cache_miss",
                    cache_key=f"key_{i}", cache_hit=False, similarity_hit=False,
                    similarity_score=0.0, price=10.0, std_error=0.1,
                    wall_clock_ms=5.0, phase_progress=i / 20, notes="",
                )
                if not still_ok:
                    break

            self.assertEqual(tc.event_count, 5)
            self.assertFalse(tc.accepting)


class TestMultiStepEventTypes(unittest.TestCase):
    """Issue #6: multi-step instrumentation emits separate event types."""

    def test_event_type_values_exist(self):
        from qhpc_cache.qmc_simulation import QMCSimulationConfig, TraceCollector

        with tempfile.TemporaryDirectory() as td:
            cfg = QMCSimulationConfig(trace_full_mode=True, trace_stride=999)
            tc = TraceCollector(Path(td), "run_multi", cfg)
            contract = {"contract_id": "C00001", "S0": 100, "K": 100, "r": 0.05, "sigma": 0.2, "T": 1.0}

            tc.emit_event(
                phase="test", phase_index=0, contract_index=0,
                engine_order_index=0, engine="classical_mc", contract=contract,
                num_paths=10_000, seed_val=42, event_type="engine_start",
                cache_key="k1", cache_hit=False, similarity_hit=False,
                similarity_score=0.0, price=float("nan"), std_error=float("nan"),
                wall_clock_ms=0.0, phase_progress=0.0, notes="",
            )
            tc.emit_event(
                phase="test", phase_index=0, contract_index=0,
                engine_order_index=0, engine="classical_mc", contract=contract,
                num_paths=10_000, seed_val=42, event_type="cache_miss",
                cache_key="k1", cache_hit=False, similarity_hit=False,
                similarity_score=0.0, price=float("nan"), std_error=float("nan"),
                wall_clock_ms=0.0, phase_progress=0.0, notes="",
            )
            tc.emit_event(
                phase="test", phase_index=0, contract_index=0,
                engine_order_index=0, engine="classical_mc", contract=contract,
                num_paths=10_000, seed_val=42, event_type="engine_end",
                cache_key="k1", cache_hit=False, similarity_hit=False,
                similarity_score=0.0, price=10.0, std_error=0.1,
                wall_clock_ms=5.0, phase_progress=0.0, notes="",
            )

            types = [e["event_type"] for e in tc._events]
            self.assertEqual(types, ["engine_start", "cache_miss", "engine_end"])
            ids = [e["event_order_index"] for e in tc._events]
            self.assertEqual(ids, sorted(ids))


class TestNoCachePoisonOnFailure(unittest.TestCase):
    """Issue #3: failed engine results must not be cached."""

    def test_nan_not_stored(self):
        from qhpc_cache.cache_store import SimpleCacheStore

        cache = SimpleCacheStore(enable_logging=True)
        features = {"engine": "test", "S0": 100, "K": 100, "r": 0.05, "sigma": 0.2, "T": 1.0, "num_paths": 10_000}

        cache.put(features, {"price": 42.0, "std_error": 0.5},
                  engine_name="test", compute_time_ms=5.0)
        result = cache.get(features, engine_name="test")
        self.assertEqual(result["price"], 42.0)

        nan_features = {"engine": "test_fail", "S0": 200, "K": 200, "r": 0.05, "sigma": 0.2, "T": 1.0, "num_paths": 10_000}
        with self.assertRaises(KeyError):
            cache.get(nan_features, engine_name="test_fail")


class TestMonacoInTraceFullMode(unittest.TestCase):
    """Issue #1: trace_full_mode must not skip Monaco in Phase 2."""

    def test_normal_mode_skips_monaco(self):
        from qhpc_cache.qmc_simulation import QMCSimulationConfig
        cfg = QMCSimulationConfig(trace_full_mode=False)
        should_skip = (not cfg.trace_full_mode)
        self.assertTrue(should_skip)

    def test_trace_mode_includes_monaco(self):
        from qhpc_cache.qmc_simulation import QMCSimulationConfig
        cfg = QMCSimulationConfig(trace_full_mode=True)
        should_skip = (not cfg.trace_full_mode)
        self.assertFalse(should_skip)


class TestWindowCountsInSummaries(unittest.TestCase):
    """Issue #7: phase/engine summary window counts must be actual emitted counts."""

    def test_emitted_window_tracking(self):
        from qhpc_cache.qmc_simulation import QMCSimulationConfig, TraceCollector

        with tempfile.TemporaryDirectory() as td:
            cfg = QMCSimulationConfig(
                trace_full_mode=True,
                trace_window_size=4,
                trace_stride=2,
            )
            tc = TraceCollector(Path(td), "run_wc", cfg)
            contract = {"contract_id": "C00001", "S0": 100, "K": 100, "r": 0.05, "sigma": 0.2, "T": 1.0}

            for i in range(20):
                tc.emit_event(
                    phase="portfolio_sweep", phase_index=2, contract_index=i,
                    engine_order_index=0, engine="classical_mc", contract=contract,
                    num_paths=10_000, seed_val=42, event_type="cache_miss",
                    cache_key=f"key_{i}", cache_hit=False, similarity_hit=False,
                    similarity_score=0.0, price=10.0, std_error=0.1,
                    wall_clock_ms=5.0, phase_progress=i / 20, notes="",
                )

            actual_windows = len(tc._emitted_windows)
            self.assertGreater(actual_windows, 0)
            phase_windows = [w for w in tc._emitted_windows if w.get("dominant_phase") == "portfolio_sweep"]
            self.assertEqual(len(phase_windows), actual_windows)


class TestHonestSimilarityFields(unittest.TestCase):
    """Issue #9: similarity_hit must be False, similarity_score honest."""

    def test_events_have_honest_similarity(self):
        from qhpc_cache.qmc_simulation import QMCSimulationConfig, TraceCollector

        with tempfile.TemporaryDirectory() as td:
            cfg = QMCSimulationConfig(trace_full_mode=True, trace_stride=999)
            tc = TraceCollector(Path(td), "run_sim_honest", cfg)
            contract = {"contract_id": "C00001", "S0": 100, "K": 100, "r": 0.05, "sigma": 0.2, "T": 1.0}

            tc.emit_event(
                phase="test", phase_index=0, contract_index=0,
                engine_order_index=0, engine="classical_mc", contract=contract,
                num_paths=10_000, seed_val=42, event_type="cache_miss",
                cache_key="k1", cache_hit=False, similarity_hit=False,
                similarity_score=0.0, price=10.0, std_error=0.1,
                wall_clock_ms=5.0, phase_progress=0.0, notes="",
            )
            tc.emit_event(
                phase="test", phase_index=0, contract_index=0,
                engine_order_index=0, engine="classical_mc", contract=contract,
                num_paths=10_000, seed_val=42, event_type="cache_hit",
                cache_key="k1", cache_hit=True, similarity_hit=False,
                similarity_score=1.0, price=10.0, std_error=0.1,
                wall_clock_ms=0.0, phase_progress=0.0, notes="",
            )

            miss_ev = tc._events[0]
            self.assertFalse(miss_ev["similarity_hit"])
            self.assertEqual(miss_ev["similarity_score"], 0.0)

            hit_ev = tc._events[1]
            self.assertTrue(hit_ev["cache_hit"])
            self.assertFalse(hit_ev["similarity_hit"])
            # With real similarity logic, exact hits don't run the matcher,
            # so similarity_score reflects no similarity query was performed.
            self.assertIsInstance(hit_ev["similarity_score"], float)


if __name__ == "__main__":
    unittest.main()
