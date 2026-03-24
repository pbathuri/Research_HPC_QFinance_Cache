"""Smoke tests for canonical event-library comparison layer."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest


class TestEventSetLibrary(unittest.TestCase):
    def test_locked_sets_present(self):
        from qhpc_cache.event_set_library import canonical_event_set_library

        sets = canonical_event_set_library()
        self.assertEqual(len(sets), 5)
        ids = {s.event_set_id for s in sets}
        self.assertIn("set_a_covid_crash", ids)
        self.assertIn("set_e_broad_institutional_stress_library", ids)

    def test_set_e_has_balanced_categories(self):
        from qhpc_cache.event_set_library import canonical_event_set_library

        set_e = [s for s in canonical_event_set_library() if s.event_set_id == "set_e_broad_institutional_stress_library"][0]
        cats = {m.category_label for m in set_e.members}
        self.assertIn("crisis / regime stress", cats)
        self.assertIn("macro / rates", cats)
        self.assertIn("banking / credit stress", cats)
        self.assertIn("liquidity dislocation", cats)
        self.assertIn("earnings shock", cats)
        self.assertIn("commodity / inflation shock", cats)

    def test_set_e_ruleset_size_and_review(self):
        from qhpc_cache.event_set_library import (
            canonical_event_set_library,
            set_e_manual_review_summary,
        )

        set_e = [s for s in canonical_event_set_library() if s.event_set_id == "set_e_broad_institutional_stress_library"][0]
        self.assertGreaterEqual(len(set_e.members), 35)
        self.assertLessEqual(len(set_e.members), 40)

        review = set_e_manual_review_summary()
        self.assertTrue(review["composition_checks"]["within_target_range"])
        self.assertTrue(review["composition_checks"]["all_required_categories_present"])
        self.assertTrue(review["composition_checks"]["macro_crisis_overweight"])
        self.assertGreater(review["macro_plus_crisis_share"], 0.50)


class TestEventLibraryCompare(unittest.TestCase):
    def test_run_and_export_comparison(self):
        import pandas as pd

        from qhpc_cache.event_library_compare import export_event_library_comparison, run_event_set_comparison

        raw = pd.DataFrame(
            [
                {
                    "qhpc_event_identifier": "covid_crash",
                    "qhpc_event_label": "COVID-19 global equity crash",
                    "window_family_label": "d-1_to_d+1",
                    "intraday_slice_label": "none",
                    "permno": 10107,
                    "symbol": "SPY",
                    "window_start_utc": "2020-03-12T14:30:00+00:00",
                    "window_end_utc": "2020-03-16T20:00:00+00:00",
                    "alignment_match_quality": 0.98,
                    "source_datasets": "taq_kdb;wrds_link;crsp",
                    "join_width": 14,
                    "stage_timing_ms": 121.5,
                },
                {
                    "qhpc_event_identifier": "2022_rate_shock",
                    "qhpc_event_label": "2022 policy-rate shock / duration sell-off",
                    "window_family_label": "d-5_to_d+5",
                    "intraday_slice_label": "none",
                    "permno": 84788,
                    "symbol": "TLT",
                    "window_start_utc": "2022-06-08T14:30:00+00:00",
                    "window_end_utc": "2022-06-22T20:00:00+00:00",
                    "alignment_match_quality": 0.94,
                    "source_datasets": "taq_kdb;wrds_link;crsp",
                    "join_width": 12,
                    "stage_timing_ms": 88.1,
                },
            ]
        )

        result = run_event_set_comparison(raw_event_rows=raw)
        self.assertIn("event_window_manifest", result)
        self.assertIn("workload_signature_summary", result)
        self.assertGreater(len(result["event_window_manifest"]), 0)
        self.assertGreater(len(result["workload_signature_summary"]), 0)

        with tempfile.TemporaryDirectory() as tmp:
            paths = export_event_library_comparison(comparison_result=result, output_dir=tmp)
            self.assertIn("event_window_manifest_csv", paths)
            self.assertTrue(Path(paths["event_window_manifest_csv"]).exists())


if __name__ == "__main__":
    unittest.main()
