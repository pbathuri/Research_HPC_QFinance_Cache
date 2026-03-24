"""Generate all 12 trace analysis figures from trace CSVs.

Every function reads from CSV, produces one figure, saves to disk.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import numpy as np

try:
    import seaborn as sns
    _SNS = True
except ImportError:
    _SNS = False


def _read(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


def _f(v: str, default: float = 0.0) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _setup():
    if _SNS:
        sns.set_theme(style="whitegrid", palette="deep")


def _save(fig, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ── 1. Hit rate over time ────────────────────────────────────────────

def plot_trace_hit_rate_over_time(trace_dir: Path) -> Path:
    _setup()
    rows = _read(trace_dir / "trace_events.csv")
    fig, ax = plt.subplots(figsize=(12, 4))
    hr16 = [_f(r.get("rolling_hit_rate_16")) for r in rows]
    hr64 = [_f(r.get("rolling_hit_rate_64")) for r in rows]
    ax.plot(hr16, linewidth=0.8, alpha=0.6, label="window=16")
    ax.plot(hr64, linewidth=1.2, label="window=64")
    ax.set_title("Cache Hit Rate Over Time")
    ax.set_xlabel("Event Index")
    ax.set_ylabel("Hit Rate")
    ax.set_ylim(-0.05, 1.05)
    ax.legend()
    out = trace_dir / "figures" / "trace_hit_rate_over_time.png"
    _save(fig, out)
    return out


# ── 2. Miss rate over time ───────────────────────────────────────────

def plot_trace_miss_rate_over_time(trace_dir: Path) -> Path:
    _setup()
    rows = _read(trace_dir / "trace_events.csv")
    fig, ax = plt.subplots(figsize=(12, 4))
    mr16 = [_f(r.get("rolling_miss_rate_16")) for r in rows]
    mr64 = [_f(r.get("rolling_miss_rate_64")) for r in rows]
    ax.plot(mr16, linewidth=0.8, alpha=0.6, label="window=16")
    ax.plot(mr64, linewidth=1.2, label="window=64")
    ax.set_title("Cache Miss Rate Over Time")
    ax.set_xlabel("Event Index")
    ax.set_ylabel("Miss Rate")
    ax.set_ylim(-0.05, 1.05)
    ax.legend()
    out = trace_dir / "figures" / "trace_miss_rate_over_time.png"
    _save(fig, out)
    return out


# ── 3. Reuse distance over time ─────────────────────────────────────

def plot_trace_reuse_distance_over_time(trace_dir: Path) -> Path:
    _setup()
    rows = _read(trace_dir / "trace_events.csv")
    fig, ax = plt.subplots(figsize=(12, 4))
    rd = [_f(r.get("reuse_distance_events", "nan")) for r in rows]
    valid = [(i, v) for i, v in enumerate(rd) if not np.isnan(v)]
    if valid:
        ax.scatter([v[0] for v in valid], [v[1] for v in valid], s=4, alpha=0.4)
    ax.set_title("Reuse Distance Over Time")
    ax.set_xlabel("Event Index")
    ax.set_ylabel("Reuse Distance (events)")
    out = trace_dir / "figures" / "trace_reuse_distance_over_time.png"
    _save(fig, out)
    return out


# ── 4. Working set over time ────────────────────────────────────────

def plot_trace_working_set_over_time(trace_dir: Path) -> Path:
    _setup()
    rows = _read(trace_dir / "trace_events.csv")
    fig, ax = plt.subplots(figsize=(12, 4))
    ws16 = [_f(r.get("rolling_working_set_16")) for r in rows]
    ws64 = [_f(r.get("rolling_working_set_64")) for r in rows]
    ax.plot(ws16, linewidth=0.8, alpha=0.6, label="window=16")
    ax.plot(ws64, linewidth=1.2, label="window=64")
    ax.set_title("Rolling Working Set Size")
    ax.set_xlabel("Event Index")
    ax.set_ylabel("Unique Keys")
    ax.legend()
    out = trace_dir / "figures" / "trace_working_set_over_time.png"
    _save(fig, out)
    return out


# ── 5. Locality score over time ─────────────────────────────────────

def plot_trace_locality_score_over_time(trace_dir: Path) -> Path:
    _setup()
    rows = _read(trace_dir / "trace_events.csv")
    fig, ax = plt.subplots(figsize=(12, 4))
    loc16 = [_f(r.get("locality_score_16")) for r in rows]
    loc64 = [_f(r.get("locality_score_64")) for r in rows]
    ax.plot(loc16, linewidth=0.8, alpha=0.6, label="window=16")
    ax.plot(loc64, linewidth=1.2, label="window=64")
    ax.set_title("Locality Score Over Time")
    ax.set_xlabel("Event Index")
    ax.set_ylabel("Locality Score")
    ax.legend()
    out = trace_dir / "figures" / "trace_locality_score_over_time.png"
    _save(fig, out)
    return out


# ── 6. Burst vs Periodic ────────────────────────────────────────────

def plot_trace_burst_vs_periodic(trace_dir: Path) -> Path:
    _setup()
    rows = _read(trace_dir / "trace_windows.csv")
    fig, ax = plt.subplots(figsize=(7, 6))
    b = [_f(r.get("burst_score")) for r in rows]
    p = [_f(r.get("periodic_score")) for r in rows]
    ax.scatter(b, p, s=20, alpha=0.6)
    ax.set_title("Burst Score vs Periodic Score (per window)")
    ax.set_xlabel("Burst Score")
    ax.set_ylabel("Periodic Score")
    out = trace_dir / "figures" / "trace_burst_vs_periodic.png"
    _save(fig, out)
    return out


# ── 7. Engine × Phase heatmap ───────────────────────────────────────

def plot_trace_engine_phase_heatmap(trace_dir: Path) -> Path:
    _setup()
    rows = _read(trace_dir / "trace_events.csv")
    from collections import Counter
    out = trace_dir / "figures" / "trace_engine_phase_heatmap.png"

    if not rows:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, "No trace events available",
                ha="center", va="center", fontsize=14, color="gray")
        ax.set_title("Engine-Phase Heatmap (no events recorded)")
        ax.set_xticks([])
        ax.set_yticks([])
        _save(fig, out)
        return out

    pairs = Counter((r.get("engine", "?"), r.get("phase", "?")) for r in rows)
    engines = sorted(set(k[0] for k in pairs))
    phases = sorted(set(k[1] for k in pairs))

    if not engines or not phases:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, "No trace events available",
                ha="center", va="center", fontsize=14, color="gray")
        ax.set_title("Engine-Phase Heatmap (no events recorded)")
        ax.set_xticks([])
        ax.set_yticks([])
        _save(fig, out)
        return out

    mat = np.zeros((len(engines), len(phases)))
    for (e, p), cnt in pairs.items():
        if e in engines and p in phases:
            mat[engines.index(e)][phases.index(p)] = cnt

    fig, ax = plt.subplots(figsize=(max(6, len(phases) * 1.5), max(4, len(engines) * 0.8)))
    if _SNS:
        sns.heatmap(mat, xticklabels=phases, yticklabels=engines, annot=True, fmt=".0f", cmap="YlOrRd", ax=ax)
    else:
        ax.imshow(mat, aspect="auto", cmap="YlOrRd")
        ax.set_xticks(range(len(phases)))
        ax.set_xticklabels(phases)
        ax.set_yticks(range(len(engines)))
        ax.set_yticklabels(engines)
    ax.set_title("Events: Engine × Phase")
    _save(fig, out)
    return out


# ── 8. Polar scatter ────────────────────────────────────────────────

def plot_trace_polar_scatter(trace_dir: Path) -> Path:
    _setup()
    rows = _read(trace_dir / "trace_polar_embeddings.csv")
    fig, ax = plt.subplots(figsize=(7, 6))
    x = [_f(r.get("x")) for r in rows]
    y = [_f(r.get("y")) for r in rows]
    c = [_f(r.get("locality_score")) for r in rows]
    sc = ax.scatter(x, y, c=c, s=25, alpha=0.7, cmap="viridis")
    fig.colorbar(sc, ax=ax, label="Locality Score")
    ax.set_title("Polar Embedding (Cartesian Projection)")
    ax.set_xlabel("x = r·cos(θ)")
    ax.set_ylabel("y = r·sin(θ)")
    out = trace_dir / "figures" / "trace_polar_scatter.png"
    _save(fig, out)
    return out


# ── 9. Polar scatter by engine ──────────────────────────────────────

def plot_trace_polar_scatter_by_engine(trace_dir: Path) -> Path:
    _setup()
    rows = _read(trace_dir / "trace_polar_embeddings.csv")
    engines = sorted(set(r.get("dominant_engine", "?") for r in rows))
    fig, ax = plt.subplots(figsize=(8, 6))
    for eng in engines:
        sub = [r for r in rows if r.get("dominant_engine") == eng]
        x = [_f(r.get("x")) for r in sub]
        y = [_f(r.get("y")) for r in sub]
        ax.scatter(x, y, s=20, alpha=0.6, label=eng)
    ax.set_title("Polar Embedding by Dominant Engine")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.legend(fontsize=8)
    out = trace_dir / "figures" / "trace_polar_scatter_by_engine.png"
    _save(fig, out)
    return out


# ── 10. Runtime vs Reuse Distance ───────────────────────────────────

def plot_trace_runtime_vs_reuse(trace_dir: Path) -> Path:
    _setup()
    rows = _read(trace_dir / "trace_windows.csv")
    fig, ax = plt.subplots(figsize=(7, 6))
    rt = [_f(r.get("mean_wall_clock_ms")) for r in rows]
    rd = [_f(r.get("mean_reuse_distance")) for r in rows]
    ax.scatter(rd, rt, s=15, alpha=0.5)
    ax.set_title("Mean Wall Clock vs Mean Reuse Distance (per window)")
    ax.set_xlabel("Mean Reuse Distance")
    ax.set_ylabel("Mean Wall Clock (ms)")
    out = trace_dir / "figures" / "trace_runtime_vs_reuse.png"
    _save(fig, out)
    return out


# ── 11. Window cluster seed plot ────────────────────────────────────

def plot_trace_window_cluster_seed(trace_dir: Path) -> Path:
    _setup()
    rows = _read(trace_dir / "trace_windows.csv")
    from collections import Counter
    seeds = Counter(r.get("cluster_seed_key", "?") for r in rows)
    top = seeds.most_common(20)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh([t[0][:16] for t in top], [t[1] for t in top])
    ax.set_title("Top 20 Window Cluster Seeds")
    ax.set_xlabel("Count")
    ax.invert_yaxis()
    out = trace_dir / "figures" / "trace_window_cluster_seed_plot.png"
    _save(fig, out)
    return out


# ── 12. Signature frequency bar ─────────────────────────────────────

def plot_trace_signature_frequency(trace_dir: Path) -> Path:
    _setup()
    rows = _read(trace_dir / "trace_similarity_reference.csv")
    rows.sort(key=lambda r: int(r.get("occurrences", "0")), reverse=True)
    top = rows[:25]
    fig, ax = plt.subplots(figsize=(10, 5))
    labels = [r.get("signature_id", "?")[:14] for r in top]
    vals = [int(r.get("occurrences", "0")) for r in top]
    ax.barh(labels, vals, color="#4da6ff")
    ax.set_title("Top 25 Pattern Signatures by Frequency")
    ax.set_xlabel("Occurrences")
    ax.invert_yaxis()
    out = trace_dir / "figures" / "trace_signature_frequency_bar.png"
    _save(fig, out)
    return out


# ── 13. Similarity score over time ──────────────────────────────────

def plot_trace_similarity_score_over_time(trace_dir: Path) -> Path:
    _setup()
    rows = _read(trace_dir / "trace_events.csv")
    fig, ax = plt.subplots(figsize=(12, 4))
    sr16 = [_f(r.get("rolling_similarity_rate_16")) for r in rows]
    sr64 = [_f(r.get("rolling_similarity_rate_64")) for r in rows]
    ax.plot(sr16, linewidth=0.8, alpha=0.6, label="sim rate w=16")
    ax.plot(sr64, linewidth=1.2, label="sim rate w=64")
    scores = [_f(r.get("similarity_score")) for r in rows if _f(r.get("similarity_score")) > 0]
    if scores:
        ax2 = ax.twinx()
        ax2.scatter(
            [i for i, r in enumerate(rows) if _f(r.get("similarity_score")) > 0],
            scores, s=6, alpha=0.4, color="orange", label="score"
        )
        ax2.set_ylabel("Similarity Score")
    ax.set_title("Similarity Rate & Score Over Time")
    ax.set_xlabel("Event Index")
    ax.set_ylabel("Rate")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(loc="upper left")
    out = trace_dir / "figures" / "trace_similarity_score_over_time.png"
    _save(fig, out)
    return out


# ── 14. Similarity family frequency ────────────────────────────────

def plot_trace_similarity_family_frequency(trace_dir: Path) -> Path:
    _setup()
    rows = _read(trace_dir / "trace_similarity_reference.csv")
    rows.sort(key=lambda r: int(r.get("similarity_hits", "0") or "0"), reverse=True)
    top = rows[:20]
    fig, ax = plt.subplots(figsize=(10, 5))
    labels = [r.get("signature_id", "?")[:14] for r in top]
    exact = [int(r.get("exact_hits", "0") or "0") for r in top]
    sim = [int(r.get("similarity_hits", "0") or "0") for r in top]
    y_pos = np.arange(len(labels))
    ax.barh(y_pos, exact, label="Exact Hits", color="#4da6ff")
    ax.barh(y_pos, sim, left=exact, label="Similarity Hits", color="#ff9f43")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.set_title("Signature Families: Exact vs Similarity Hits")
    ax.set_xlabel("Count")
    ax.legend()
    ax.invert_yaxis()
    out = trace_dir / "figures" / "trace_similarity_family_frequency.png"
    _save(fig, out)
    return out


# ── 15. Exact vs similarity hits ────────────────────────────────────

def plot_trace_exact_vs_similarity_hits(trace_dir: Path) -> Path:
    _setup()
    rows = _read(trace_dir / "trace_events.csv")
    fig, ax = plt.subplots(figsize=(12, 4))
    exact = [1 if r.get("cache_hit") == "True" else 0 for r in rows]
    sim = [1 if r.get("similarity_hit") == "True" else 0 for r in rows]
    cum_exact = np.cumsum(exact)
    cum_sim = np.cumsum(sim)
    ax.plot(cum_exact, label="Cumulative Exact Hits", linewidth=1.2)
    ax.plot(cum_sim, label="Cumulative Similarity Hits", linewidth=1.2, linestyle="--")
    ax.set_title("Exact vs Similarity Hits (cumulative)")
    ax.set_xlabel("Event Index")
    ax.set_ylabel("Cumulative Count")
    ax.legend()
    out = trace_dir / "figures" / "trace_exact_vs_similarity_hits.png"
    _save(fig, out)
    return out


# ── 16. Similarity scatter polar ────────────────────────────────────

def plot_trace_similarity_scatter_polar(trace_dir: Path) -> Path:
    _setup()
    rows = _read(trace_dir / "trace_polar_embeddings.csv")
    fig, ax = plt.subplots(figsize=(7, 6))
    x = [_f(r.get("x")) for r in rows]
    y = [_f(r.get("y")) for r in rows]
    miss = [_f(r.get("miss_rate")) for r in rows]
    sc = ax.scatter(x, y, c=miss, s=25, alpha=0.7, cmap="RdYlGn_r")
    fig.colorbar(sc, ax=ax, label="Miss Rate")
    ax.set_title("Polar Embedding — Similarity / Miss Landscape")
    ax.set_xlabel("x = r·cos(θ)")
    ax.set_ylabel("y = r·sin(θ)")
    out = trace_dir / "figures" / "trace_similarity_scatter_polar.png"
    _save(fig, out)
    return out


# ── 17. PMU cache misses over time ──────────────────────────────────

def _has_pmu_data(rows: List[Dict[str, str]]) -> bool:
    return any(_f(r.get("pmu_cycles")) > 0 for r in rows)


def _no_data_figure(title: str, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.text(0.5, 0.5, "PMU data not available",
            ha="center", va="center", fontsize=14, color="gray")
    ax.set_title(title)
    ax.set_xticks([])
    ax.set_yticks([])
    _save(fig, out)
    return out


def plot_trace_pmu_cache_misses_over_time(trace_dir: Path) -> Path:
    _setup()
    out = trace_dir / "figures" / "trace_pmu_cache_misses_over_time.png"
    rows = _read(trace_dir / "trace_events.csv")
    if not _has_pmu_data(rows):
        return _no_data_figure("PMU Cache Misses Over Time (unsupported)", out)
    fig, ax = plt.subplots(figsize=(12, 4))
    misses = [_f(r.get("pmu_cache_misses")) for r in rows]
    ax.plot(misses, linewidth=0.8)
    ax.set_title("PMU Cache Misses Over Time")
    ax.set_xlabel("Event Index")
    ax.set_ylabel("Cache Misses")
    _save(fig, out)
    return out


# ── 18. PMU IPC by engine ───────────────────────────────────────────

def plot_trace_pmu_ipc_by_engine(trace_dir: Path) -> Path:
    _setup()
    out = trace_dir / "figures" / "trace_pmu_ipc_by_engine.png"
    rows = _read(trace_dir / "trace_engine_summary.csv")
    if not rows or not any(_f(r.get("pmu_cycles_total")) > 0 for r in rows):
        return _no_data_figure("PMU IPC by Engine (unsupported)", out)
    fig, ax = plt.subplots(figsize=(8, 5))
    engines = [r.get("engine", "?") for r in rows]
    ipcs = [_f(r.get("pmu_ipc")) for r in rows]
    ax.bar(engines, ipcs, color="#4da6ff")
    ax.set_title("Instructions Per Cycle by Engine")
    ax.set_ylabel("IPC")
    _save(fig, out)
    return out


# ── 19. PMU miss ratio by phase ─────────────────────────────────────

def plot_trace_pmu_miss_ratio_by_phase(trace_dir: Path) -> Path:
    _setup()
    out = trace_dir / "figures" / "trace_pmu_miss_ratio_by_phase.png"
    rows = _read(trace_dir / "trace_events.csv")
    if not _has_pmu_data(rows):
        return _no_data_figure("PMU Miss Ratio by Phase (unsupported)", out)

    from collections import defaultdict
    phase_data: dict = defaultdict(list)
    for r in rows:
        refs = _f(r.get("pmu_cache_references"))
        miss = _f(r.get("pmu_cache_misses"))
        if refs > 0:
            phase_data[r.get("phase", "?")].append(miss / refs)

    fig, ax = plt.subplots(figsize=(8, 5))
    phases = sorted(phase_data.keys())
    means = [float(np.mean(phase_data[p])) if phase_data[p] else 0 for p in phases]
    ax.bar(phases, means, color="#ff6b6b")
    ax.set_title("PMU Cache Miss Ratio by Phase")
    ax.set_ylabel("Miss Ratio")
    _save(fig, out)
    return out


# ── Master function ─────────────────────────────────────────────────

def generate_all_trace_plots(trace_dir: str | Path) -> List[Path]:
    td = Path(trace_dir)
    saved: List[Path] = []
    plotters = [
        plot_trace_hit_rate_over_time,
        plot_trace_miss_rate_over_time,
        plot_trace_reuse_distance_over_time,
        plot_trace_working_set_over_time,
        plot_trace_locality_score_over_time,
        plot_trace_burst_vs_periodic,
        plot_trace_engine_phase_heatmap,
        plot_trace_polar_scatter,
        plot_trace_polar_scatter_by_engine,
        plot_trace_runtime_vs_reuse,
        plot_trace_window_cluster_seed,
        plot_trace_signature_frequency,
        plot_trace_similarity_score_over_time,
        plot_trace_similarity_family_frequency,
        plot_trace_exact_vs_similarity_hits,
        plot_trace_similarity_scatter_polar,
        plot_trace_pmu_cache_misses_over_time,
        plot_trace_pmu_ipc_by_engine,
        plot_trace_pmu_miss_ratio_by_phase,
    ]
    for fn in plotters:
        try:
            p = fn(td)
            saved.append(p)
        except Exception as exc:
            print(f"  [trace-plot] {fn.__name__} failed: {exc}")
    return saved
