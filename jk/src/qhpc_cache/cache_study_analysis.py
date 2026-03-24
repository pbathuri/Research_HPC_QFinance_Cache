"""First serious cache-study analysis layer on event-library substrate.

Stage order is locked:
1) Deep within-set analysis
2) Cross-set comparison

Primary artifacts are CSV/JSON outputs; markdown/plots are secondary views.
"""

from __future__ import annotations

import json
from pathlib import Path
import platform
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from qhpc_cache.event_set_library import ensure_required_sets
from qhpc_cache.event_workload_signatures import compute_event_workload_signatures


LOCKED_CACHE_STUDY_SET_IDS: Tuple[str, ...] = (
    "set_a_covid_crash",
    "set_b_march_2020_liquidity",
    "set_c_2022_rate_shock",
    "set_d_2023_banking_stress",
    "set_e_broad_institutional_stress_library",
)


def _quantile(series: Any, q: float) -> float:
    if series is None or len(series) == 0:
        return 0.0
    return float(series.quantile(q))


def _safe_mean(series: Any) -> float:
    if series is None or len(series) == 0:
        return 0.0
    return float(series.mean())


def _safe_nunique(series: Any) -> int:
    if series is None or len(series) == 0:
        return 0
    return int(series.dropna().nunique())


def _safe_entropy(counts: Any) -> float:
    import numpy as np

    if counts is None or len(counts) == 0:
        return 0.0
    vals = np.asarray(counts, dtype=float)
    total = float(vals.sum())
    if total <= 0:
        return 0.0
    p = vals / total
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def _empty_frame(columns: Sequence[str]) -> Any:
    import pandas as pd

    return pd.DataFrame(columns=list(columns))


def _coerce_set_rows(normalized_rows: Any, event_set_id: str) -> Any:
    import pandas as pd

    if normalized_rows is None or len(normalized_rows) == 0:
        return pd.DataFrame()
    df = normalized_rows.copy()
    if "event_set_id" not in df.columns:
        raise ValueError("normalized_rows must include event_set_id")
    return df.loc[df["event_set_id"] == event_set_id].copy()


def analyze_window_family_within_set(event_set_rows: Any, *, event_set_id: str) -> Any:
    """Within-set behavior grouped by window family."""
    if event_set_rows is None or len(event_set_rows) == 0:
        return _empty_frame(
            [
                "event_set_id",
                "window_family_label",
                "row_count",
                "event_count",
                "aligned_permno_count",
                "join_width_mean",
                "join_width_p90",
                "timing_p50_ms",
                "timing_p90_ms",
                "timing_p99_ms",
                "identifier_match_quality_mean",
            ]
        )
    grp = event_set_rows.groupby("window_family_label", dropna=False).agg(
        row_count=("event_id", "size"),
        event_count=("event_id", "nunique"),
        aligned_permno_count=("permno", lambda s: int(s.dropna().nunique())),
        join_width_mean=("join_width", "mean"),
        join_width_p90=("join_width", lambda s: _quantile(s, 0.90)),
        timing_p50_ms=("stage_timing_ms", lambda s: _quantile(s, 0.50)),
        timing_p90_ms=("stage_timing_ms", lambda s: _quantile(s, 0.90)),
        timing_p99_ms=("stage_timing_ms", lambda s: _quantile(s, 0.99)),
        identifier_match_quality_mean=("alignment_match_quality", "mean"),
    )
    out = grp.reset_index()
    out.insert(0, "event_set_id", event_set_id)
    return out


def analyze_intraday_slice_within_set(event_set_rows: Any, *, event_set_id: str) -> Any:
    """Within-set behavior grouped by intraday slice."""
    if event_set_rows is None or len(event_set_rows) == 0:
        return _empty_frame(
            [
                "event_set_id",
                "intraday_slice_label",
                "row_count",
                "event_count",
                "aligned_permno_count",
                "timing_p50_ms",
                "timing_p90_ms",
                "identifier_match_quality_mean",
            ]
        )
    grp = event_set_rows.groupby("intraday_slice_label", dropna=False).agg(
        row_count=("event_id", "size"),
        event_count=("event_id", "nunique"),
        aligned_permno_count=("permno", lambda s: int(s.dropna().nunique())),
        timing_p50_ms=("stage_timing_ms", lambda s: _quantile(s, 0.50)),
        timing_p90_ms=("stage_timing_ms", lambda s: _quantile(s, 0.90)),
        identifier_match_quality_mean=("alignment_match_quality", "mean"),
    )
    out = grp.reset_index()
    out.insert(0, "event_set_id", event_set_id)
    return out


