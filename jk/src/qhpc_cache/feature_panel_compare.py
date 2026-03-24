"""Canonical feature-panel comparison layer.

Compares four locked panel variants on two axes:
  Axis A: event-aware vs non-event-aware
  Axis B: raw vs PCA-condensed
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from qhpc_cache.feature_panel import (
    attach_event_tags_to_feature_panel,
    attach_rates_context_to_feature_panel,
    build_daily_feature_panel,
    compute_condensed_feature_panel_with_meta,
    deterministic_panel_label,
)


VARIANT_NON_EVENT_RAW = "non_event_aware_raw"
VARIANT_NON_EVENT_CONDENSED = "non_event_aware_pca_condensed"
VARIANT_EVENT_RAW = "event_aware_raw"
VARIANT_EVENT_CONDENSED = "event_aware_pca_condensed"

LOCKED_PANEL_VARIANTS: Tuple[str, ...] = (
    VARIANT_NON_EVENT_RAW,
    VARIANT_NON_EVENT_CONDENSED,
    VARIANT_EVENT_RAW,
    VARIANT_EVENT_CONDENSED,
)


def _safe_mean(series: Any) -> float:
    if series is None or len(series) == 0:
        return 0.0
    return float(series.mean())


def _quantile(series: Any, q: float) -> float:
    if series is None or len(series) == 0:
        return 0.0
    return float(series.quantile(q))


def _safe_nunique(series: Any) -> int:
    if series is None or len(series) == 0:
        return 0
    return int(series.dropna().nunique())


def _variant_flags(variant_label: str) -> Tuple[bool, bool]:
    event_aware = variant_label in (VARIANT_EVENT_RAW, VARIANT_EVENT_CONDENSED)
    condensed = variant_label in (VARIANT_NON_EVENT_CONDENSED, VARIANT_EVENT_CONDENSED)
    return event_aware, condensed


def _mac_degrade_ohlcv_input(
    ohlcv_long: Any,
    *,
    permno_column: str,
    date_column: str,
    mac_row_limit: int,
) -> Tuple[Any, List[str]]:
    import pandas as pd

    if ohlcv_long is None or len(ohlcv_long) == 0:
        return ohlcv_long, []
    if platform.system().lower() != "darwin":
        return ohlcv_long, []
    if len(ohlcv_long) <= mac_row_limit:
        return ohlcv_long, []

    df = ohlcv_long.copy()
    if permno_column not in df.columns:
        return df.head(mac_row_limit).copy(), [
            f"mac_scope_degraded_feature_panel rows={len(df)} limit={mac_row_limit}",
            "hpc_deferred::missing_permno_column_sampling_applied",
        ]

    df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
    n_perm = max(1, _safe_nunique(df[permno_column]))
    per_perm_cap = max(40, mac_row_limit // n_perm)
    parts = []
    deferred = 0
    for _, grp in df.sort_values(date_column).groupby(permno_column, dropna=False):
        if len(grp) > per_perm_cap:
            deferred += len(grp) - per_perm_cap
            parts.append(grp.tail(per_perm_cap))
        else:
            parts.append(grp)
    out = pd.concat(parts, ignore_index=True) if parts else df.head(0).copy()
    notes = [
        f"mac_scope_degraded_feature_panel rows={len(df)} limit={mac_row_limit} per_perm_cap={per_perm_cap}",
    ]
    if deferred > 0:
        notes.append(f"hpc_deferred::feature_panel_rows={deferred}")
    return out, notes


def _feature_columns_for_variant(panel: Any, base_feature_cols: Sequence[str], *, event_aware: bool, condensed: bool) -> List[str]:
    cols = [c for c in base_feature_cols if c in panel.columns]
    if event_aware:
        evt_cols = [c for c in panel.columns if c.startswith("event_") or c.startswith("qhpc_")]
        cols.extend([c for c in evt_cols if c not in cols])
    if condensed:
        pca_cols = [c for c in panel.columns if c.startswith("pca_")]
        cols = pca_cols if pca_cols else cols
    return cols


def _panel_reuse_proxies(panel: Any, feature_columns: Sequence[str]) -> Dict[str, Any]:
    import numpy as np
    import pandas as pd

    if panel is None or len(panel) == 0:
        return {
            "repeated_derived_structure_markers": 0,
            "repeated_join_pattern_markers": 0,
            "repeated_reconstruction_markers": 0,
            "reuse_density": 0.0,
        }
    df = panel.copy()
    cols = [c for c in feature_columns if c in df.columns]
    if not cols:
        cols = [c for c in df.columns if str(df[c].dtype).startswith(("float", "int", "bool"))][:8]
    if not cols:
        return {
            "repeated_derived_structure_markers": 0,
            "repeated_join_pattern_markers": 0,
            "repeated_reconstruction_markers": 0,
            "reuse_density": 0.0,
        }

    # Derived structure marker: rounded numeric feature-vector hash.
    sub = df[cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    rounded = sub.astype(float).round(3).astype(str).agg("|".join, axis=1)
    derived_counts = rounded.value_counts(dropna=True)
    repeated_derived = int((derived_counts > 1).sum())

    # Join pattern marker: null/non-null bit-pattern across join-sensitive columns.
    join_cols = [c for c in df.columns if c in ("risk_free_rate", "source") or c.startswith("event_") or c.startswith("qhpc_")]
    if join_cols:
        join_bits = df[join_cols].notna().astype(int).astype(str).agg("|".join, axis=1)
        join_counts = join_bits.value_counts(dropna=True)
        repeated_join = int((join_counts > 1).sum())
    else:
        repeated_join = 0

    # Reconstruction marker: repeated permno/date tuples where available.
    if "permno" in df.columns and "date" in df.columns:
        recon = (
            pd.to_datetime(df["date"], errors="coerce").dt.normalize().astype(str)
            + "|"
            + df["permno"].astype(str)
        )
        recon_counts = recon.value_counts(dropna=True)
        repeated_recon = int((recon_counts > 1).sum())
    else:
        repeated_recon = 0

    reuse_density = float(repeated_derived + repeated_join + repeated_recon) / max(1, len(df))
    return {
        "repeated_derived_structure_markers": repeated_derived,
        "repeated_join_pattern_markers": repeated_join,
        "repeated_reconstruction_markers": repeated_recon,
        "reuse_density": reuse_density,
    }


def build_feature_panel_variant(
    ohlcv_long: Any,
    *,
    variant_label: str,
    panel_key_base: str,
    rates_frame: Optional[Any] = None,
    event_tags: Optional[Any] = None,
    condense_n_components: int = 8,
    permno_column: str = "permno",
    date_column: str = "date",
    build_feature_kwargs: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, Dict[str, Any]]:
    """Build one canonical feature-panel variant with deterministic manifest fields."""
    import pandas as pd

    if variant_label not in LOCKED_PANEL_VARIANTS:
        raise ValueError(f"Unknown variant_label={variant_label}")
    build_kw = dict(build_feature_kwargs or {})
    build_kw.setdefault("permno_column", permno_column)
    build_kw.setdefault("date_column", date_column)
    t0 = time.perf_counter()

    event_aware, condensed = _variant_flags(variant_label)
    panel, feat_cols = build_daily_feature_panel(ohlcv_long, **build_kw)
    feature_count_before = len(feat_cols)
    event_attached = False
    rates_attached = False

    if event_aware and event_tags is not None and len(event_tags) > 0:
        tag_cols = [c for c in event_tags.columns if c not in (permno_column, date_column)]
        panel = attach_event_tags_to_feature_panel(
            panel,
            event_tags,
            permno_column=permno_column,
            date_column=date_column,
            tag_columns=tag_cols,
        )
        event_attached = True
        feature_count_before += len(tag_cols)

    if rates_frame is not None and len(rates_frame) > 0:
        panel = attach_rates_context_to_feature_panel(panel, rates_frame, date_column=date_column)
        rates_attached = True

    condense_meta: Dict[str, Any]
    if condensed:
        panel, n_after, condense_meta = compute_condensed_feature_panel_with_meta(
            panel,
            feat_cols,
            n_components=condense_n_components,
            prefix="pca_",
        )
    else:
        n_after = feature_count_before
        condense_meta = {
            "condensation_method": "raw_baseline",
            "explained_variance_ratio_sum": 0.0,
            "sklearn_used": False,
            "condensation_skipped": True,
            "skip_reason": "raw_variant",
            "n_input_features": feature_count_before,
            "n_output_features": feature_count_before,
        }

    d0 = str(pd.to_datetime(panel[date_column], errors="coerce").min())[:10] if len(panel) else ""
    d1 = str(pd.to_datetime(panel[date_column], errors="coerce").max())[:10] if len(panel) else ""
    permnos = panel[permno_column].dropna().astype(str).unique().tolist()[:5000] if len(panel) and permno_column in panel.columns else []
    panel_key = f"{panel_key_base}::{variant_label}"
    det = deterministic_panel_label(panel_key=panel_key, permnos=permnos, date_start=d0, date_end=d1)

    variant_feature_cols = _feature_columns_for_variant(panel, feat_cols, event_aware=event_aware, condensed=condensed)
    reuse = _panel_reuse_proxies(panel, variant_feature_cols)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    manifest = {
        "panel_variant_label": variant_label,
        "event_aware": event_aware,
        "condensed": condensed,
        "panel_key": panel_key,
        "deterministic_label": det,
        "n_rows": int(len(panel)),
        "n_securities": int(_safe_nunique(panel[permno_column])) if permno_column in panel.columns else 0,
        "n_dates": int(_safe_nunique(pd.to_datetime(panel[date_column], errors="coerce").dt.normalize())) if date_column in panel.columns else 0,
        "date_range_start": d0,
        "date_range_end": d1,
        "feature_count_before_condense": int(feature_count_before),
        "feature_count_after_condense": int(n_after),
        "event_tags_attached": bool(event_attached),
        "rates_attached": bool(rates_attached),
        "condensation_method": str(condense_meta.get("condensation_method", "")),
        "explained_variance_ratio_sum": float(condense_meta.get("explained_variance_ratio_sum", 0.0)),
        "sklearn_used": bool(condense_meta.get("sklearn_used", False)),
        "condensation_skipped": bool(condense_meta.get("condensation_skipped", False)),
        "condensation_skip_reason": str(condense_meta.get("skip_reason", "")),
        "panel_build_timing_ms": elapsed_ms,
        "feature_columns_used": ";".join(variant_feature_cols),
    }
    manifest.update(reuse)
    return panel, manifest


def build_non_event_aware_raw_panel(ohlcv_long: Any, **kwargs: Any) -> Tuple[Any, Dict[str, Any]]:
    return build_feature_panel_variant(ohlcv_long, variant_label=VARIANT_NON_EVENT_RAW, **kwargs)


def build_non_event_aware_condensed_panel(ohlcv_long: Any, **kwargs: Any) -> Tuple[Any, Dict[str, Any]]:
    return build_feature_panel_variant(ohlcv_long, variant_label=VARIANT_NON_EVENT_CONDENSED, **kwargs)


def build_event_aware_raw_panel(ohlcv_long: Any, **kwargs: Any) -> Tuple[Any, Dict[str, Any]]:
    return build_feature_panel_variant(ohlcv_long, variant_label=VARIANT_EVENT_RAW, **kwargs)


def build_event_aware_condensed_panel(ohlcv_long: Any, **kwargs: Any) -> Tuple[Any, Dict[str, Any]]:
    return build_feature_panel_variant(ohlcv_long, variant_label=VARIANT_EVENT_CONDENSED, **kwargs)


def summarize_panel_dimensionality(variant_manifest_df: Any) -> Any:
    if variant_manifest_df is None or len(variant_manifest_df) == 0:
        return variant_manifest_df.head(0) if variant_manifest_df is not None else None
    df = variant_manifest_df.copy()
    df["dimensionality_reduction_ratio"] = (
        df["feature_count_after_condense"].astype(float) / df["feature_count_before_condense"].replace(0, 1).astype(float)
    )
    return df[
        [
            "panel_variant_label",
            "event_aware",
            "condensed",
            "feature_count_before_condense",
            "feature_count_after_condense",
            "dimensionality_reduction_ratio",
            "n_rows",
            "n_securities",
            "n_dates",
        ]
    ].copy()


def summarize_panel_reuse_proxies(variant_manifest_df: Any) -> Any:
    if variant_manifest_df is None or len(variant_manifest_df) == 0:
        return variant_manifest_df.head(0) if variant_manifest_df is not None else None
    return variant_manifest_df[
        [
            "panel_variant_label",
            "event_aware",
            "condensed",
            "repeated_derived_structure_markers",
            "repeated_join_pattern_markers",
            "repeated_reconstruction_markers",
            "reuse_density",
            "event_tags_attached",
            "rates_attached",
        ]
    ].copy()


def summarize_panel_timing(variant_manifest_df: Any) -> Any:
    if variant_manifest_df is None or len(variant_manifest_df) == 0:
        return variant_manifest_df.head(0) if variant_manifest_df is not None else None
    return variant_manifest_df[
        [
            "panel_variant_label",
            "event_aware",
            "condensed",
            "panel_build_timing_ms",
            "n_rows",
            "feature_count_before_condense",
            "feature_count_after_condense",
        ]
    ].copy()


def compare_event_aware_vs_non_event_aware(variant_manifest_df: Any) -> Any:
    if variant_manifest_df is None or len(variant_manifest_df) == 0:
        return variant_manifest_df.head(0) if variant_manifest_df is not None else None
    grp = variant_manifest_df.groupby("event_aware", dropna=False).agg(
        variants=("panel_variant_label", "count"),
        avg_rows=("n_rows", "mean"),
        avg_feature_before=("feature_count_before_condense", "mean"),
        avg_feature_after=("feature_count_after_condense", "mean"),
        avg_timing_ms=("panel_build_timing_ms", "mean"),
        avg_reuse_density=("reuse_density", "mean"),
    )
    out = grp.reset_index()
    out["comparison_axis"] = "event_aware_vs_non_event_aware"
    return out


def compare_raw_vs_condensed(variant_manifest_df: Any) -> Any:
    if variant_manifest_df is None or len(variant_manifest_df) == 0:
        return variant_manifest_df.head(0) if variant_manifest_df is not None else None
    grp = variant_manifest_df.groupby("condensed", dropna=False).agg(
        variants=("panel_variant_label", "count"),
        avg_rows=("n_rows", "mean"),
        avg_feature_before=("feature_count_before_condense", "mean"),
        avg_feature_after=("feature_count_after_condense", "mean"),
        avg_timing_ms=("panel_build_timing_ms", "mean"),
        avg_reuse_density=("reuse_density", "mean"),
    )
    out = grp.reset_index()
    out["comparison_axis"] = "raw_vs_condensed"
    return out


def compare_panel_variants(variant_manifest_df: Any) -> Any:
    if variant_manifest_df is None or len(variant_manifest_df) == 0:
        return variant_manifest_df.head(0) if variant_manifest_df is not None else None
    cols = [
        "panel_variant_label",
        "event_aware",
        "condensed",
        "n_rows",
        "n_securities",
        "n_dates",
        "feature_count_before_condense",
        "feature_count_after_condense",
        "panel_build_timing_ms",
        "reuse_density",
        "event_tags_attached",
        "rates_attached",
    ]
    return variant_manifest_df[cols].copy()


def rank_panel_variants_for_cache_study_value(variant_manifest_df: Any) -> Any:
    if variant_manifest_df is None or len(variant_manifest_df) == 0:
        return variant_manifest_df.head(0) if variant_manifest_df is not None else None
    df = variant_manifest_df.copy()
    df["cache_study_value_score"] = (
        0.20 * df["n_rows"].astype(float).rank(pct=True)
        + 0.15 * df["feature_count_before_condense"].astype(float).rank(pct=True)
        + 0.20 * df["reuse_density"].astype(float).rank(pct=True)
        + 0.20 * df["panel_build_timing_ms"].astype(float).rank(pct=True)
        + 0.10 * df["event_tags_attached"].astype(int)
        + 0.15 * df["rates_attached"].astype(int)
    )
    df["rank"] = df["cache_study_value_score"].rank(method="dense", ascending=False).astype(int)
    return df[["panel_variant_label", "cache_study_value_score", "rank"]].sort_values("rank").reset_index(drop=True)


def build_feature_panel_comparison_bundle(
    ohlcv_long: Any,
    *,
    panel_key_base: str,
    rates_frame: Optional[Any] = None,
    event_tags: Optional[Any] = None,
    condense_n_components: int = 8,
    build_feature_kwargs: Optional[Dict[str, Any]] = None,
    run_id: str = "",
    record_observability: bool = True,
    mac_row_limit: int = 2_000_000,
) -> Dict[str, Any]:
    """Build four panel variants and return structured comparison bundle."""
    import pandas as pd

    build_kw = dict(build_feature_kwargs or {})
    permno_column = str(build_kw.get("permno_column", "permno"))
    date_column = str(build_kw.get("date_column", "date"))
    ohlcv_used, deferred_notes = _mac_degrade_ohlcv_input(
        ohlcv_long,
        permno_column=permno_column,
        date_column=date_column,
        mac_row_limit=mac_row_limit,
    )

    variant_frames: Dict[str, Any] = {}
    variant_manifests: List[Dict[str, Any]] = []
    for variant in LOCKED_PANEL_VARIANTS:
        frame, manifest = build_feature_panel_variant(
            ohlcv_used,
            variant_label=variant,
            panel_key_base=panel_key_base,
            rates_frame=rates_frame,
            event_tags=event_tags,
            condense_n_components=condense_n_components,
            build_feature_kwargs=build_kw,
        )
        variant_frames[variant] = frame
        variant_manifests.append(manifest)

    manifest_df = pd.DataFrame(variant_manifests)
    comparison_summary = compare_panel_variants(manifest_df)
    condensation_summary = summarize_panel_dimensionality(manifest_df)
    timing_summary = summarize_panel_timing(manifest_df)
    reuse_proxy_summary = summarize_panel_reuse_proxies(manifest_df)
    rankings = rank_panel_variants_for_cache_study_value(manifest_df)
    axis_event = compare_event_aware_vs_non_event_aware(manifest_df)
    axis_condense = compare_raw_vs_condensed(manifest_df)

    if record_observability:
        from qhpc_cache.cache_workload_mapping import record_spine_pipeline_observation
        from qhpc_cache.workload_signatures import WORKLOAD_SPINE_FEATURE_PANEL

        record_spine_pipeline_observation(
            run_id=run_id or f"feature_panel_compare::{panel_key_base}",
            workload_spine_id=WORKLOAD_SPINE_FEATURE_PANEL,
            pipeline_phase="feature_panel_compare",
            source_datasets="crsp.dsf;rates_data;event_alignment_tags",
            row_count_primary=int(len(ohlcv_long) if ohlcv_long is not None else 0),
            row_count_after_join=int(_safe_mean(manifest_df["n_rows"])),
            join_width_estimate=int(_safe_mean(manifest_df["feature_count_before_condense"])),
            feature_dim_before=int(_safe_mean(manifest_df["feature_count_before_condense"])),
            feature_dim_after=int(_safe_mean(manifest_df["feature_count_after_condense"])),
            reuse_alignment_opportunities=int(manifest_df["repeated_derived_structure_markers"].sum()),
            notes=json.dumps({"deferred_hpc_workloads": len(deferred_notes), "variants": list(LOCKED_PANEL_VARIANTS)})[:500],
        )

    return {
        "variant_panels": variant_frames,
        "variant_manifest": manifest_df,
        "comparison_summary": comparison_summary,
        "condensation_summary": condensation_summary,
        "timing_summary": timing_summary,
        "reuse_proxy_summary": reuse_proxy_summary,
        "dimension_summary": condensation_summary.copy(),
        "axis_event_vs_non_event": axis_event,
        "axis_raw_vs_condensed": axis_condense,
        "rankings": rankings,
        "deferred_hpc_workloads": deferred_notes,
        "panel_key_base": panel_key_base,
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


def export_feature_panel_comparison_bundle(
    *,
    bundle: Mapping[str, Any],
    output_dir: str | Path,
) -> Dict[str, str]:
    """Export primary CSV/JSON products then secondary markdown/plot products."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Primary CSV outputs
    csv_variant_manifest = out / "feature_panel_variant_manifest.csv"
    csv_cmp = out / "feature_panel_comparison_summary.csv"
    csv_condense = out / "feature_panel_condensation_summary.csv"
    csv_timing = out / "feature_panel_timing_summary.csv"
    csv_reuse = out / "feature_panel_reuse_proxy_summary.csv"
    csv_dim = out / "feature_panel_dimension_summary.csv"

    bundle["variant_manifest"].to_csv(csv_variant_manifest, index=False)
    bundle["comparison_summary"].to_csv(csv_cmp, index=False)
    bundle["condensation_summary"].to_csv(csv_condense, index=False)
    bundle["timing_summary"].to_csv(csv_timing, index=False)
    bundle["reuse_proxy_summary"].to_csv(csv_reuse, index=False)
    bundle["dimension_summary"].to_csv(csv_dim, index=False)

    # Primary JSON outputs
    json_variant = out / "feature_panel_variant_manifest.json"
    json_cmp_manifest = out / "feature_panel_comparison_manifest.json"
    json_cond_manifest = out / "feature_panel_condensation_manifest.json"
    json_variant.write_text(
        bundle["variant_manifest"].to_json(orient="records", indent=2),
        encoding="utf-8",
    )
    comparison_manifest = {
        "schema_version": "1.0",
        "panel_key_base": str(bundle.get("panel_key_base", "")),
        "variants": list(LOCKED_PANEL_VARIANTS),
        "primary_csv_outputs": [
            csv_variant_manifest.name,
            csv_cmp.name,
            csv_condense.name,
            csv_timing.name,
            csv_reuse.name,
            csv_dim.name,
        ],
        "deferred_hpc_workloads": list(bundle.get("deferred_hpc_workloads", [])),
    }
    condensation_manifest = {
        "schema_version": "1.0",
        "condensation_method_summary": bundle["condensation_summary"].to_dict(orient="records"),
    }
    json_cmp_manifest.write_text(json.dumps(comparison_manifest, indent=2), encoding="utf-8")
    json_cond_manifest.write_text(json.dumps(condensation_manifest, indent=2), encoding="utf-8")

    # Secondary markdown outputs
    md_cmp = out / "feature_panel_comparison_summary.md"
    md_cond = out / "feature_panel_condensation_summary.md"
    md_rank = out / "feature_panel_rankings_summary.md"
    bullets_cmp = [
        (
            f"{r.panel_variant_label}: rows={int(r.n_rows)} sec={int(r.n_securities)} "
            f"dates={int(r.n_dates)} timing_ms={float(r.panel_build_timing_ms):.2f}"
        )
        for r in bundle["comparison_summary"].itertuples(index=False)
    ]
    _write_md(md_cmp, title="Feature Panel Comparison Summary", bullets=bullets_cmp)
    bullets_cond = [
        (
            f"{r.panel_variant_label}: before={int(r.feature_count_before_condense)} "
            f"after={int(r.feature_count_after_condense)} ratio={float(r.dimensionality_reduction_ratio):.4f}"
        )
        for r in bundle["condensation_summary"].itertuples(index=False)
    ]
    _write_md(md_cond, title="Feature Panel Condensation Summary", bullets=bullets_cond)
    bullets_rank = [
        f"rank={int(r.rank)} {r.panel_variant_label}: score={float(r.cache_study_value_score):.4f}"
        for r in bundle["rankings"].itertuples(index=False)
    ]
    _write_md(md_rank, title="Feature Panel Rankings Summary", bullets=bullets_rank)

    # Secondary plot outputs
    plot_feat = out / "plot_feature_count_before_after_condensation.png"
    plot_timing = out / "plot_panel_variant_timing_comparison.png"
    plot_event_axis = out / "plot_event_aware_vs_non_event_aware_comparison.png"
    plot_cond_axis = out / "plot_raw_vs_condensed_comparison.png"
    plot_rank = out / "plot_panel_variant_rankings.png"
    plot_dim = out / "plot_panel_dimensionality_comparison.png"

    _plot_bar(
        bundle["condensation_summary"],
        x="panel_variant_label",
        y="feature_count_after_condense",
        hue="event_aware",
        title="Feature Count After Condensation",
        output_path=plot_feat,
    )
    _plot_bar(
        bundle["timing_summary"],
        x="panel_variant_label",
        y="panel_build_timing_ms",
        title="Panel Variant Timing Comparison",
        output_path=plot_timing,
    )
    _plot_bar(
        bundle["axis_event_vs_non_event"],
        x="event_aware",
        y="avg_feature_after",
        title="Event-Aware vs Non-Event-Aware",
        output_path=plot_event_axis,
    )
    _plot_bar(
        bundle["axis_raw_vs_condensed"],
        x="condensed",
        y="avg_feature_after",
        title="Raw vs Condensed",
        output_path=plot_cond_axis,
    )
    _plot_bar(
        bundle["rankings"],
        x="panel_variant_label",
        y="cache_study_value_score",
        title="Panel Variant Rankings",
        output_path=plot_rank,
    )
    _plot_bar(
        bundle["dimension_summary"],
        x="panel_variant_label",
        y="dimensionality_reduction_ratio",
        title="Panel Dimensionality Comparison",
        output_path=plot_dim,
    )

    return {
        "feature_panel_variant_manifest_csv": str(csv_variant_manifest),
        "feature_panel_comparison_summary_csv": str(csv_cmp),
        "feature_panel_condensation_summary_csv": str(csv_condense),
        "feature_panel_timing_summary_csv": str(csv_timing),
        "feature_panel_reuse_proxy_summary_csv": str(csv_reuse),
        "feature_panel_dimension_summary_csv": str(csv_dim),
        "feature_panel_variant_manifest_json": str(json_variant),
        "feature_panel_comparison_manifest_json": str(json_cmp_manifest),
        "feature_panel_condensation_manifest_json": str(json_cond_manifest),
        "feature_panel_comparison_summary_md": str(md_cmp),
        "feature_panel_condensation_summary_md": str(md_cond),
        "feature_panel_rankings_summary_md": str(md_rank),
        "plot_feature_count_before_after_condensation": str(plot_feat),
        "plot_panel_variant_timing_comparison": str(plot_timing),
        "plot_event_aware_vs_non_event_aware_comparison": str(plot_event_axis),
        "plot_raw_vs_condensed_comparison": str(plot_cond_axis),
        "plot_panel_variant_rankings": str(plot_rank),
        "plot_panel_dimensionality_comparison": str(plot_dim),
    }
