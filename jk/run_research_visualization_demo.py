#!/usr/bin/env python3
"""End-to-end research visualization demo: data loading, diagnostics, figures.

Run from ``jk/``::

    pip install -e ".[data-pipeline]"
    PYTHONPATH=src python3 run_research_visualization_demo.py

Outputs under ``outputs/research_visualization/``.
Degrades gracefully: skips any stage whose data source is unavailable and still
produces as many figures as possible.  A machine-readable ``summary.json`` and
human-readable ``summary.md`` are always written.
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
import time
import traceback
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import numpy as np

try:
    import pandas as pd
except ImportError:
    print("FATAL: pandas is required.  pip install -e '.[data-pipeline]'")
    sys.exit(1)

from qhpc_cache.config import PricingConfig, VisualizationConfig, get_visualization_config
from qhpc_cache.historical_returns import (
    align_return_panel,
    compute_log_returns,
    compute_rolling_volatility,
    compute_simple_returns,
)
from qhpc_cache.alpha_features import (
    moving_average_spread_feature,
    price_momentum_feature,
    realized_volatility_feature,
    rolling_z_score_feature,
    simple_mean_reversion_feature,
)
from qhpc_cache.alpha_evaluation import (
    compute_forward_returns,
    evaluate_feature_information_coefficient,
    summarize_feature_predictiveness,
)
from qhpc_cache.universe_analysis import normalize_ohlcv_panel
from qhpc_cache.visualization.plot_utils import apply_research_style, ensure_output_dirs
from qhpc_cache.visualization.market_overview import (
    plot_correlation_heatmap,
    plot_cumulative_returns,
    plot_rolling_volatility,
)
from qhpc_cache.visualization.microstructure_plots import (
    plot_event_window_response,
    plot_intraday_spread,
    plot_intraday_volume_profile,
)
from qhpc_cache.visualization.alpha_diagnostics import (
    plot_feature_correlation_heatmap,
    plot_feature_distributions,
    plot_signal_quantile_returns,
)
from qhpc_cache.visualization.simulation_comparison import (
    plot_distribution_comparison,
    plot_qq_comparison,
    plot_tail_comparison,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def _generate_synthetic_daily_panel(cfg: VisualizationConfig) -> pd.DataFrame:
    """Multi-symbol GBM panel for offline / fallback demos."""
    rng = np.random.default_rng(cfg.mc_seed)
    start = date.fromisoformat(cfg.start_date)
    end = date.fromisoformat(cfg.end_date)
    n_days = (end - start).days
    dates = pd.bdate_range(start=start, periods=min(n_days, cfg.lookback_days), freq="B")
    rows: List[Dict[str, Any]] = []
    for sym in cfg.symbols:
        price = 100.0 + rng.uniform(-20, 60)
        vol = 0.15 + rng.uniform(0, 0.25)
        drift = 0.04 + rng.uniform(-0.02, 0.06)
        for d in dates:
            z = rng.standard_normal()
            ret = (drift / 252) + vol / math.sqrt(252) * z
            price *= math.exp(ret)
            high = price * (1.0 + abs(rng.standard_normal()) * 0.005)
            low = price * (1.0 - abs(rng.standard_normal()) * 0.005)
            volume = int(rng.uniform(500_000, 5_000_000))
            rows.append({
                "date": d.strftime("%Y-%m-%d"),
                "symbol": sym,
                "open": round(price * (1.0 + rng.uniform(-0.002, 0.002)), 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(price, 4),
                "volume": volume,
            })
    return pd.DataFrame(rows)


def _generate_synthetic_intraday(symbol: str, n_ticks: int = 500, seed: int = 99) -> pd.DataFrame:
    """Synthetic tick-level data with spread, price, volume fields."""
    rng = np.random.default_rng(seed)
    mid = 150.0
    timestamps = pd.date_range("2024-03-15 09:30", periods=n_ticks, freq="1min")
    prices, spreads, volumes = [], [], []
    for i in range(n_ticks):
        mid += rng.standard_normal() * 0.02
        spread = max(0.01, 0.02 + rng.standard_normal() * 0.005)
        vol = int(max(10, rng.exponential(500)))
        prices.append(round(mid, 4))
        spreads.append(round(spread, 4))
        volumes.append(vol)
    return pd.DataFrame({
        "timestamp": timestamps[:n_ticks],
        "symbol": symbol,
        "price": prices,
        "spread": spreads,
        "volume": volumes,
    })


def _try_load_real_daily(cfg: VisualizationConfig, data_root: str) -> Optional[pd.DataFrame]:
    """Attempt to load daily OHLCV from registry or Databento."""
    try:
        from qhpc_cache.data_registry import load_dataset_registry
        from qhpc_cache.data_storage import load_saved_dataset

        entries = load_dataset_registry(data_root)
        daily_paths = []
        for e in entries:
            if e.dataset_kind == "daily_ohlcv":
                daily_paths.extend(e.local_paths)
        if not daily_paths:
            return None
        frames = []
        for p in daily_paths:
            path = Path(p)
            if path.exists():
                frames.append(load_saved_dataset(path))
        if not frames:
            return None
        panel = pd.concat(frames, ignore_index=True)
        panel = normalize_ohlcv_panel(panel)
        if "close" in panel.columns and "symbol" in panel.columns:
            return panel
        return None
    except Exception:
        return None


def _try_load_taq_event_window(cfg: VisualizationConfig) -> Optional[pd.DataFrame]:
    """Attempt one TAQ event-window extraction via the kdb adapter."""
    if not cfg.enable_taq:
        return None
    try:
        from qhpc_cache.taq_kdb_adapter import (
            default_kdb_taq_repo,
            kdb_backend_ready,
            discover_local_taq_datasets,
        )
        from qhpc_cache.data_sources import NyseTaqFileProvider

        ready, msg = kdb_backend_ready()
        if not ready:
            return None
        discovery = discover_local_taq_datasets()
        flat_files = discovery.get("flat_data_candidates", [])
        if not flat_files:
            return None
        repo = default_kdb_taq_repo()
        provider = NyseTaqFileProvider()
        first_file = repo / flat_files[0]
        if first_file.exists():
            return provider.load_taq_window(first_file)
        return None
    except Exception:
        return None


def _simulate_mc_returns(cfg: VisualizationConfig, n_samples: int = 10_000) -> np.ndarray:
    """Generate MC terminal-price returns using the repo's GBM simulator."""
    from qhpc_cache.market_models import simulate_gbm_terminal_price

    rng = np.random.default_rng(cfg.mc_seed)
    S0, r, sigma, T = 100.0, 0.05, 0.20, 1.0
    terminal_prices = []
    for _ in range(n_samples):
        z = rng.standard_normal()
        st = simulate_gbm_terminal_price(S0, r, sigma, T, z)
        terminal_prices.append(math.log(st / S0))
    return np.array(terminal_prices)