def summarize_alignment_quality_within_set(event_set_rows: Any, *, event_set_id: str) -> Any:
    """Within-set alignment-quality summary."""
    import pandas as pd

    if event_set_rows is None or len(event_set_rows) == 0:
        return pd.DataFrame(
            [
                {
                    "event_set_id": event_set_id,
                    "alignment_quality_mean": 0.0,
                    "alignment_quality_p10": 0.0,
                    "alignment_quality_p90": 0.0,
                    "alignment_quality_p99": 0.0,
                    "join_width_mean": 0.0,
                }
            ]
        )
    s = event_set_rows["alignment_match_quality"]
    return pd.DataFrame(
        [
            {
                "event_set_id": event_set_id,
                "alignment_quality_mean": _safe_mean(s),
                "alignment_quality_p10": _quantile(s, 0.10),
                "alignment_quality_p90": _quantile(s, 0.90),
                "alignment_quality_p99": _quantile(s, 0.99),
                "join_width_mean": _safe_mean(event_set_rows["join_width"]),
            }
        ]
    )


def summarize_reconstruction_reuse_within_set(event_set_rows: Any, *, event_set_id: str) -> Any:
    """Within-set repeated reconstruction/join-pattern/derived-structure markers."""
    import pandas as pd

    if event_set_rows is None or len(event_set_rows) == 0:
        return pd.DataFrame(
            [
                {
                    "event_set_id": event_set_id,
                    "repeated_event_window_reconstruction_markers": 0,
                    "repeated_join_pattern_markers": 0,
                    "reusable_derived_structure_markers": 0,
                    "reuse_density": 0.0,
                }
            ]
        )
    row_count = int(len(event_set_rows))
    w = event_set_rows["normalized_window_id"].value_counts(dropna=True)
    j = event_set_rows["join_pattern_id"].value_counts(dropna=True)
    d = event_set_rows["derived_structure_id"].value_counts(dropna=True)
    repeated_windows = int((w > 1).sum())
    repeated_join_patterns = int((j > 1).sum())
    reusable_derived = int((d > 1).sum())
    reuse_density = float(repeated_windows + repeated_join_patterns + reusable_derived) / max(1, row_count)
    return pd.DataFrame(
        [
            {
                "event_set_id": event_set_id,
                "repeated_event_window_reconstruction_markers": repeated_windows,
                "repeated_join_pattern_markers": repeated_join_patterns,
                "reusable_derived_structure_markers": reusable_derived,
                "reuse_density": reuse_density,
            }
        ]
    )


def summarize_timing_within_set(event_set_rows: Any, *, event_set_id: str) -> Any:
    """Within-set timing distribution summary."""
    import pandas as pd

    if event_set_rows is None or len(event_set_rows) == 0:
        return pd.DataFrame(
            [
                {
                    "event_set_id": event_set_id,
                    "timing_p50_ms": 0.0,
                    "timing_p90_ms": 0.0,
                    "timing_p99_ms": 0.0,
                    "timing_p999_ms": 0.0,
                    "timing_mean_ms": 0.0,
                }
            ]
        )
    s = event_set_rows["stage_timing_ms"]
    return pd.DataFrame(
        [
            {
                "event_set_id": event_set_id,
                "timing_p50_ms": _quantile(s, 0.50),
                "timing_p90_ms": _quantile(s, 0.90),
                "timing_p99_ms": _quantile(s, 0.99),
                "timing_p999_ms": _quantile(s, 0.999),
                "timing_mean_ms": _safe_mean(s),
            }
        ]
    )


