"""Canonical event-library comparison and export layer.

Builds normalized cross-set rows, compares locked sets A-E across locked window
families, and exports researcher-grade artifacts (CSV/JSON/Markdown/plots).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from qhpc_cache.event_set_library import (
    LOCKED_INTRADAY_SLICES,
    LOCKED_MULTI_DAY_WINDOWS,
    build_event_set_manifest as _build_set_manifest,
    ensure_required_sets,
    flatten_event_library_rows,
    locked_window_policy_manifest,
)
from qhpc_cache.event_workload_signatures import (
    compute_event_workload_signatures,
    join_pattern_id_from_row,
    summarize_cache_proxies,
    summarize_timing_distribution,
)


NORMALIZED_SCHEMA_VERSION = "1.0"


def _window_key(*, event_set_id: str, event_id: str, window_family: str, intraday_slice: str, start: str, end: str) -> str:
    raw = "|".join([event_set_id, event_id, window_family, intraday_slice, start, end])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:18]


def _select_set_rows(set_ids: Optional[Sequence[str]]) -> List[Dict[str, Any]]:
    rows = flatten_event_library_rows()
    if not set_ids:
        return rows
    wanted = set(ensure_required_sets(set_ids))
    return [r for r in rows if r["event_set_id"] in wanted]


def build_event_set_manifest(*, selected_set_ids: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Return event-set manifest (optionally filtered to selected set IDs)."""
    payload = _build_set_manifest(include_window_policy=True)
    if not selected_set_ids:
        return payload
    wanted = set(ensure_required_sets(selected_set_ids))
    payload["event_sets"] = [s for s in payload["event_sets"] if s.get("event_set_id") in wanted]
    return payload


def _event_to_set_rows(set_rows: Sequence[Mapping[str, Any]]) -> Dict[str, List[Mapping[str, Any]]]:
    out: Dict[str, List[Mapping[str, Any]]] = {}
    for row in set_rows:
        eid = str(row["event_id"])
        out.setdefault(eid, []).append(row)
    return out