# ---------------------------------------------------------------------------
# Stage runners
# ---------------------------------------------------------------------------

def stage_daily_market(
    cfg: VisualizationConfig,
    dirs: Dict[str, Path],
    summary: Dict[str, Any],
) -> Optional[pd.DataFrame]:
    """Load / generate daily panel, compute returns and vol, plot market figures."""
    _section("Stage A: Daily Market Layer")

    data_root = os.environ.get("QHPC_DATA_ROOT", str(ROOT / "data" / "qhpc_data"))
    panel = _try_load_real_daily(cfg, data_root)
    source = "registry/databento"
    if panel is None:
        print("  [info] No registry daily data found; generating synthetic GBM panel.")
        panel = _generate_synthetic_daily_panel(cfg)
        source = "synthetic_gbm"
    summary["daily_source"] = source
    summary["daily_rows"] = len(panel)
    summary["daily_symbols"] = sorted(panel["symbol"].unique().tolist())

    returns_long = compute_log_returns(panel)
    wide = align_return_panel(returns_long)
    vol = compute_rolling_volatility(wide, cfg.rolling_vol_window)

    figures_done: List[str] = []
    try:
        meta = plot_cumulative_returns(wide, output_path=dirs["market"] / "cumulative_returns.png")
        figures_done.append(meta["path"])
        print(f"  [ok] {meta['filename']}")
    except Exception as exc:
        print(f"  [warn] cumulative returns plot failed: {exc}")

    try:
        meta = plot_rolling_volatility(vol, output_path=dirs["market"] / "rolling_volatility.png")
        figures_done.append(meta["path"])
        print(f"  [ok] {meta['filename']}")
    except Exception as exc:
        print(f"  [warn] rolling volatility plot failed: {exc}")

    try:
        meta = plot_correlation_heatmap(
            wide, max_symbols=cfg.max_symbols_corr,
            output_path=dirs["market"] / "correlation_heatmap.png",
        )
        figures_done.append(meta["path"])
        print(f"  [ok] {meta['filename']}")
    except Exception as exc:
        print(f"  [warn] correlation heatmap failed: {exc}")

    summary["market_figures"] = figures_done
    return panel