def summarize_cache_proxies_within_set(event_set_rows: Any, *, event_set_id: str) -> Any:
    """Within-set cache-proxy summary derived from workload signatures."""
    import pandas as pd

    sig = compute_event_workload_signatures(event_set_rows)
    if sig is None or len(sig) == 0:
        return pd.DataFrame(
            [
                {
                    "event_set_id": event_set_id,
                    "cache_proxy_reuse_density": 0.0,
                    "cache_proxy_locality_hint": 0.0,
                    "cache_proxy_alignment_penalty": 0.0,
                    "workload_family_count": 0,
                }
            ]
        )
    return pd.DataFrame(
        [
            {
                "event_set_id": event_set_id,
                "cache_proxy_reuse_density": _safe_mean(sig["cache_proxy_reuse_density"]),
                "cache_proxy_locality_hint": _safe_mean(sig["cache_proxy_locality_hint"]),
                "cache_proxy_alignment_penalty": _safe_mean(sig["cache_proxy_alignment_penalty"]),
                "workload_family_count": _safe_nunique(sig["workload_family_label"]),
            }
        ]
    )


def analyze_event_set_cache_structure(normalized_rows: Any, *, event_set_id: str) -> Dict[str, Any]:
    """Deep within-set analysis bundle for one event set."""
    import pandas as pd

    df = _coerce_set_rows(normalized_rows, event_set_id)
    if len(df) == 0:
        summary = pd.DataFrame(
            [
                {
                    "event_set_id": event_set_id,
                    "event_count": 0,
                    "category_count": 0,
                    "window_family_count": 0,
                    "intraday_slice_count": 0,
                    "row_count": 0,
                    "aligned_permno_count": 0,
                    "join_width_mean": 0.0,
                    "category_entropy": 0.0,
                }
            ]
        )
        return {
            "within_set_summary": summary,
            "category_mix": _empty_frame(["event_set_id", "category_label", "event_count", "row_count"]),
            "window_family": analyze_window_family_within_set(df, event_set_id=event_set_id),
            "intraday_slice": analyze_intraday_slice_within_set(df, event_set_id=event_set_id),
            "alignment": summarize_alignment_quality_within_set(df, event_set_id=event_set_id),
            "reuse": summarize_reconstruction_reuse_within_set(df, event_set_id=event_set_id),
            "timing": summarize_timing_within_set(df, event_set_id=event_set_id),
            "cache_proxy": summarize_cache_proxies_within_set(df, event_set_id=event_set_id),
        }

    cat = df.groupby("category_label", dropna=False).agg(
        event_count=("event_id", "nunique"),
        row_count=("event_id", "size"),
    )
    cat = cat.reset_index()
    cat.insert(0, "event_set_id", event_set_id)
    category_entropy = _safe_entropy(cat["row_count"])
    summary = pd.DataFrame(
        [
            {
                "event_set_id": event_set_id,
                "event_count": _safe_nunique(df["event_id"]),
                "category_count": _safe_nunique(df["category_label"]),
                "window_family_count": _safe_nunique(df["window_family_label"]),
                "intraday_slice_count": _safe_nunique(df["intraday_slice_label"]),
                "row_count": int(len(df)),
                "aligned_permno_count": _safe_nunique(df["permno"]),
                "join_width_mean": _safe_mean(df["join_width"]),
                "category_entropy": category_entropy,
            }
        ]
    )
    return {
        "within_set_summary": summary,
        "category_mix": cat,
        "window_family": analyze_window_family_within_set(df, event_set_id=event_set_id),
        "intraday_slice": analyze_intraday_slice_within_set(df, event_set_id=event_set_id),
        "alignment": summarize_alignment_quality_within_set(df, event_set_id=event_set_id),
        "reuse": summarize_reconstruction_reuse_within_set(df, event_set_id=event_set_id),
        "timing": summarize_timing_within_set(df, event_set_id=event_set_id),
        "cache_proxy": summarize_cache_proxies_within_set(df, event_set_id=event_set_id),
    }


