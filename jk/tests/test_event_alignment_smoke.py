"""Smoke tests for CRSP+TAQ alignment and feature panel (no WRDS, no kdb)."""

from __future__ import annotations

import unittest


class TestEventAlignment(unittest.TestCase):
    def test_deterministic_label_stable(self):
        from qhpc_cache.event_alignment import deterministic_event_label

        a = deterministic_event_label(
            event_identifier="e1",
            window_start_iso="2020-03-01T14:00:00",
            window_end_iso="2020-03-01T15:00:00",
            symbols=["ZZZ", "AAA"],
        )
        b = deterministic_event_label(
            event_identifier="e1",
            window_start_iso="2020-03-01T14:00:00",
            window_end_iso="2020-03-01T15:00:00",
            symbols=["AAA", "ZZZ"],
        )
        self.assertEqual(a, b)

    def test_normalize_symbol_root(self):
        from qhpc_cache.event_alignment import normalize_taq_symbol_root

        self.assertEqual(normalize_taq_symbol_root("ibm"), "IBM")
        self.assertEqual(normalize_taq_symbol_root("brk.b"), "BRK")

    def test_align_taq_to_permno_synthetic(self):
        import pandas as pd

        from qhpc_cache.event_alignment import align_taq_window_to_crsp_permno

        taq = pd.DataFrame({"symbol": ["IBM", "MSFT", "XXX"], "px": [1, 2, 3]})
        tclink = pd.DataFrame({"sym_root": ["IBM", "MSFT"], "permno": [100, 200]})
        out, meta = align_taq_window_to_crsp_permno(
            taq,
            link_frames={"tclink": tclink, "taqmclink": None, "cusip_2010": None},
            taq_symbol_col="symbol",
        )
        self.assertIn("permno", out.columns)
        self.assertEqual(out.loc[0, "permno"], 100)
        self.assertTrue(meta["permno_match_rate"] > 0.5)


class TestFeaturePanelSmoke(unittest.TestCase):
    def test_build_daily_feature_panel(self):
        import pandas as pd

        from qhpc_cache.feature_panel import build_daily_feature_panel

        rows = []
        for perm, days in ((1, 80), (2, 80)):
            for i in range(days):
                rows.append(
                    {
                        "permno": perm,
                        "date": pd.Timestamp("2020-01-01") + pd.Timedelta(days=i),
                        "close": 100.0 + i * 0.1 + perm,
                        "volume": 1e6,
                    }
                )
        df = pd.DataFrame(rows)
        panel, feats = build_daily_feature_panel(df)
        self.assertIn("momentum", panel.columns)
        self.assertIn("rolling_vol", panel.columns)
        self.assertGreater(len(feats), 3)


if __name__ == "__main__":
    unittest.main()
