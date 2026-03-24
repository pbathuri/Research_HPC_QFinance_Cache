"""Tests for the visualization subpackage and run_research_visualization_demo helpers."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import numpy as np

try:
    import pandas as pd
except ImportError:
    pd = None

import matplotlib
matplotlib.use("Agg")

from qhpc_cache.config import VisualizationConfig, get_visualization_config
from qhpc_cache.visualization.plot_utils import ensure_output_dirs, save_figure


class TestOutputDirs(unittest.TestCase):
    """Verify that ensure_output_dirs creates the expected tree."""

    def test_creates_all_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "viz_test"
            dirs = ensure_output_dirs(base)
            self.assertTrue(dirs["root"].is_dir())
            self.assertTrue(dirs["market"].is_dir())
            self.assertTrue(dirs["microstructure"].is_dir())
            self.assertTrue(dirs["alpha"].is_dir())
            self.assertTrue(dirs["simulation"].is_dir())
            self.assertTrue(dirs["optional_traces"].is_dir())
            self.assertTrue(dirs["summaries"].is_dir())


class TestSaveFigure(unittest.TestCase):
    """save_figure should write a PNG and return metadata."""

    def test_save_and_meta(self) -> None:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], [1, 4, 9])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test_fig.png"
            meta = save_figure(fig, path)
            self.assertEqual(meta["status"], "ok")
            self.assertTrue(Path(meta["path"]).is_file())
            self.assertGreater(Path(meta["path"]).stat().st_size, 0)


class TestVisualizationConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = get_visualization_config()
        self.assertIsInstance(cfg, VisualizationConfig)
        self.assertGreater(len(cfg.symbols), 0)
        self.assertTrue(cfg.output_root)


@unittest.skipIf(pd is None, "pandas not available")
class TestMarketPlots(unittest.TestCase):
    """Smoke-test market plots with small synthetic data."""

    def _make_wide(self) -> "pd.DataFrame":
        rng = np.random.default_rng(42)
        dates = pd.bdate_range("2024-01-01", periods=60)
        data = rng.standard_normal((60, 3)) * 0.01
        return pd.DataFrame(data, index=dates, columns=["A", "B", "C"])

    def test_cumulative_returns(self) -> None:
        from qhpc_cache.visualization.market_overview import plot_cumulative_returns

        with tempfile.TemporaryDirectory() as tmp:
            meta = plot_cumulative_returns(
                self._make_wide(),
                output_path=Path(tmp) / "cum.png",
            )
            self.assertEqual(meta["status"], "ok")
            self.assertTrue(Path(meta["path"]).is_file())

    def test_rolling_volatility(self) -> None:
        from qhpc_cache.visualization.market_overview import plot_rolling_volatility

        with tempfile.TemporaryDirectory() as tmp:
            wide = self._make_wide()
            vol = wide.rolling(10, min_periods=3).std()
            meta = plot_rolling_volatility(
                vol, output_path=Path(tmp) / "vol.png",
            )
            self.assertEqual(meta["status"], "ok")

    def test_correlation_heatmap(self) -> None:
        from qhpc_cache.visualization.market_overview import plot_correlation_heatmap

        with tempfile.TemporaryDirectory() as tmp:
            meta = plot_correlation_heatmap(
                self._make_wide(), output_path=Path(tmp) / "corr.png",
            )
            self.assertEqual(meta["status"], "ok")


@unittest.skipIf(pd is None, "pandas not available")
class TestAlphaPlots(unittest.TestCase):
    def test_feature_distributions(self) -> None:
        from qhpc_cache.visualization.alpha_diagnostics import plot_feature_distributions

        rng = np.random.default_rng(7)
        df = pd.DataFrame({"f1": rng.standard_normal(200), "f2": rng.uniform(size=200)})
        with tempfile.TemporaryDirectory() as tmp:
            meta = plot_feature_distributions(
                df, feature_columns=["f1", "f2"],
                output_path=Path(tmp) / "dist.png",
            )
            self.assertEqual(meta["status"], "ok")

    def test_signal_quantile_insufficient(self) -> None:
        from qhpc_cache.visualization.alpha_diagnostics import plot_signal_quantile_returns

        meta = plot_signal_quantile_returns(
            np.array([1.0, 2.0]), np.array([0.01, -0.01]),
            n_quantiles=5,
        )
        self.assertEqual(meta["status"], "insufficient_data")


class TestSimulationPlots(unittest.TestCase):
    def test_distribution_comparison(self) -> None:
        from qhpc_cache.visualization.simulation_comparison import plot_distribution_comparison

        rng = np.random.default_rng(9)
        with tempfile.TemporaryDirectory() as tmp:
            meta = plot_distribution_comparison(
                rng.standard_normal(300), rng.standard_normal(300),
                output_path=Path(tmp) / "comp.png",
            )
            self.assertEqual(meta["status"], "ok")

    def test_qq_comparison(self) -> None:
        from qhpc_cache.visualization.simulation_comparison import plot_qq_comparison

        rng = np.random.default_rng(11)
        with tempfile.TemporaryDirectory() as tmp:
            meta = plot_qq_comparison(
                rng.standard_normal(200), rng.standard_normal(200),
                output_path=Path(tmp) / "qq.png",
            )
            self.assertEqual(meta["status"], "ok")


class TestGracefulDegradation(unittest.TestCase):
    """Verify that missing sources don't crash the orchestration helpers."""

    def test_try_load_real_daily_missing(self) -> None:
        sys.path.insert(0, str(ROOT))
        from run_research_visualization_demo import _try_load_real_daily

        cfg = get_visualization_config()
        result = _try_load_real_daily(cfg, "/nonexistent/path")
        self.assertIsNone(result)

    def test_try_load_taq_disabled(self) -> None:
        sys.path.insert(0, str(ROOT))
        from run_research_visualization_demo import _try_load_taq_event_window

        cfg = get_visualization_config()
        cfg.enable_taq = False
        result = _try_load_taq_event_window(cfg)
        self.assertIsNone(result)


@unittest.skipIf(pd is None, "pandas not available")
class TestSummaryArtifact(unittest.TestCase):
    """Verify that summary files are always written."""

    def test_write_summary(self) -> None:
        sys.path.insert(0, str(ROOT))
        import time as _time
        from run_research_visualization_demo import write_summary

        with tempfile.TemporaryDirectory() as tmp:
            dirs = ensure_output_dirs(Path(tmp) / "viz")
            summary: dict = {
                "started_at_utc": "2024-01-01T00:00:00+00:00",
                "market_figures": ["/tmp/a.png"],
                "microstructure_figures": [],
                "alpha_figures": [],
                "simulation_figures": [],
                "failures": [],
            }
            write_summary(dirs, summary, _time.time() - 5.0)
            self.assertTrue((dirs["summaries"] / "summary.json").is_file())
            self.assertTrue((dirs["summaries"] / "summary.md").is_file())
            data = json.loads((dirs["summaries"] / "summary.json").read_text())
            self.assertIn("total_runtime_seconds", data)


if __name__ == "__main__":
    unittest.main()