def normalize_event_rows_common_schema(
    raw_rows: Any,
    *,
    selected_set_ids: Optional[Sequence[str]] = None,
    include_intraday: bool = True,
) -> Any:
    """Normalize rows to one common event-library schema.

    Required normalized fields are always emitted:
      - event_set_id, event_id, event_label, category_label
      - window_family_label, intraday_slice_label
      - permno, symbol, symbol_root
      - window_start, window_end, event_time_start, event_time_end
      - alignment_match_quality, source_datasets
      - row_count, join_width, normalization_schema_version
      - normalized_window_id, join_pattern_id, derived_structure_id
      - stage_timing_ms
    """
    import pandas as pd

    if raw_rows is None:
        return pd.DataFrame()
    df = raw_rows.copy() if hasattr(raw_rows, "copy") else pd.DataFrame(raw_rows)
    if len(df) == 0:
        return pd.DataFrame()

    set_rows = _select_set_rows(selected_set_ids)
    event_lookup = _event_to_set_rows(set_rows)

    window_allowed = set(LOCKED_MULTI_DAY_WINDOWS)
    if include_intraday:
        window_allowed.update(LOCKED_INTRADAY_SLICES)

    event_id_col = "event_id"
    if event_id_col not in df.columns:
        for cand in ("qhpc_event_identifier", "event_identifier"):
            if cand in df.columns:
                event_id_col = cand
                break
    event_label_col = "event_label" if "event_label" in df.columns else "qhpc_event_label"
    permno_col = "permno" if "permno" in df.columns else None
    symbol_col = "symbol" if "symbol" in df.columns else ("ticker" if "ticker" in df.columns else "")
    sym_root_col = "qhpc_sym_root_norm" if "qhpc_sym_root_norm" in df.columns else symbol_col
    event_set_col = "event_set_id" if "event_set_id" in df.columns else ""

    out_rows: List[Dict[str, Any]] = []
    for row in df.to_dict(orient="records"):
        event_id = str(row.get(event_id_col, "")).strip()
        if not event_id:
            continue
        mapped = event_lookup.get(event_id, [])
        if event_set_col and row.get(event_set_col):
            mapped = [m for m in mapped if m["event_set_id"] == str(row[event_set_col])]
        if not mapped:
            continue

        window_family = str(row.get("window_family_label", "d-1_to_d+1"))
        intraday_slice = str(row.get("intraday_slice_label", "none"))
        if window_family not in window_allowed and intraday_slice not in window_allowed:
            continue
        if window_family in LOCKED_INTRADAY_SLICES:
            intraday_slice = window_family
            window_family = "intraday_extension"

        source_ds = str(row.get("source_datasets", "taq_kdb;wrds_link;crsp"))
        join_width = int(row.get("join_width", row.get("join_width_estimate", 0)) or 0)
        if join_width <= 0:
            join_width = len(row.keys())
        align_quality = float(
            row.get("alignment_match_quality", row.get("qhpc_link_confidence", row.get("permno_match_rate", 0.0))) or 0.0
        )
        stage_timing_ms = float(row.get("stage_timing_ms", (row.get("elapsed_seconds", 0.0) or 0.0) * 1000.0) or 0.0)

        w_start = str(row.get("window_start", row.get("window_start_utc", row.get("time_window_start", ""))))
        w_end = str(row.get("window_end", row.get("window_end_utc", row.get("time_window_end", ""))))
        t_start = str(row.get("event_time_start", w_start))
        t_end = str(row.get("event_time_end", w_end))

        for m in mapped:
            norm = {
                "event_set_id": m["event_set_id"],
                "event_set_label": m["event_set_label"],
                "event_id": event_id,
                "event_label": str(row.get(event_label_col, m["event_label"])),
                "category_label": m["category_label"],
                "window_family_label": window_family,
                "intraday_slice_label": intraday_slice,
                "permno": row.get(permno_col, None) if permno_col else None,
                "symbol": str(row.get(symbol_col, "")) if symbol_col else "",
                "symbol_root": str(row.get(sym_root_col, "")) if sym_root_col else "",
                "window_start": w_start,
                "window_end": w_end,
                "event_time_start": t_start,
                "event_time_end": t_end,
                "alignment_match_quality": align_quality,
                "source_datasets": source_ds,
                "row_count": int(row.get("row_count", 1) or 1),
                "join_width": join_width,
                "normalization_schema_version": NORMALIZED_SCHEMA_VERSION,
                "stage_timing_ms": stage_timing_ms,
            }
            norm["normalized_window_id"] = _window_key(
                event_set_id=norm["event_set_id"],
                event_id=norm["event_id"],
                window_family=norm["window_family_label"],
                intraday_slice=norm["intraday_slice_label"],
                start=norm["window_start"],
                end=norm["window_end"],
            )
            norm["join_pattern_id"] = join_pattern_id_from_row(norm)
            derived = f"{norm['event_set_id']}|{norm['window_family_label']}|{norm['intraday_slice_label']}"
            norm["derived_structure_id"] = hashlib.sha256(derived.encode("utf-8")).hexdigest()[:12]
            out_rows.append(norm)
    return pd.DataFrame(out_rows)


def compare_event_set_sizes(*, event_set_rows: Any, normalized_rows: Any) -> Any:
    """Compare set size by definitions and normalized run materialization."""
    import pandas as pd

    if event_set_rows is None:
        event_set_rows = pd.DataFrame()
    if normalized_rows is None:
        normalized_rows = pd.DataFrame()
    base = event_set_rows.groupby(["event_set_id", "event_set_label"], dropna=False).agg(
        defined_event_count=("event_id", "nunique")
    )
    base = base.reset_index()
    if len(normalized_rows) == 0:
        base["materialized_row_count"] = 0
        base["aligned_permno_count"] = 0
        return base
    g2 = normalized_rows.groupby("event_set_id", dropna=False).agg(
        materialized_row_count=("event_id", "size"),
        aligned_permno_count=("permno", lambda s: int(s.dropna().nunique())),
    )
    return base.merge(g2.reset_index(), on="event_set_id", how="left").fillna(0)


