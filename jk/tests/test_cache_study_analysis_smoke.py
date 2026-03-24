"""Smoke tests for cache-study analysis layer."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest


class TestCacheStudyAnalysisSmoke(unittest.TestCase):
    def test_run_and_export_cache_study(self):
        import pandas as pd

        from qhpc_cache.cache_study_analysis import export_cache_study_analysis, run_cache_study_analysis

        rows = []
        specs = [
            ("set_a_covid_crash", "covid_crash", "d-1_to_d+1", "none", 10107, 0.98, 14, 120.0),
            ("set_b_march_2020_liquidity", "march_2020_liquidity_stress", "d-5_to_d+5", "full_day", 20001, 0.95, 18, 140.0),
            ("set_c_2022_rate_shock", "2022_rate_shock", "d-10_to_d+10", "none", 84788, 0.94, 12, 90.0),
            ("set_d_2023_banking_stress", "banking_stress_2023", "d-20_to_d+20", "centered_2h_stress", 55555, 0.92, 16, 160.0),
            ("set_e_broad_institutional_stress_library", "covid_crash", "d-5_to_d+5", "first_trading_hour", 10107, 0.97, 15, 130.0),
        ]
        for sid, eid, wf, intraday, permno, aq, jw, tm in specs:
            for i in range(3):
                rows.append(
                    {
                        "event_set_id": sid,
                        "event_id": eid,
                        "event_label": eid,
                        "category_label": "crisis / regime stress" if "covid" in eid else "macro / rates",
                        "window_family_label": wf,
                        "intraday_slice_label": intraday,
                        "permno": permno + i,
                        "symbol": "SPY",
                        "symbol_root": "SPY",
                        "window_start": "2020-01-01T14:30:00+00:00",
                        "window_end": "2020-01-02T20:00:00+00:00",
                        "event_time_start": "2020-01-01T14:30:00+00:00",
                        "event_time_end": "2020-01-02T20:00:00+00:00",
                        "alignment_match_quality": aq,
                        "source_datasets": "taq_kdb;wrds_link;crsp",
                        "row_count": 1,
                        "join_width": jw,
                        "normalization_schema_version": "1.0",
                        "stage_timing_ms": tm + i,
                        "normalized_window_id": f"{sid}_{eid}_{wf}",
                        "join_pattern_id": f"jp_{sid}_{jw}",
                        "derived_structure_id": f"ds_{sid}_{wf}",
                    }
                )

        normalized = pd.DataFrame(rows)
        analysis = run_cache_study_analysis(normalized_event_rows=normalized, record_observability=False)
        self.assertIn("within_set_summary", analysis)
        self.assertIn("cross_set_summary", analysis)
        self.assertEqual(len(analysis["within_set_summary"]), 5)
        self.assertEqual(len(analysis["rankings"]), 5)

        with tempfile.TemporaryDirectory() as tmp:
            paths = export_cache_study_analysis(
                analysis_result=analysis,
                output_dir=tmp,
            )
            self.assertIn("cache_study_within_set_summary_csv", paths)
            self.assertTrue(Path(paths["cache_study_within_set_summary_csv"]).exists())
            self.assertTrue(Path(paths["cache_study_analysis_manifest_json"]).exists())


if __name__ == "__main__":
    unittest.main()