def _mac_degrade_for_cache_analysis(normalized_rows: Any, *, mac_row_limit: int) -> Tuple[Any, List[str]]:
    import pandas as pd

    if normalized_rows is None or len(normalized_rows) == 0:
        return normalized_rows, []
    is_mac = platform.system().lower() == "darwin"
    if not is_mac or len(normalized_rows) <= mac_row_limit:
        return normalized_rows, []

    # Deterministic per-set cap to keep coverage across all sets.
    per_set_cap = max(25_000, mac_row_limit // max(1, _safe_nunique(normalized_rows["event_set_id"])))
    kept_parts = []
    notes: List[str] = [
        f"mac_scope_degraded_cache_study rows={len(normalized_rows)} limit={mac_row_limit} per_set_cap={per_set_cap}"
    ]
    for sid, grp in normalized_rows.groupby("event_set_id", dropna=False):
        if len(grp) > per_set_cap:
            notes.append(f"hpc_deferred::{sid}::rows={len(grp) - per_set_cap}")
            kept_parts.append(grp.head(per_set_cap))
        else:
            kept_parts.append(grp)
    kept = pd.concat(kept_parts, ignore_index=True) if kept_parts else normalized_rows.head(0)
    return kept, notes


def compare_event_sets_cache_structure(within_set_summary: Any) -> Any:
    """Cross-set structure comparison using within-set summaries."""
    import pandas as pd

    if within_set_summary is None or len(within_set_summary) == 0:
        return _empty_frame(["event_set_id", "structure_complexity_score", "structure_similarity_to_centroid"])
    df = within_set_summary.copy()
    centroid = {
        "event_count": _safe_mean(df["event_count"]),
        "category_entropy": _safe_mean(df["category_entropy"]),
        "join_width_mean": _safe_mean(df["join_width_mean"]),
    }
    out_rows: List[Dict[str, Any]] = []
    for r in df.itertuples(index=False):
        complexity = float(r.event_count) * 0.20 + float(r.category_entropy) * 0.35 + float(r.join_width_mean) * 0.45
        d = (
            abs(float(r.event_count) - centroid["event_count"]) / max(1.0, centroid["event_count"])
            + abs(float(r.category_entropy) - centroid["category_entropy"]) / max(1e-6, centroid["category_entropy"])
            + abs(float(r.join_width_mean) - centroid["join_width_mean"]) / max(1e-6, centroid["join_width_mean"])
        ) / 3.0
        out_rows.append(
            {
                "event_set_id": r.event_set_id,
                "structure_complexity_score": complexity,
                "structure_similarity_to_centroid": max(0.0, 1.0 - d),
            }
        )
    return pd.DataFrame(out_rows)


def compare_event_sets_alignment_quality(alignment_summary: Any) -> Any:
    """Cross-set alignment-quality comparison."""
    if alignment_summary is None or len(alignment_summary) == 0:
        return _empty_frame(["event_set_id", "alignment_quality_mean", "alignment_quality_p90", "alignment_rank"])
    df = alignment_summary.copy()
    df = df[["event_set_id", "alignment_quality_mean", "alignment_quality_p90"]].copy()
    df["alignment_rank"] = df["alignment_quality_mean"].rank(method="dense", ascending=False).astype(int)
    return df.sort_values("alignment_rank").reset_index(drop=True)


def compare_event_sets_timing(timing_summary: Any) -> Any:
    """Cross-set timing comparison."""
    if timing_summary is None or len(timing_summary) == 0:
        return _empty_frame(["event_set_id", "timing_p90_ms", "timing_p99_ms", "timing_spread_ratio", "timing_rank"])
    df = timing_summary.copy()
    df["timing_spread_ratio"] = df["timing_p99_ms"] / df["timing_p50_ms"].replace(0, 1.0)
    df["timing_rank"] = df["timing_p90_ms"].rank(method="dense", ascending=False).astype(int)
    return df[["event_set_id", "timing_p90_ms", "timing_p99_ms", "timing_spread_ratio", "timing_rank"]]


def compare_event_sets_reuse_proxies(reuse_proxy_summary: Any) -> Any:
    """Cross-set reuse-proxy comparison."""
    if reuse_proxy_summary is None or len(reuse_proxy_summary) == 0:
        return _empty_frame(
            [
                "event_set_id",
                "cache_proxy_reuse_density",
                "cache_proxy_locality_hint",
                "cache_proxy_alignment_penalty",
                "reuse_rank",
            ]
        )
    df = reuse_proxy_summary.copy()
    df["reuse_rank"] = df["cache_proxy_reuse_density"].rank(method="dense", ascending=False).astype(int)
    return df.sort_values("reuse_rank").reset_index(drop=True)


def rank_event_sets_for_cache_study_value(
    *,
    within_set_summary: Any,
    alignment_summary: Any,
    timing_summary: Any,
    reuse_proxy_summary: Any,
) -> Any:
    """Rank sets for later guided-cache research value."""
    import pandas as pd

    if within_set_summary is None or len(within_set_summary) == 0:
        return _empty_frame(["event_set_id", "cache_study_value_score", "rank", "notes"])
    df = within_set_summary.merge(alignment_summary, on="event_set_id", how="left").merge(
        timing_summary, on="event_set_id", how="left"
    ).merge(reuse_proxy_summary, on="event_set_id", how="left")
    for col in (
        "row_count",
        "join_width_mean",
        "alignment_quality_mean",
        "timing_p90_ms",
        "cache_proxy_reuse_density",
        "cache_proxy_locality_hint",
    ):
        if col not in df.columns:
            df[col] = 0.0
    # Composite score: data richness + complexity + quality + reuse + timing pressure.
    df["cache_study_value_score"] = (
        0.15 * df["row_count"].astype(float).rank(pct=True)
        + 0.20 * df["join_width_mean"].astype(float).rank(pct=True)
        + 0.20 * df["alignment_quality_mean"].astype(float).rank(pct=True)
        + 0.20 * df["cache_proxy_reuse_density"].astype(float).rank(pct=True)
        + 0.10 * df["cache_proxy_locality_hint"].astype(float).rank(pct=True)
        + 0.15 * df["timing_p90_ms"].astype(float).rank(pct=True)
    )
    df["rank"] = df["cache_study_value_score"].rank(method="dense", ascending=False).astype(int)
    df["notes"] = (
        "higher_score=>better_candidate_for_guided_cache_followup;"
        "first_layer_proxies_not_pmu_proof"
    )
    return df[["event_set_id", "cache_study_value_score", "rank", "notes"]].sort_values("rank").reset_index(drop=True)


def export_cross_set_cache_summary(
    *,
    cross_set_summary: Any,
    output_dir: str | Path,
    filename: str = "cache_study_cross_set_summary.csv",
) -> Path:
    """Export cross-set cache summary CSV only."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / filename
    cross_set_summary.to_csv(path, index=False)
    return path


def run_cache_study_analysis(
    *,
    normalized_event_rows: Any,
    selected_set_ids: Optional[Sequence[str]] = None,
    mac_row_limit: int = 1_500_000,
    run_id: str = "",
    record_observability: bool = True,
) -> Dict[str, Any]:
    """Run full cache-study analysis (within-set first, cross-set second)."""
    import pandas as pd

    set_ids = tuple(selected_set_ids) if selected_set_ids else LOCKED_CACHE_STUDY_SET_IDS
    ensure_required_sets(set_ids)

    normalized = normalized_event_rows.copy() if hasattr(normalized_event_rows, "copy") else pd.DataFrame(normalized_event_rows)
    normalized = normalized.loc[normalized["event_set_id"].isin(set_ids)].copy() if len(normalized) else normalized
    normalized, deferred_notes = _mac_degrade_for_cache_analysis(normalized, mac_row_limit=mac_row_limit)

    # Stage 1: within-set
    within_summaries: List[Any] = []
    category_mixes: List[Any] = []
    window_behaviors: List[Any] = []
    intraday_behaviors: List[Any] = []
    alignments: List[Any] = []
    reuses: List[Any] = []
    timings: List[Any] = []
    proxies: List[Any] = []
    for sid in set_ids:
        bundle = analyze_event_set_cache_structure(normalized, event_set_id=sid)
        within_summaries.append(bundle["within_set_summary"])
        category_mixes.append(bundle["category_mix"])
        window_behaviors.append(bundle["window_family"])
        intraday_behaviors.append(bundle["intraday_slice"])
        alignments.append(bundle["alignment"])
        reuses.append(bundle["reuse"])
        timings.append(bundle["timing"])
        proxies.append(bundle["cache_proxy"])

    within_set_summary = pd.concat(within_summaries, ignore_index=True) if within_summaries else pd.DataFrame()
    category_mix = pd.concat(category_mixes, ignore_index=True) if category_mixes else pd.DataFrame()
    window_family_summary = pd.concat(window_behaviors, ignore_index=True) if window_behaviors else pd.DataFrame()
    intraday_slice_summary = pd.concat(intraday_behaviors, ignore_index=True) if intraday_behaviors else pd.DataFrame()
    alignment_summary = pd.concat(alignments, ignore_index=True) if alignments else pd.DataFrame()
    reuse_reconstruction_summary = pd.concat(reuses, ignore_index=True) if reuses else pd.DataFrame()
    timing_summary = pd.concat(timings, ignore_index=True) if timings else pd.DataFrame()
    reuse_proxy_summary = pd.concat(proxies, ignore_index=True) if proxies else pd.DataFrame()

    # Stage 2: cross-set
    cross_structure = compare_event_sets_cache_structure(within_set_summary)
    cross_alignment = compare_event_sets_alignment_quality(alignment_summary)
    cross_timing = compare_event_sets_timing(timing_summary)
    cross_reuse = compare_event_sets_reuse_proxies(reuse_proxy_summary)
    rankings = rank_event_sets_for_cache_study_value(
        within_set_summary=within_set_summary,
        alignment_summary=alignment_summary,
        timing_summary=timing_summary,
        reuse_proxy_summary=reuse_proxy_summary,
    )
    cross_set_summary = cross_structure.merge(cross_alignment, on="event_set_id", how="left").merge(
        cross_timing, on="event_set_id", how="left"
    ).merge(cross_reuse, on="event_set_id", how="left").merge(
        rankings[["event_set_id", "cache_study_value_score", "rank"]], on="event_set_id", how="left"
    )

    if record_observability:
        from qhpc_cache.cache_workload_mapping import record_spine_pipeline_observation
        from qhpc_cache.workload_signatures import WORKLOAD_SPINE_EVENT_WINDOW

        record_spine_pipeline_observation(
            run_id=run_id or "cache_study_analysis",
            workload_spine_id=WORKLOAD_SPINE_EVENT_WINDOW,
            pipeline_phase="cache_study_analysis",
            source_datasets="event_window_manifest;workload_signature_summary",
            row_count_primary=int(len(normalized_event_rows) if normalized_event_rows is not None else 0),
            row_count_after_join=int(len(normalized)),
            join_width_estimate=int(_safe_mean(normalized["join_width"]) if len(normalized) and "join_width" in normalized.columns else 0),
            alignment_match_rate=float(_safe_mean(normalized["alignment_match_quality"]) if len(normalized) and "alignment_match_quality" in normalized.columns else -1.0),
            reuse_alignment_opportunities=int(
                reuse_reconstruction_summary["repeated_join_pattern_markers"].sum()
                if len(reuse_reconstruction_summary)
                else 0
            ),
            notes=json.dumps({"deferred_hpc_workloads": len(deferred_notes), "set_count": len(set_ids)})[:500],
        )

    return {
        "normalized_rows": normalized,
        "within_set_summary": within_set_summary,
        "within_set_category_mix": category_mix,
        "within_set_window_family": window_family_summary,
        "within_set_intraday_slice": intraday_slice_summary,
        "alignment_summary": alignment_summary,
        "reuse_reconstruction_summary": reuse_reconstruction_summary,
        "timing_summary": timing_summary,
        "reuse_proxy_summary": reuse_proxy_summary,
        "cross_set_summary": cross_set_summary,
        "rankings": rankings,
        "deferred_hpc_workloads": deferred_notes,
        "selected_set_ids": list(set_ids),
    }


def _safe_plot_library() -> Tuple[Any, Any]:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return None, None
    try:
        import seaborn as sns

        return plt, sns
    except Exception:
        return plt, None


def _plot_bar(frame: Any, *, x: str, y: str, hue: str = "", title: str, output_path: Path) -> Optional[Path]:
    if frame is None or len(frame) == 0:
        return None
    plt, sns = _safe_plot_library()
    if plt is None:
        return None
    fig = plt.figure(figsize=(9, 4.5))
    ax = fig.add_subplot(111)
    if sns is not None:
        if hue:
            sns.barplot(data=frame, x=x, y=y, hue=hue, ax=ax)
        else:
            sns.barplot(data=frame, x=x, y=y, ax=ax)
    else:
        if hue:
            frame.pivot_table(index=x, columns=hue, values=y, aggfunc="mean").plot(kind="bar", ax=ax)
        else:
            frame.groupby(x)[y].mean().plot(kind="bar", ax=ax)
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=140)
    plt.close(fig)
    return output_path


def _write_md(path: Path, *, title: str, bullets: Sequence[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {title}", ""]
    for b in bullets:
        lines.append(f"- {b}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def export_cache_study_analysis(
    *,
    analysis_result: Mapping[str, Any],
    output_dir: str | Path,
) -> Dict[str, str]:
    """Export primary CSV/JSON data products then secondary markdown/plot outputs."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Primary CSV outputs
    csv_within = out / "cache_study_within_set_summary.csv"
    csv_cross = out / "cache_study_cross_set_summary.csv"
    csv_timing = out / "cache_study_timing_summary.csv"
    csv_reuse = out / "cache_study_reuse_proxy_summary.csv"
    csv_align = out / "cache_study_alignment_summary.csv"
    csv_rank = out / "cache_study_rankings.csv"

    analysis_result["within_set_summary"].to_csv(csv_within, index=False)
    analysis_result["cross_set_summary"].to_csv(csv_cross, index=False)
    analysis_result["timing_summary"].to_csv(csv_timing, index=False)
    analysis_result["reuse_proxy_summary"].to_csv(csv_reuse, index=False)
    analysis_result["alignment_summary"].to_csv(csv_align, index=False)
    analysis_result["rankings"].to_csv(csv_rank, index=False)

    # Primary JSON outputs
    json_within_manifest = out / "cache_study_within_set_manifest.json"
    json_cross_manifest = out / "cache_study_cross_set_manifest.json"
    json_analysis_manifest = out / "cache_study_analysis_manifest.json"
    within_manifest = {
        "schema_version": "1.0",
        "selected_set_ids": list(analysis_result["selected_set_ids"]),
        "within_set_row_count": int(len(analysis_result["within_set_summary"])),
        "deferred_hpc_workloads": list(analysis_result.get("deferred_hpc_workloads", [])),
    }
    cross_manifest = {
        "schema_version": "1.0",
        "cross_set_row_count": int(len(analysis_result["cross_set_summary"])),
        "ranking_row_count": int(len(analysis_result["rankings"])),
    }
    full_manifest = {
        "schema_version": "1.0",
        "primary_csv_outputs": [
            csv_within.name,
            csv_cross.name,
            csv_timing.name,
            csv_reuse.name,
            csv_align.name,
            csv_rank.name,
        ],
        "primary_json_outputs": [
            json_within_manifest.name,
            json_cross_manifest.name,
            json_analysis_manifest.name,
        ],
        "secondary_md_outputs": [
            "cache_study_within_set_summary.md",
            "cache_study_cross_set_summary.md",
            "cache_study_rankings_summary.md",
        ],
        "deferred_hpc_workloads": list(analysis_result.get("deferred_hpc_workloads", [])),
    }
    json_within_manifest.write_text(json.dumps(within_manifest, indent=2), encoding="utf-8")
    json_cross_manifest.write_text(json.dumps(cross_manifest, indent=2), encoding="utf-8")
    json_analysis_manifest.write_text(json.dumps(full_manifest, indent=2), encoding="utf-8")

    # Secondary markdown outputs
    md_within = out / "cache_study_within_set_summary.md"
    md_cross = out / "cache_study_cross_set_summary.md"
    md_rank = out / "cache_study_rankings_summary.md"

    bullets_within = [
        (
            f"{r.event_set_id}: events={int(r.event_count)} rows={int(r.row_count)} "
            f"permnos={int(r.aligned_permno_count)} join_width_mean={float(r.join_width_mean):.2f}"
        )
        for r in analysis_result["within_set_summary"].itertuples(index=False)
    ]
    _write_md(md_within, title="Cache Study Within-Set Summary", bullets=bullets_within)
    bullets_cross = [
        (
            f"{r.event_set_id}: structure_sim={float(r.structure_similarity_to_centroid):.4f} "
            f"align_mean={float(r.alignment_quality_mean):.4f} timing_p90_ms={float(r.timing_p90_ms):.2f}"
        )
        for r in analysis_result["cross_set_summary"].fillna(0).itertuples(index=False)
    ]
    _write_md(md_cross, title="Cache Study Cross-Set Summary", bullets=bullets_cross)
    bullets_rank = [
        f"rank={int(r.rank)} {r.event_set_id}: score={float(r.cache_study_value_score):.4f}"
        for r in analysis_result["rankings"].itertuples(index=False)
    ]
    _write_md(md_rank, title="Cache Study Rankings Summary", bullets=bullets_rank)

    # Secondary plots
    plot_within_timing = out / "plot_within_set_timing_distributions.png"
    plot_cross_timing = out / "plot_cross_set_timing_comparison.png"
    plot_alignment = out / "plot_alignment_quality_comparison.png"
    plot_reuse = out / "plot_reuse_proxy_comparison.png"
    plot_ranking = out / "plot_event_set_rankings.png"
    plot_window = out / "plot_window_family_comparison.png"

    _plot_bar(
        analysis_result["within_set_window_family"],
        x="window_family_label",
        y="timing_p90_ms",
        hue="event_set_id",
        title="Within-Set Timing Distributions",
        output_path=plot_within_timing,
    )
    _plot_bar(
        analysis_result["timing_summary"],
        x="event_set_id",
        y="timing_p90_ms",
        title="Cross-Set Timing Comparison",
        output_path=plot_cross_timing,
    )
    _plot_bar(
        analysis_result["alignment_summary"],
        x="event_set_id",
        y="alignment_quality_mean",
        title="Alignment-Quality Comparison",
        output_path=plot_alignment,
    )
    _plot_bar(
        analysis_result["reuse_proxy_summary"],
        x="event_set_id",
        y="cache_proxy_reuse_density",
        title="Reuse-Proxy Comparison",
        output_path=plot_reuse,
    )
    _plot_bar(
        analysis_result["rankings"],
        x="event_set_id",
        y="cache_study_value_score",
        title="Event-Set Ranking for Cache Study Value",
        output_path=plot_ranking,
    )
    _plot_bar(
        analysis_result["within_set_window_family"],
        x="event_set_id",
        y="row_count",
        hue="window_family_label",
        title="Window-Family Comparison",
        output_path=plot_window,
    )

    return {
        "cache_study_within_set_summary_csv": str(csv_within),
        "cache_study_cross_set_summary_csv": str(csv_cross),
        "cache_study_timing_summary_csv": str(csv_timing),
        "cache_study_reuse_proxy_summary_csv": str(csv_reuse),
        "cache_study_alignment_summary_csv": str(csv_align),
        "cache_study_rankings_csv": str(csv_rank),
        "cache_study_within_set_manifest_json": str(json_within_manifest),
        "cache_study_cross_set_manifest_json": str(json_cross_manifest),
        "cache_study_analysis_manifest_json": str(json_analysis_manifest),
        "cache_study_within_set_summary_md": str(md_within),
        "cache_study_cross_set_summary_md": str(md_cross),
        "cache_study_rankings_summary_md": str(md_rank),
        "plot_within_set_timing_distributions": str(plot_within_timing),
        "plot_cross_set_timing_comparison": str(plot_cross_timing),
        "plot_alignment_quality_comparison": str(plot_alignment),
        "plot_reuse_proxy_comparison": str(plot_reuse),
        "plot_event_set_rankings": str(plot_ranking),
        "plot_window_family_comparison": str(plot_window),
    }