def compare_event_category_distribution(*, event_set_rows: Any, normalized_rows: Any) -> Any:
    """Compare category balance for each event set."""
    import pandas as pd

    dist_def = event_set_rows.groupby(["event_set_id", "category_label"], dropna=False).agg(
        defined_event_count=("event_id", "nunique")
    )
    dist_def = dist_def.reset_index()
    if normalized_rows is None or len(normalized_rows) == 0:
        dist_def["materialized_row_count"] = 0
        return dist_def
    dist_run = normalized_rows.groupby(["event_set_id", "category_label"], dropna=False).agg(
        materialized_row_count=("event_id", "size")
    )
    out = dist_def.merge(dist_run.reset_index(), on=["event_set_id", "category_label"], how="left")
    out["materialized_row_count"] = out["materialized_row_count"].fillna(0).astype(int)
    return out


def compare_alignment_quality(normalized_rows: Any) -> Any:
    """Alignment quality and join characteristics by set/window."""
    import pandas as pd

    if normalized_rows is None or len(normalized_rows) == 0:
        return pd.DataFrame(
            columns=[
                "event_set_id",
                "window_family_label",
                "intraday_slice_label",
                "alignment_quality_mean",
                "alignment_quality_p10",
                "alignment_quality_p90",
                "join_width_mean",
            ]
        )

    def q(s: Any, frac: float) -> float:
        return float(s.quantile(frac)) if len(s) else 0.0

    grp = normalized_rows.groupby(
        ["event_set_id", "window_family_label", "intraday_slice_label"],
        dropna=False,
    ).agg(
        alignment_quality_mean=("alignment_match_quality", "mean"),
        alignment_quality_p10=("alignment_match_quality", lambda s: q(s, 0.10)),
        alignment_quality_p90=("alignment_match_quality", lambda s: q(s, 0.90)),
        join_width_mean=("join_width", "mean"),
    )
    return grp.reset_index()


def compare_window_family_behavior(normalized_rows: Any) -> Any:
    """Behavior comparison by set/window family with timing and row intensity."""
    import pandas as pd

    if normalized_rows is None or len(normalized_rows) == 0:
        return pd.DataFrame(
            columns=[
                "event_set_id",
                "window_family_label",
                "intraday_slice_label",
                "row_count",
                "aligned_permno_count",
                "timing_p50_ms",
                "timing_p90_ms",
                "join_width_mean",
            ]
        )
    grp = normalized_rows.groupby(
        ["event_set_id", "window_family_label", "intraday_slice_label"],
        dropna=False,
    ).agg(
        row_count=("event_id", "size"),
        aligned_permno_count=("permno", lambda s: int(s.dropna().nunique())),
        timing_p50_ms=("stage_timing_ms", "median"),
        timing_p90_ms=("stage_timing_ms", lambda s: float(s.quantile(0.90)) if len(s) else 0.0),
        join_width_mean=("join_width", "mean"),
    )
    return grp.reset_index()


def _mac_degrade_if_needed(normalized_rows: Any, *, mac_row_limit: int) -> Tuple[Any, List[str]]:
    """Apply sensible Mac scope degradation; return deferred notes for HPC."""
    import pandas as pd

    if normalized_rows is None or len(normalized_rows) == 0:
        return normalized_rows, []
    is_mac = platform.system().lower() == "darwin"
    if not is_mac:
        return normalized_rows, []
    if len(normalized_rows) <= mac_row_limit:
        return normalized_rows, []

    # Keep top slices by coverage, defer the rest to HPC.
    grp = normalized_rows.groupby(["event_set_id", "window_family_label"], dropna=False).size()
    keep_keys = set(grp.sort_values(ascending=False).head(32).index.tolist())
    mask = normalized_rows.apply(
        lambda r: (r.get("event_set_id"), r.get("window_family_label")) in keep_keys,
        axis=1,
    )
    kept = normalized_rows.loc[mask].copy()
    deferred = normalized_rows.loc[~mask, ["event_set_id", "window_family_label"]].drop_duplicates()
    notes = [
        f"hpc_deferred::{r.event_set_id}::{r.window_family_label}"
        for r in deferred.itertuples(index=False)
    ]
    notes.insert(
        0,
        (
            f"mac_scope_degraded rows={len(normalized_rows)} limit={mac_row_limit}; "
            f"deferred_pairs={len(notes)}"
        ),
    )
    return kept, notes


