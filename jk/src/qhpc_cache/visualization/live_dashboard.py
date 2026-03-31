"""Live Matplotlib/Seaborn dashboard for QMC simulation monitoring.

Uses plt.ion() for non-blocking updates.  Reads from CSV files produced by
the QMC simulation harness and refreshes every ``update_interval`` seconds.
"""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

try:
    import matplotlib
    matplotlib.use("TkAgg")
except Exception:
    pass

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

try:
    import seaborn as sns
    SNS = True
except ImportError:
    SNS = False


def _read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r") as f:
        return list(csv.DictReader(f))


def _safe_float(val: str, default: float = 0.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


class LiveDashboard:
    """Six-panel dashboard updated in real time during simulation."""

    def __init__(self, output_dir: str = "outputs/qmc_simulation", update_interval: float = 5.0):
        self.output_dir = Path(output_dir)
        self.update_interval = update_interval
        self._fig = None
        self._axes = {}
        self._running = False

    def _setup_figure(self) -> None:
        if SNS:
            sns.set_theme(style="darkgrid", palette="deep")

        self._fig = plt.figure(figsize=(18, 11))
        self._fig.suptitle("QMC Simulation — Live Dashboard", fontsize=14, fontweight="bold", y=0.98)
        gs = gridspec.GridSpec(2, 3, figure=self._fig, hspace=0.35, wspace=0.3)

        self._axes = {
            "hit_rate": self._fig.add_subplot(gs[0, 0]),
            "reuse_dist": self._fig.add_subplot(gs[0, 1]),
            "feature_heatmap": self._fig.add_subplot(gs[0, 2]),
            "convergence": self._fig.add_subplot(gs[1, 0]),
            "working_set": self._fig.add_subplot(gs[1, 1]),
            "param_space": self._fig.add_subplot(gs[1, 2]),
        }

    def _update_hit_rate(self, sim_rows: List[Dict]) -> None:
        ax = self._axes["hit_rate"]
        ax.clear()
        ax.set_title("Cache Hit Rate Over Time", fontsize=10)

        engine_data: Dict[str, List] = {}
        for row in sim_rows:
            eng = row.get("engine", "?")
            engine_data.setdefault(eng, []).append(row.get("cache_hit", "False") == "True")

        for eng, hits in engine_data.items():
            if len(hits) < 5:
                continue
            window = 50
            rates = []
            for i in range(0, len(hits), max(1, len(hits) // 200)):
                chunk = hits[max(0, i - window):i + 1]
                rates.append(sum(chunk) / len(chunk) if chunk else 0)
            ax.plot(rates, label=eng, linewidth=1.5)

        ax.set_xlabel("Time (pricing calls)")
        ax.set_ylabel("Hit Rate")
        ax.set_ylim(-0.05, 1.05)
        ax.legend(fontsize=7, loc="upper right")

    def _update_reuse_dist(self, pattern_rows: List[Dict]) -> None:
        ax = self._axes["reuse_dist"]
        ax.clear()
        ax.set_title("Mean Reuse Distance", fontsize=10)

        dists = [_safe_float(r.get("mean_reuse_distance", "0")) for r in pattern_rows]
        if dists:
            ax.bar(range(len(dists)), dists, color="#4da6ff", alpha=0.7)
        ax.set_xlabel("Analysis Window")
        ax.set_ylabel("Mean Reuse Distance")

    def _update_feature_heatmap(self, feature_rows: List[Dict]) -> None:
        ax = self._axes["feature_heatmap"]
        ax.clear()
        ax.set_title("Feature Condensation", fontsize=10)

        if feature_rows:
            last = feature_rows[-1]
            cond_status = str(last.get("condensation_status", "")).strip().lower()
            if cond_status and cond_status != "executed":
                reason = str(last.get("condensation_reason", "")).strip()
                ax.text(
                    0.5,
                    0.6,
                    f"Condensation status: {cond_status}",
                    transform=ax.transAxes,
                    ha="center",
                    va="center",
                    fontsize=10,
                )
                ax.text(
                    0.5,
                    0.4,
                    reason if reason else "(no reason provided)",
                    transform=ax.transAxes,
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="gray",
                )
                return
            orig = int(_safe_float(last.get("original_dims", "5")))
            reduced = int(_safe_float(last.get("reduced_dims", "3")))
            var_exp = _safe_float(last.get("pca_variance_explained", "0"))
            collisions = int(_safe_float(last.get("cache_key_collisions", "0")))
            util = _safe_float(last.get("effective_cache_utilization", "0"))

            labels = ["Orig Dims", "Reduced", "Var Explained", "Collisions", "Utilization"]
            values = [orig, reduced, var_exp, collisions, util]
            colors = ["#4da6ff", "#00e5a0", "#b794f4", "#ff6b6b", "#ffa94d"]
            ax.barh(labels, values, color=colors)
            for i, v in enumerate(values):
                ax.text(v + 0.01, i, f"{v:.2f}" if isinstance(v, float) else str(v), va="center", fontsize=8)
        else:
            ax.text(0.5, 0.5, "Awaiting data...", transform=ax.transAxes, ha="center", va="center")

    def _update_convergence(self, sim_rows: List[Dict]) -> None:
        ax = self._axes["convergence"]
        ax.clear()
        ax.set_title("Price vs Path Count (Convergence)", fontsize=10)

        engine_paths: Dict[str, Dict[int, List[float]]] = {}
        for row in sim_rows:
            eng = row.get("engine", "?")
            paths = int(_safe_float(row.get("num_paths", "0")))
            price = _safe_float(row.get("price", "nan"))
            if paths > 0 and not np.isnan(price):
                engine_paths.setdefault(eng, {}).setdefault(paths, []).append(price)

        for eng, path_dict in engine_paths.items():
            xs = sorted(path_dict.keys())
            ys = [np.mean(path_dict[x]) for x in xs]
            errs = [np.std(path_dict[x]) for x in xs]
            if len(xs) > 1:
                ax.errorbar(xs, ys, yerr=errs, label=eng, marker="o", markersize=3, linewidth=1, capsize=2)

        ax.set_xlabel("Num Paths")
        ax.set_ylabel("Price")
        ax.set_xscale("log")
        ax.legend(fontsize=7, loc="upper right")

    def _update_working_set(self, pattern_rows: List[Dict]) -> None:
        ax = self._axes["working_set"]
        ax.clear()
        ax.set_title("Working Set Size Over Time", fontsize=10)

        ws = [int(_safe_float(r.get("working_set_size", "0"))) for r in pattern_rows]
        if ws:
            ax.fill_between(range(len(ws)), ws, alpha=0.3, color="#00e5a0")
            ax.plot(ws, color="#00e5a0", linewidth=1.5)
        ax.set_xlabel("Analysis Window")
        ax.set_ylabel("Unique Keys")

    def _update_param_space(self, sim_rows: List[Dict]) -> None:
        ax = self._axes["param_space"]
        ax.clear()
        ax.set_title("Parameter Space (sigma vs T)", fontsize=10)

        sigmas, ts, colors = [], [], []
        for row in sim_rows[-2000:]:
            s = _safe_float(row.get("sigma", "0"))
            t = _safe_float(row.get("T", "0"))
            hit = row.get("cache_hit", "False") == "True"
            if s > 0 and t > 0:
                sigmas.append(s)
                ts.append(t)
                colors.append("#00e5a0" if hit else "#ff6b6b")

        if sigmas:
            ax.scatter(sigmas, ts, c=colors, s=8, alpha=0.5)
        ax.set_xlabel("Volatility (sigma)")
        ax.set_ylabel("Maturity (T)")

    def refresh(self) -> None:
        if self._fig is None:
            self._setup_figure()

        sim_rows = _read_csv(self.output_dir / "qmc_simulation_log.csv")
        pattern_rows = _read_csv(self.output_dir / "qmc_cache_patterns.csv")
        feature_rows = _read_csv(self.output_dir / "qmc_feature_condensation.csv")

        self._update_hit_rate(sim_rows)
        self._update_reuse_dist(pattern_rows)
        self._update_feature_heatmap(feature_rows)
        self._update_convergence(sim_rows)
        self._update_working_set(pattern_rows)
        self._update_param_space(sim_rows)

        self._fig.canvas.draw_idle()
        self._fig.canvas.flush_events()

    def run_live(self, duration_seconds: float = 1200) -> None:
        plt.ion()
        self._setup_figure()
        self._running = True
        t0 = time.perf_counter()

        try:
            while self._running and (time.perf_counter() - t0) < duration_seconds:
                self.refresh()
                plt.pause(self.update_interval)
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False

    def stop(self) -> None:
        self._running = False

    def save_snapshot(self, path: Optional[Path] = None) -> Path:
        if self._fig is None:
            self._setup_figure()
            self.refresh()
        out = path or (self.output_dir / "dashboard_snapshot.png")
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        self._fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(self._fig)
        self._fig = None
        return out


def generate_post_simulation_plots(output_dir: str = "outputs/qmc_simulation") -> List[Path]:
    """Generate static publication-quality plots after simulation completes."""
    out = Path(output_dir)
    figures_dir = out / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    saved: List[Path] = []

    if SNS:
        sns.set_theme(style="whitegrid", palette="deep")

    sim_rows = _read_csv(out / "qmc_simulation_log.csv")
    pattern_rows = _read_csv(out / "qmc_cache_patterns.csv")

    if sim_rows:
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle("QMC Cache Research Summary", fontsize=13, fontweight="bold")

        ax = axes[0, 0]
        engine_hits: Dict[str, List[bool]] = {}
        for r in sim_rows:
            engine_hits.setdefault(r.get("engine", "?"), []).append(r.get("cache_hit") == "True")
        for eng, hits in engine_hits.items():
            total_hr = sum(hits) / len(hits) if hits else 0
            ax.bar(eng, total_hr, alpha=0.8)
        ax.set_title("Overall Hit Rate by Engine")
        ax.set_ylabel("Hit Rate")
        ax.set_ylim(0, 1)

        ax = axes[0, 1]
        wall_times: Dict[str, List[float]] = {}
        for r in sim_rows:
            wt = _safe_float(r.get("wall_clock_ms"))
            if wt > 0:
                wall_times.setdefault(r.get("engine", "?"), []).append(wt)
        if wall_times:
            ax.boxplot(wall_times.values(), labels=wall_times.keys())
        ax.set_title("Compute Time by Engine (ms)")
        ax.set_ylabel("Wall Clock (ms)")

        ax = axes[1, 0]
        if pattern_rows:
            windows = list(range(len(pattern_rows)))
            hr = [_safe_float(r.get("exact_hit_rate")) for r in pattern_rows]
            ax.plot(windows, hr, linewidth=1.5)
            ax.fill_between(windows, hr, alpha=0.2)
        ax.set_title("Hit Rate Evolution")
        ax.set_xlabel("Window")
        ax.set_ylabel("Exact Hit Rate")

        ax = axes[1, 1]
        sigmas = [_safe_float(r.get("sigma")) for r in sim_rows if _safe_float(r.get("sigma")) > 0]
        prices = [_safe_float(r.get("price")) for r in sim_rows if not np.isnan(_safe_float(r.get("price", "nan")))]
        if sigmas and prices and len(sigmas) == len(sim_rows):
            sigmas_clean = []
            prices_clean = []
            for r in sim_rows:
                s = _safe_float(r.get("sigma"))
                p = _safe_float(r.get("price", "nan"))
                if s > 0 and not np.isnan(p):
                    sigmas_clean.append(s)
                    prices_clean.append(p)
            ax.scatter(sigmas_clean[:2000], prices_clean[:2000], s=5, alpha=0.3)
        ax.set_title("Price vs Volatility")
        ax.set_xlabel("Sigma")
        ax.set_ylabel("Price")

        fig.tight_layout()
        p = figures_dir / "qmc_cache_summary.png"
        fig.savefig(p, dpi=150, bbox_inches="tight")
        plt.close(fig)
        saved.append(p)

    return saved