def stage_microstructure(
    cfg: VisualizationConfig,
    dirs: Dict[str, Path],
    summary: Dict[str, Any],
) -> None:
    """Attempt TAQ / intraday extraction and plot microstructure diagnostics."""
    _section("Stage B: Microstructure / Intraday Layer")

    taq_frame = _try_load_taq_event_window(cfg)
    source = "kdb_taq"
    if taq_frame is None:
        print("  [info] TAQ extraction unavailable; using synthetic intraday data.")
        taq_frame = _generate_synthetic_intraday(cfg.symbols[0] if cfg.symbols else "SPY")
        source = "synthetic_intraday"
    summary["microstructure_source"] = source

    figures_done: List[str] = []
    ts_col = "timestamp" if "timestamp" in taq_frame.columns else taq_frame.columns[0]

    if "spread" in taq_frame.columns:
        try:
            meta = plot_intraday_spread(
                taq_frame[ts_col], taq_frame["spread"],
                output_path=dirs["microstructure"] / "intraday_spread.png",
            )
            figures_done.append(meta["path"])
            print(f"  [ok] {meta['filename']}")
        except Exception as exc:
            print(f"  [warn] intraday spread plot failed: {exc}")

    if "volume" in taq_frame.columns:
        try:
            n_bins = min(50, len(taq_frame))
            binned_vol = taq_frame["volume"].values[:n_bins * (len(taq_frame) // n_bins)]
            binned_vol = binned_vol.reshape(-1, max(1, len(taq_frame) // n_bins)).sum(axis=1)
            meta = plot_intraday_volume_profile(
                list(range(len(binned_vol))), binned_vol,
                output_path=dirs["microstructure"] / "intraday_volume_profile.png",
            )
            figures_done.append(meta["path"])
            print(f"  [ok] {meta['filename']}")
        except Exception as exc:
            print(f"  [warn] intraday volume profile failed: {exc}")

    if "price" in taq_frame.columns and "volume" in taq_frame.columns:
        try:
            meta = plot_event_window_response(
                taq_frame[ts_col], taq_frame["price"], taq_frame["volume"],
                event_label=f"Event Window ({cfg.symbols[0] if cfg.symbols else 'SPY'})",
                output_path=dirs["microstructure"] / "event_window_response.png",
            )
            figures_done.append(meta["path"])
            print(f"  [ok] {meta['filename']}")
        except Exception as exc:
            print(f"  [warn] event window response plot failed: {exc}")

    summary["microstructure_figures"] = figures_done


def stage_alpha(
    cfg: VisualizationConfig,
    panel: pd.DataFrame,
    dirs: Dict[str, Path],
    summary: Dict[str, Any],
) -> None:
    """Compute alpha features and plot diagnostics."""
    _section("Stage C: Alpha / Feature Diagnostics")

    figures_done: List[str] = []
    feature_cols: List[str] = []

    try:
        panel = price_momentum_feature(panel, lookback=21)
        feature_cols.append("momentum")
    except Exception:
        pass
    try:
        panel = moving_average_spread_feature(panel, fast_window=10, slow_window=50)
        feature_cols.append("ma_spread")
    except Exception:
        pass
    try:
        panel = rolling_z_score_feature(panel, value_column="close", window=60)
        feature_cols.append("z_score")
    except Exception:
        pass
    try:
        mr = simple_mean_reversion_feature(panel, lookback=21)
        if "mean_reversion" in mr.columns:
            panel["mean_reversion"] = mr["mean_reversion"].values
            feature_cols.append("mean_reversion")
    except Exception:
        pass

    if feature_cols:
        try:
            meta = plot_feature_distributions(
                panel, feature_columns=feature_cols,
                output_path=dirs["alpha"] / "feature_distributions.png",
            )
            figures_done.append(meta.get("path", ""))
            print(f"  [ok] feature_distributions.png")
        except Exception as exc:
            print(f"  [warn] feature distributions plot failed: {exc}")

        try:
            meta = plot_feature_correlation_heatmap(
                panel, feature_columns=feature_cols,
                output_path=dirs["alpha"] / "feature_correlation.png",
            )
            figures_done.append(meta.get("path", ""))
            print(f"  [ok] feature_correlation.png")
        except Exception as exc:
            print(f"  [warn] feature correlation heatmap failed: {exc}")

    if "momentum" in panel.columns:
        try:
            returns_long = compute_simple_returns(panel)
            wide_simple = align_return_panel(returns_long, value_column="simple_return")
            fwd = compute_forward_returns(wide_simple, horizon=cfg.alpha_forward_horizon)
            mom_wide = panel.pivot_table(index="date", columns="symbol", values="momentum", aggfunc="first")
            common_idx = mom_wide.index.intersection(fwd.index)
            common_cols = mom_wide.columns.intersection(fwd.columns)
            if len(common_idx) > 10 and len(common_cols) > 1:
                mom_vals = mom_wide.loc[common_idx, common_cols].values.ravel()
                fwd_vals = fwd.loc[common_idx, common_cols].values.ravel()
                mask = np.isfinite(mom_vals) & np.isfinite(fwd_vals)
                meta = plot_signal_quantile_returns(
                    mom_vals[mask], fwd_vals[mask],
                    n_quantiles=cfg.alpha_quantile_buckets,
                    signal_name="Momentum",
                    output_path=dirs["alpha"] / "signal_quantile_returns.png",
                )
                figures_done.append(meta.get("path", ""))
                print(f"  [ok] signal_quantile_returns.png")

                ic = evaluate_feature_information_coefficient(
                    mom_wide.loc[common_idx, common_cols],
                    fwd.loc[common_idx, common_cols],
                )
                pred = summarize_feature_predictiveness(ic)
                summary["alpha_ic_summary"] = pred
                print(f"  [info] Momentum IC: mean={pred['mean_ic']:.4f}  hit_rate={pred['hit_rate']:.2f}")
        except Exception as exc:
            print(f"  [warn] signal vs forward return analysis failed: {exc}")

    summary["alpha_features_computed"] = feature_cols
    summary["alpha_figures"] = [f for f in figures_done if f]


def stage_simulation_comparison(
    cfg: VisualizationConfig,
    panel: pd.DataFrame,
    dirs: Dict[str, Path],
    summary: Dict[str, Any],
) -> None:
    """Compare historical returns to MC-simulated distribution."""
    _section("Stage D: Simulation Comparison")

    figures_done: List[str] = []
    returns_long = compute_log_returns(panel)
    wide = align_return_panel(returns_long)
    hist_rets = wide.values.ravel()
    hist_rets = hist_rets[np.isfinite(hist_rets)]

    mc_rets = _simulate_mc_returns(cfg, n_samples=cfg.mc_paths_for_sim_comparison)

    try:
        meta = plot_distribution_comparison(
            hist_rets, mc_rets,
            output_path=dirs["simulation"] / "hist_vs_sim_distribution.png",
        )
        figures_done.append(meta["path"])
        print(f"  [ok] hist_vs_sim_distribution.png")
    except Exception as exc:
        print(f"  [warn] distribution comparison failed: {exc}")

    try:
        meta = plot_qq_comparison(
            hist_rets, mc_rets,
            output_path=dirs["simulation"] / "qq_comparison.png",
        )
        figures_done.append(meta.get("path", ""))
        print(f"  [ok] qq_comparison.png")
    except Exception as exc:
        print(f"  [warn] QQ comparison failed: {exc}")

    try:
        meta = plot_tail_comparison(
            hist_rets, mc_rets,
            output_path=dirs["simulation"] / "tail_comparison.png",
        )
        figures_done.append(meta.get("path", ""))
        print(f"  [ok] tail_comparison.png")
    except Exception as exc:
        print(f"  [warn] tail comparison failed: {exc}")

    summary["simulation_figures"] = [f for f in figures_done if f]


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def write_summary(
    dirs: Dict[str, Path],
    summary: Dict[str, Any],
    start_time: float,
) -> None:
    """Write summary.json and summary.md."""
    elapsed = time.time() - start_time
    summary["total_runtime_seconds"] = round(elapsed, 2)
    summary["finished_at_utc"] = _utc_now_iso()

    json_path = dirs["summaries"] / "summary.json"
    json_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    all_figs = (
        summary.get("market_figures", [])
        + summary.get("microstructure_figures", [])
        + summary.get("alpha_figures", [])
        + summary.get("simulation_figures", [])
    )

    md_lines = [
        "# Research Visualization Run Summary",
        "",
        f"- **Started**: {summary.get('started_at_utc', 'n/a')}",
        f"- **Finished**: {summary.get('finished_at_utc', 'n/a')}",
        f"- **Runtime**: {elapsed:.1f}s",
        "",
        "## Data Sources",
        f"- Daily: {summary.get('daily_source', 'none')} ({summary.get('daily_rows', 0)} rows, {len(summary.get('daily_symbols', []))} symbols)",
        f"- Microstructure: {summary.get('microstructure_source', 'none')}",
        "",
        "## Figures Produced",
    ]
    if all_figs:
        for fig in all_figs:
            md_lines.append(f"- {fig}")
    else:
        md_lines.append("- (none)")
    md_lines.append("")
    md_lines.append("## Alpha")
    md_lines.append(f"- Features: {summary.get('alpha_features_computed', [])}")
    ic = summary.get("alpha_ic_summary", {})
    if ic:
        md_lines.append(f"- Momentum IC: mean={ic.get('mean_ic', 0):.4f}, hit_rate={ic.get('hit_rate', 0):.2f}")
    md_lines.append("")

    failures = summary.get("failures", [])
    if failures:
        md_lines.append("## Failures")
        for f in failures:
            md_lines.append(f"- {f}")
    else:
        md_lines.append("## Failures\n- (none)")

    md_path = dirs["summaries"] / "summary.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"\n  Summary: {json_path}")
    print(f"  Summary: {md_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    start_time = time.time()
    cfg = get_visualization_config()
    apply_research_style()

    base = Path(cfg.output_root)
    dirs = ensure_output_dirs(base)

    summary: Dict[str, Any] = {
        "started_at_utc": _utc_now_iso(),
        "config": {
            "symbols": cfg.symbols,
            "start_date": cfg.start_date,
            "end_date": cfg.end_date,
            "enable_databento": cfg.enable_databento,
            "enable_taq": cfg.enable_taq,
        },
        "failures": [],
    }

    panel: Optional[pd.DataFrame] = None
    try:
        panel = stage_daily_market(cfg, dirs, summary)
    except Exception as exc:
        msg = f"Daily market stage failed: {exc}"
        print(f"  [ERROR] {msg}")
        summary["failures"].append(msg)

    try:
        stage_microstructure(cfg, dirs, summary)
    except Exception as exc:
        msg = f"Microstructure stage failed: {exc}"
        print(f"  [ERROR] {msg}")
        summary["failures"].append(msg)

    if panel is not None:
        try:
            stage_alpha(cfg, panel, dirs, summary)
        except Exception as exc:
            msg = f"Alpha stage failed: {exc}"
            print(f"  [ERROR] {msg}")
            summary["failures"].append(msg)

        try:
            stage_simulation_comparison(cfg, panel, dirs, summary)
        except Exception as exc:
            msg = f"Simulation comparison stage failed: {exc}"
            print(f"  [ERROR] {msg}")
            summary["failures"].append(msg)
    else:
        summary["failures"].append("No daily panel available; alpha and simulation stages skipped.")

    _section("Run Summary")
    write_summary(dirs, summary, start_time)

    all_figs = (
        summary.get("market_figures", [])
        + summary.get("microstructure_figures", [])
        + summary.get("alpha_figures", [])
        + summary.get("simulation_figures", [])
    )
    print(f"\n  Total figures: {len(all_figs)}")
    print(f"  Failures: {len(summary.get('failures', []))}")
    print(f"  Output root: {base.resolve()}")
    print()


if __name__ == "__main__":
    main()