def run_event_set_comparison(
    *,
    raw_event_rows: Any,
    selected_set_ids: Optional[Sequence[str]] = None,
    include_intraday_extensions: bool = True,
    mac_row_limit: int = 1_250_000,
    run_id: str = "",
    record_observability: bool = True,
) -> Dict[str, Any]:
    """Run canonical set comparison over locked sets and locked windows."""
    import pandas as pd

    set_rows = _select_set_rows(selected_set_ids)
    set_df = pd.DataFrame(set_rows)

    normalized = normalize_event_rows_common_schema(
        raw_event_rows,
        selected_set_ids=selected_set_ids,
        include_intraday=include_intraday_extensions,
    )
    normalized, deferred_notes = _mac_degrade_if_needed(normalized, mac_row_limit=mac_row_limit)

    out = {
        "event_set_manifest": build_event_set_manifest(selected_set_ids=selected_set_ids),
        "window_policy_manifest": locked_window_policy_manifest(),
        "event_window_manifest": normalized,
        "event_set_sizes": compare_event_set_sizes(event_set_rows=set_df, normalized_rows=normalized),
        "category_distribution": compare_event_category_distribution(event_set_rows=set_df, normalized_rows=normalized),
        "alignment_quality": compare_alignment_quality(normalized),
        "window_family_behavior": compare_window_family_behavior(normalized),
        "deferred_hpc_workloads": deferred_notes,
    }

    signatures = compute_event_workload_signatures(normalized)
    out["workload_signature_summary"] = signatures
    out["timing_distribution_summary"] = summarize_timing_distribution(signatures)
    out["cache_proxy_summary"] = summarize_cache_proxies(signatures)

    # One canonical comparison table for quick analyst use.
    out["event_library_comparison"] = out["event_set_sizes"].merge(
        out["timing_distribution_summary"], on="event_set_id", how="left"
    ).merge(out["cache_proxy_summary"], on="event_set_id", how="left")

    if record_observability:
        from qhpc_cache.cache_workload_mapping import record_spine_pipeline_observation
        from qhpc_cache.workload_signatures import WORKLOAD_SPINE_EVENT_WINDOW

        join_width = int(normalized["join_width"].max()) if len(normalized) and "join_width" in normalized.columns else 0
        align_quality = (
            float(normalized["alignment_match_quality"].mean())
            if len(normalized) and "alignment_match_quality" in normalized.columns
            else -1.0
        )
        notes = json.dumps(
            {"deferred_hpc_workloads": len(deferred_notes), "selected_sets": list(selected_set_ids or [])}
        )[:500]
        record_spine_pipeline_observation(
            run_id=run_id or "event_library_compare",
            workload_spine_id=WORKLOAD_SPINE_EVENT_WINDOW,
            pipeline_phase="event_library_compare",
            source_datasets="normalized_event_rows",
            row_count_primary=int(len(raw_event_rows) if raw_event_rows is not None else 0),
            row_count_after_join=int(len(normalized)),
            join_width_estimate=join_width,
            alignment_match_rate=align_quality,
            reuse_alignment_opportunities=int(
                out["workload_signature_summary"]["repeated_join_pattern_markers"].sum()
                if len(out["workload_signature_summary"])
                else 0
            ),
            notes=notes,
        )
    return out


def _safe_plot_library() -> Tuple[Any, Any]:
    try:
        import matplotlib.pyplot as plt  # noqa: WPS433
    except Exception:
        return None, None

    try:
        import seaborn as sns  # noqa: WPS433

        return plt, sns
    except Exception:
        return plt, None


def _plot_bar(
    frame: Any,
    *,
    x: str,
    y: str,
    hue: str = "",
    title: str,
    output_path: Path,
) -> Optional[Path]:
    if frame is None or len(frame) == 0:
        return None
    plt, sns = _safe_plot_library()
    if plt is None:
        return None
    fig = plt.figure(figsize=(9, 4.5))
    if sns is not None:
        ax = fig.add_subplot(111)
        if hue:
            sns.barplot(data=frame, x=x, y=y, hue=hue, ax=ax)
        else:
            sns.barplot(data=frame, x=x, y=y, ax=ax)
    else:
        ax = fig.add_subplot(111)
        if hue:
            pvt = frame.pivot_table(index=x, columns=hue, values=y, aggfunc="mean")
            pvt.plot(kind="bar", ax=ax)
        else:
            frame.groupby(x)[y].mean().plot(kind="bar", ax=ax)
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=140)
    plt.close(fig)
    return output_path


def _write_markdown_summary(path: Path, *, title: str, bullets: Sequence[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {title}", ""]
    for b in bullets:
        lines.append(f"- {b}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def export_event_library_comparison(
    *,
    comparison_result: Mapping[str, Any],
    output_dir: str | Path,
) -> Dict[str, str]:
    """Export canonical event-library package (CSV, JSON, markdown, plots)."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # CSV package
    csv_event_window_manifest = out / "event_window_manifest.csv"
    csv_alignment_quality = out / "event_window_alignment_quality.csv"
    csv_library_cmp = out / "event_library_comparison.csv"
    csv_signature = out / "workload_signature_summary.csv"
    csv_timing = out / "timing_distribution_summary.csv"
    csv_cache = out / "cache_proxy_summary.csv"

    comparison_result["event_window_manifest"].to_csv(csv_event_window_manifest, index=False)
    comparison_result["alignment_quality"].to_csv(csv_alignment_quality, index=False)
    comparison_result["event_library_comparison"].to_csv(csv_library_cmp, index=False)
    comparison_result["workload_signature_summary"].to_csv(csv_signature, index=False)
    comparison_result["timing_distribution_summary"].to_csv(csv_timing, index=False)
    comparison_result["cache_proxy_summary"].to_csv(csv_cache, index=False)

    # JSON manifests
    json_event_set_manifest = out / "event_set_manifest.json"
    json_window_policy = out / "window_policy_manifest.json"
    json_cmp_manifest = out / "event_library_comparison_manifest.json"
    json_event_set_manifest.write_text(
        json.dumps(comparison_result["event_set_manifest"], indent=2),
        encoding="utf-8",
    )
    json_window_policy.write_text(
        json.dumps(comparison_result["window_policy_manifest"], indent=2),
        encoding="utf-8",
    )
    cmp_manifest = {
        "schema_version": "1.0",
        "output_files": [
            csv_event_window_manifest.name,
            csv_alignment_quality.name,
            csv_library_cmp.name,
            csv_signature.name,
            csv_timing.name,
            csv_cache.name,
        ],
        "deferred_hpc_workloads": list(comparison_result.get("deferred_hpc_workloads", [])),
    }
    json_cmp_manifest.write_text(json.dumps(cmp_manifest, indent=2), encoding="utf-8")

    # Markdown summaries
    md_event_set_summary = out / "event_set_summary.md"
    md_cmp_summary = out / "event_library_comparison_summary.md"
    md_sig_summary = out / "workload_signature_summary.md"
    size_rows = comparison_result["event_set_sizes"]
    bullets_a = [
        f"{r.event_set_id}: defined_events={int(r.defined_event_count)} materialized_rows={int(r.materialized_row_count)}"
        for r in size_rows.itertuples(index=False)
    ]
    _write_markdown_summary(md_event_set_summary, title="Event Set Summary", bullets=bullets_a)
    bullets_b = [
        f"{r.event_set_id}: timing_p90_ms={float(r.timing_p90_ms):.2f} cache_reuse_density={float(r.cache_proxy_reuse_density):.4f}"
        for r in comparison_result["event_library_comparison"].fillna(0).itertuples(index=False)
    ]
    _write_markdown_summary(md_cmp_summary, title="Event Library Comparison Summary", bullets=bullets_b)
    bullets_c = [
        (
            f"{r.event_set_id}/{r.window_family_label}/{r.intraday_slice_label}: "
            f"rows={int(r.row_count)} align_q={float(r.identifier_match_quality):.4f} "
            f"reuse={float(r.cache_proxy_reuse_density):.4f}"
        )
        for r in comparison_result["workload_signature_summary"].fillna(0).itertuples(index=False)
    ]
    _write_markdown_summary(md_sig_summary, title="Workload Signature Summary", bullets=bullets_c[:120])

    # Plots
    plot_set_size = out / "plot_event_set_size_comparison.png"
    plot_category = out / "plot_category_distribution_comparison.png"
    plot_window = out / "plot_window_family_comparison.png"
    plot_align = out / "plot_alignment_quality_comparison.png"
    plot_timing = out / "plot_timing_distribution_comparison.png"
    plot_sig = out / "plot_workload_signature_comparison.png"

    _plot_bar(
        comparison_result["event_set_sizes"],
        x="event_set_id",
        y="materialized_row_count",
        title="Event-Set Size Comparison",
        output_path=plot_set_size,
    )
    _plot_bar(
        comparison_result["category_distribution"],
        x="event_set_id",
        y="materialized_row_count",
        hue="category_label",
        title="Category Distribution Comparison",
        output_path=plot_category,
    )
    _plot_bar(
        comparison_result["window_family_behavior"],
        x="window_family_label",
        y="row_count",
        hue="event_set_id",
        title="Window-Family Comparison",
        output_path=plot_window,
    )
    _plot_bar(
        comparison_result["alignment_quality"],
        x="event_set_id",
        y="alignment_quality_mean",
        hue="window_family_label",
        title="Alignment-Quality Comparison",
        output_path=plot_align,
    )
    _plot_bar(
        comparison_result["timing_distribution_summary"],
        x="event_set_id",
        y="timing_p90_ms",
        title="Timing Distribution Comparison",
        output_path=plot_timing,
    )
    _plot_bar(
        comparison_result["workload_signature_summary"],
        x="event_set_id",
        y="cache_proxy_reuse_density",
        hue="window_family_label",
        title="Workload-Signature Comparison",
        output_path=plot_sig,
    )

    return {
        "event_window_manifest_csv": str(csv_event_window_manifest),
        "event_window_alignment_quality_csv": str(csv_alignment_quality),
        "event_library_comparison_csv": str(csv_library_cmp),
        "workload_signature_summary_csv": str(csv_signature),
        "timing_distribution_summary_csv": str(csv_timing),
        "cache_proxy_summary_csv": str(csv_cache),
        "event_set_manifest_json": str(json_event_set_manifest),
        "window_policy_manifest_json": str(json_window_policy),
        "event_library_comparison_manifest_json": str(json_cmp_manifest),
        "event_set_summary_md": str(md_event_set_summary),
        "event_library_comparison_summary_md": str(md_cmp_summary),
        "workload_signature_summary_md": str(md_sig_summary),
        "plot_event_set_size_comparison": str(plot_set_size),
        "plot_category_distribution_comparison": str(plot_category),
        "plot_window_family_comparison": str(plot_window),
        "plot_alignment_quality_comparison": str(plot_align),
        "plot_timing_distribution_comparison": str(plot_timing),
        "plot_workload_signature_comparison": str(plot_sig),
    }
