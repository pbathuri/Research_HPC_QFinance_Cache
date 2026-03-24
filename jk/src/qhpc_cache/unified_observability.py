"""Unified observability across canonical workload families.

Schema-first design:
1) adapt family-specific bundles into one common table
2) run ranking/similarity on top of that common table
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from qhpc_cache.workload_signatures import (
    WORKLOAD_SPINE_EVENT_WINDOW,
    WORKLOAD_SPINE_FEATURE_PANEL,
    WORKLOAD_SPINE_OPTION_PRICING,
    WORKLOAD_SPINE_PORTFOLIO_RISK,
    workload_spine_rank_for_id,
)


COMMON_SCHEMA_COLUMNS: Tuple[str, ...] = (
    "workload_family",
    "workload_variant",
    "workload_spine_id",
    "workload_spine_rank",
    "deterministic_label",
    "source_dataset_labels",
    "source_outputs_used",
    "n_rows",
    "n_entities",
    "n_dates_or_periods",
    "join_width",
    "feature_dim_before",
    "feature_dim_after",
    "scenario_count",
    "batch_size",
    "parameter_grid_width",
    "timing_p50",
    "timing_p90",
    "timing_p99",
    "timing_p999",
    "reuse_proxy_count",
    "reconstruction_proxy_count",
    "cache_proxy_reuse_density",
    "cache_proxy_locality_hint",
    "cache_proxy_alignment_penalty",
    "execution_environment",
    "mac_executable_now",
    "deferred_to_hpc",
    "metric_lineage",
    "unavailable_fields",
    "notes",
)


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_mean(series: Any) -> float:
    if series is None or len(series) == 0:
        return 0.0
    return float(series.mean())


def _safe_nunique(series: Any) -> int:
    if series is None or len(series) == 0:
        return 0
    return int(series.dropna().nunique())


def _quantile(series: Any, q: float) -> float:
    if series is None or len(series) == 0:
        return 0.0
    return float(series.quantile(q))


def _normalize_sources(labels: Any) -> str:
    if labels is None:
        return ""
    if isinstance(labels, str):
        return labels
    if hasattr(labels, "__iter__"):
        vals = [str(x) for x in labels if str(x)]
        return ";".join(sorted(set(vals)))
    return str(labels)


def _environment_label() -> str:
    return f"{platform.system().lower()}::{platform.machine().lower()}"


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y")
    if value is None:
        return False
    return bool(value)


def _empty_common_frame() -> Any:
    import pandas as pd

    return pd.DataFrame(columns=list(COMMON_SCHEMA_COLUMNS))


def _base_row(
    *,
    workload_family: str,
    workload_variant: str,
    workload_spine_id: str,
    deterministic_label: str,
    source_dataset_labels: str,
    source_outputs_used: str,
    execution_environment: str,
    mac_executable_now: bool,
    deferred_to_hpc: bool,
    unavailable_fields: Sequence[str],
    metric_lineage: str,
    notes: str,
) -> Dict[str, Any]:
    row = {c: None for c in COMMON_SCHEMA_COLUMNS}
    row.update(
        {
            "workload_family": workload_family,
            "workload_variant": workload_variant,
            "workload_spine_id": workload_spine_id,
            "workload_spine_rank": workload_spine_rank_for_id(workload_spine_id),
            "deterministic_label": deterministic_label,
            "source_dataset_labels": source_dataset_labels,
            "source_outputs_used": source_outputs_used,
            "execution_environment": execution_environment,
            "mac_executable_now": bool(mac_executable_now),
            "deferred_to_hpc": bool(deferred_to_hpc),
            "metric_lineage": metric_lineage,
            "unavailable_fields": ";".join(unavailable_fields),
            "notes": notes,
        }
    )
    return row


def adapt_event_workload_to_common_schema(
    *,
    event_comparison_result: Optional[Mapping[str, Any]] = None,
    cache_study_result: Optional[Mapping[str, Any]] = None,
    execution_environment: str = "",
) -> Any:
    """Adapt event-family outputs to the common unified schema."""
    import pandas as pd

    env = execution_environment or _environment_label()
    rows: List[Dict[str, Any]] = []

    if event_comparison_result is not None:
        ew = event_comparison_result.get("event_window_manifest", pd.DataFrame())
        sig = event_comparison_result.get("workload_signature_summary", pd.DataFrame())
        cache = event_comparison_result.get("cache_proxy_summary", pd.DataFrame())
        timing = event_comparison_result.get("timing_distribution_summary", pd.DataFrame())
        cmp_frame = event_comparison_result.get("event_library_comparison", pd.DataFrame())
        deferred = list(event_comparison_result.get("deferred_hpc_workloads", []))

        det = hashlib.sha256(
            json.dumps(
                {
                    "rows": int(len(ew)) if ew is not None else 0,
                    "sets": sorted(ew.get("event_set_id", pd.Series(dtype=str)).dropna().unique().tolist())
                    if ew is not None and len(ew)
                    else [],
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()[:18]
        base = _base_row(
            workload_family="event_workloads",
            workload_variant="aligned_event_windows",
            workload_spine_id=WORKLOAD_SPINE_EVENT_WINDOW,
            deterministic_label=f"event::{det}",
            source_dataset_labels=_normalize_sources(
                ew.get("source_datasets", pd.Series(dtype=str)).dropna().unique().tolist()
                if ew is not None and len(ew)
                else ["taq_kdb;wrds_link;crsp"]
            ),
            source_outputs_used="event_window_manifest;workload_signature_summary;timing_distribution_summary;cache_proxy_summary",
            execution_environment=env,
            mac_executable_now=True,
            deferred_to_hpc=len(deferred) > 0,
            unavailable_fields=["scenario_count", "batch_size", "parameter_grid_width"],
            metric_lineage=(
                "direct:n_rows,n_entities,join_width,timing_*;"
                "derived:n_dates_or_periods,reuse_proxy_count;"
                "proxy:cache_proxy_*"
            ),
            notes=(
                "event adapter uses normalized event windows and signature summaries; "
                "cache-proxy fields remain proxy-level evidence"
            ),
        )
        base["n_rows"] = int(len(ew)) if ew is not None else 0
        base["n_entities"] = (
            _safe_nunique(ew.get("permno", pd.Series(dtype=float))) if ew is not None and len(ew) else 0
        )
        if ew is not None and len(ew) and "window_start" in ew.columns:
            base["n_dates_or_periods"] = _safe_nunique(
                pd.to_datetime(ew["window_start"], errors="coerce").dt.normalize()
            )
        else:
            base["n_dates_or_periods"] = 0
        base["join_width"] = _safe_mean(ew.get("join_width", pd.Series(dtype=float))) if ew is not None else 0.0
        base["timing_p50"] = (
            _safe_mean(timing.get("timing_p50_ms", pd.Series(dtype=float))) if timing is not None else 0.0
        )
        base["timing_p90"] = (
            _safe_mean(timing.get("timing_p90_ms", pd.Series(dtype=float))) if timing is not None else 0.0
        )
        base["timing_p99"] = (
            _safe_mean(timing.get("timing_p99_ms", pd.Series(dtype=float))) if timing is not None else 0.0
        )
        base["timing_p999"] = (
            _safe_mean(timing.get("timing_p999_ms", pd.Series(dtype=float))) if timing is not None else 0.0
        )
        if sig is not None and len(sig):
            base["reuse_proxy_count"] = int(
                sig.get("repeated_join_pattern_markers", pd.Series(dtype=float)).sum()
                + sig.get("reusable_derived_structure_markers", pd.Series(dtype=float)).sum()
            )
            base["reconstruction_proxy_count"] = int(
                sig.get("repeated_event_window_reconstruction_markers", pd.Series(dtype=float)).sum()
            )
            base["cache_proxy_reuse_density"] = _safe_mean(
                sig.get("cache_proxy_reuse_density", pd.Series(dtype=float))
            )
            base["cache_proxy_locality_hint"] = _safe_mean(
                sig.get("cache_proxy_locality_hint", pd.Series(dtype=float))
            )
            base["cache_proxy_alignment_penalty"] = _safe_mean(
                sig.get("cache_proxy_alignment_penalty", pd.Series(dtype=float))
            )
        elif cache is not None and len(cache):
            base["reuse_proxy_count"] = 0
            base["reconstruction_proxy_count"] = 0
            base["cache_proxy_reuse_density"] = _safe_mean(
                cache.get("cache_proxy_reuse_density", pd.Series(dtype=float))
            )
            base["cache_proxy_locality_hint"] = _safe_mean(
                cache.get("cache_proxy_locality_hint", pd.Series(dtype=float))
            )
            base["cache_proxy_alignment_penalty"] = _safe_mean(
                cache.get("cache_proxy_alignment_penalty", pd.Series(dtype=float))
            )
        rows.append(base)

        cmp_row = dict(base)
        cmp_row["workload_variant"] = "event_library_comparison"
        cmp_row["deterministic_label"] = f"event_cmp::{det}"
        cmp_row["source_outputs_used"] = "event_library_comparison;event_set_sizes;timing_distribution_summary;cache_proxy_summary"
        cmp_row["n_rows"] = int(len(cmp_frame)) if cmp_frame is not None else 0
        cmp_row["n_entities"] = (
            _safe_nunique(cmp_frame.get("event_set_id", pd.Series(dtype=str)))
            if cmp_frame is not None and len(cmp_frame)
            else 0
        )
        cmp_row["n_dates_or_periods"] = cmp_row["n_entities"]
        rows.append(cmp_row)

    if cache_study_result is not None:
        normalized = cache_study_result.get("normalized_rows", pd.DataFrame())
        reuse = cache_study_result.get("reuse_reconstruction_summary", pd.DataFrame())
        timing = cache_study_result.get("timing_summary", pd.DataFrame())
        proxies = cache_study_result.get("reuse_proxy_summary", pd.DataFrame())
        deferred = list(cache_study_result.get("deferred_hpc_workloads", []))
        det = hashlib.sha256(
            json.dumps(
                {
                    "rows": int(len(normalized)) if normalized is not None else 0,
                    "sets": sorted(
                        normalized.get("event_set_id", pd.Series(dtype=str)).dropna().unique().tolist()
                    )
                    if normalized is not None and len(normalized)
                    else [],
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()[:18]
        row = _base_row(
            workload_family="event_workloads",
            workload_variant="cache_study_event_analysis",
            workload_spine_id=WORKLOAD_SPINE_EVENT_WINDOW,
            deterministic_label=f"event_cache::{det}",
            source_dataset_labels="event_window_manifest;event_library_comparison",
            source_outputs_used="within_set_summary;cross_set_summary;timing_summary;reuse_reconstruction_summary;reuse_proxy_summary",
            execution_environment=env,
            mac_executable_now=True,
            deferred_to_hpc=len(deferred) > 0,
            unavailable_fields=["scenario_count", "batch_size", "parameter_grid_width"],
            metric_lineage=(
                "direct:n_rows,n_entities,timing_*;"
                "derived:n_dates_or_periods,reuse_proxy_count,reconstruction_proxy_count;"
                "proxy:cache_proxy_*"
            ),
            notes=(
                "event cache-study adapter uses within/cross summaries; "
                "cross-family comparability is approximate when family-specific semantics differ"
            ),
        )
        row["n_rows"] = int(len(normalized)) if normalized is not None else 0
        row["n_entities"] = (
            _safe_nunique(normalized.get("permno", pd.Series(dtype=float)))
            if normalized is not None and len(normalized)
            else 0
        )
        row["n_dates_or_periods"] = (
            _safe_nunique(normalized.get("window_family_label", pd.Series(dtype=str)))
            if normalized is not None and len(normalized)
            else 0
        )
        row["join_width"] = (
            _safe_mean(normalized.get("join_width", pd.Series(dtype=float)))
            if normalized is not None and len(normalized)
            else 0.0
        )
        row["timing_p50"] = _safe_mean(timing.get("timing_p50_ms", pd.Series(dtype=float)))
        row["timing_p90"] = _safe_mean(timing.get("timing_p90_ms", pd.Series(dtype=float)))
        row["timing_p99"] = _safe_mean(timing.get("timing_p99_ms", pd.Series(dtype=float)))
        row["timing_p999"] = _safe_mean(timing.get("timing_p999_ms", pd.Series(dtype=float)))
        row["reuse_proxy_count"] = int(
            reuse.get("repeated_join_pattern_markers", pd.Series(dtype=float)).sum()
            + reuse.get("reusable_derived_structure_markers", pd.Series(dtype=float)).sum()
        )
        row["reconstruction_proxy_count"] = int(
            reuse.get("repeated_event_window_reconstruction_markers", pd.Series(dtype=float)).sum()
        )
        row["cache_proxy_reuse_density"] = _safe_mean(
            proxies.get("cache_proxy_reuse_density", pd.Series(dtype=float))
        )
        row["cache_proxy_locality_hint"] = _safe_mean(
            proxies.get("cache_proxy_locality_hint", pd.Series(dtype=float))
        )
        row["cache_proxy_alignment_penalty"] = _safe_mean(
            proxies.get("cache_proxy_alignment_penalty", pd.Series(dtype=float))
        )
        rows.append(row)

    return pd.DataFrame(rows) if rows else _empty_common_frame()


def adapt_feature_panel_workload_to_common_schema(
    feature_panel_bundle: Optional[Mapping[str, Any]],
    *,
    execution_environment: str = "",
) -> Any:
    """Adapt feature-panel workload variants into the common schema."""
    import pandas as pd

    if not feature_panel_bundle:
        return _empty_common_frame()
    env = execution_environment or _environment_label()
    manifest = feature_panel_bundle.get("variant_manifest", pd.DataFrame())
    deferred = list(feature_panel_bundle.get("deferred_hpc_workloads", []))
    if manifest is None or len(manifest) == 0:
        return _empty_common_frame()
    rows: List[Dict[str, Any]] = []
    for r in manifest.itertuples(index=False):
        row = _base_row(
            workload_family="feature_panel_workloads",
            workload_variant=str(r.panel_variant_label),
            workload_spine_id=WORKLOAD_SPINE_FEATURE_PANEL,
            deterministic_label=str(r.deterministic_label),
            source_dataset_labels="crsp.dsf;rates_data;event_tags;alpha_features",
            source_outputs_used="variant_manifest;timing_summary;reuse_proxy_summary",
            execution_environment=env,
            mac_executable_now=True,
            deferred_to_hpc=len(deferred) > 0,
            unavailable_fields=["scenario_count", "batch_size", "parameter_grid_width", "cache_proxy_locality_hint", "cache_proxy_alignment_penalty"],
            metric_lineage=(
                "direct:n_rows,n_entities,n_dates_or_periods,feature_dim_*,timing_p*;"
                "derived:reuse_proxy_count,reconstruction_proxy_count;"
                "proxy:cache_proxy_reuse_density"
            ),
            notes=(
                "feature adapter maps panel variants directly; "
                "join_width is approximated by pre-condense feature width"
            ),
        )
        row["n_rows"] = int(r.n_rows)
        row["n_entities"] = int(r.n_securities)
        row["n_dates_or_periods"] = int(r.n_dates)
        row["join_width"] = float(r.feature_count_before_condense)
        row["feature_dim_before"] = int(r.feature_count_before_condense)
        row["feature_dim_after"] = int(r.feature_count_after_condense)
        row["timing_p50"] = float(r.panel_build_timing_ms)
        row["timing_p90"] = float(r.panel_build_timing_ms)
        row["timing_p99"] = float(r.panel_build_timing_ms)
        row["timing_p999"] = float(r.panel_build_timing_ms)
        row["reuse_proxy_count"] = int(
            int(r.repeated_derived_structure_markers)
            + int(r.repeated_join_pattern_markers)
        )
        row["reconstruction_proxy_count"] = int(r.repeated_reconstruction_markers)
        row["cache_proxy_reuse_density"] = float(r.reuse_density)
        row["cache_proxy_locality_hint"] = None
        row["cache_proxy_alignment_penalty"] = None
        rows.append(row)
    return pd.DataFrame(rows)


def adapt_portfolio_risk_workload_to_common_schema(
    portfolio_risk_bundle: Optional[Mapping[str, Any]],
    *,
    execution_environment: str = "",
) -> Any:
    """Adapt portfolio-risk workload variants into the common schema."""
    import pandas as pd

    if not portfolio_risk_bundle:
        return _empty_common_frame()
    env = execution_environment or _environment_label()
    manifest = portfolio_risk_bundle.get("workload_manifest", pd.DataFrame())
    timing = portfolio_risk_bundle.get("portfolio_risk_timing_summary", pd.DataFrame())
    reuse = portfolio_risk_bundle.get("portfolio_risk_reuse_proxy_summary", pd.DataFrame())
    recomputation = portfolio_risk_bundle.get("recomputation_patterns", pd.DataFrame())
    deferred = list(portfolio_risk_bundle.get("deferred_hpc_workloads", []))
    if manifest is None or len(manifest) == 0:
        return _empty_common_frame()
    rows: List[Dict[str, Any]] = []
    for r in manifest.itertuples(index=False):
        variant = str(r.workload_variant_label)
        t = timing.loc[timing["risk_workload_variant_label"] == variant] if len(timing) else pd.DataFrame()
        reuse_row = reuse.iloc[0] if len(reuse) else None
        recon_row = recomputation.iloc[0] if len(recomputation) else None
        row = _base_row(
            workload_family="portfolio_risk_workloads",
            workload_variant=variant,
            workload_spine_id=WORKLOAD_SPINE_PORTFOLIO_RISK,
            deterministic_label=str(r.deterministic_label),
            source_dataset_labels="crsp.dsf;rates_data;event_tags;feature_panel_outputs",
            source_outputs_used="workload_manifest;portfolio_risk_timing_summary;portfolio_risk_reuse_proxy_summary;recomputation_patterns",
            execution_environment=env,
            mac_executable_now=True,
            deferred_to_hpc=len(deferred) > 0,
            unavailable_fields=["parameter_grid_width", "cache_proxy_locality_hint", "cache_proxy_alignment_penalty"],
            metric_lineage=(
                "direct:n_rows,n_entities,n_dates_or_periods,scenario_count,timing_p*;"
                "derived:feature_dim_*,batch_size,reuse_proxy_count,reconstruction_proxy_count;"
                "proxy:cache_proxy_reuse_density"
            ),
            notes=(
                "risk adapter uses broad-vs-slice manifests; "
                "feature dimensions are structural proxies from security/slice widths"
            ),
        )
        row["n_rows"] = int(r.n_rows)
        row["n_entities"] = int(r.n_securities)
        row["n_dates_or_periods"] = int(r.n_dates)
        row["join_width"] = int(r.n_securities)
        row["feature_dim_before"] = int(r.n_securities)
        row["feature_dim_after"] = int(r.n_securities) + int(r.scenario_count)
        row["scenario_count"] = int(r.scenario_count)
        row["batch_size"] = int(r.slice_count) if "slice_count" in manifest.columns else 0
        row["timing_p50"] = _safe_mean(t.get("timing_ms", pd.Series(dtype=float)))
        row["timing_p90"] = _quantile(t.get("timing_ms", pd.Series(dtype=float)), 0.90)
        row["timing_p99"] = _quantile(t.get("timing_ms", pd.Series(dtype=float)), 0.99)
        row["timing_p999"] = _quantile(t.get("timing_ms", pd.Series(dtype=float)), 0.999)
        if reuse_row is not None and variant.endswith("slice_scenario_risk"):
            row["reuse_proxy_count"] = int(
                int(reuse_row.get("repeated_slice_construction_markers", 0))
                + int(reuse_row.get("repeated_covariance_window_markers", 0))
                + int(reuse_row.get("repeated_aggregation_markers", 0))
            )
            row["cache_proxy_reuse_density"] = float(reuse_row.get("reuse_density", 0.0))
        else:
            row["reuse_proxy_count"] = int(row["n_rows"])
            row["cache_proxy_reuse_density"] = 0.0
        row["reconstruction_proxy_count"] = (
            int(recon_row.get("repeated_slice_construction_markers", 0))
            if recon_row is not None and variant.endswith("slice_scenario_risk")
            else 0
        )
        row["cache_proxy_locality_hint"] = None
        row["cache_proxy_alignment_penalty"] = None
        rows.append(row)
    return pd.DataFrame(rows)


def adapt_pricing_workload_to_common_schema(
    pricing_bundle: Optional[Mapping[str, Any]],
    *,
    execution_environment: str = "",
) -> Any:
    """Adapt option-pricing workload variants into the common schema."""
    import pandas as pd

    if not pricing_bundle:
        return _empty_common_frame()
    env = execution_environment or _environment_label()
    manifest = pricing_bundle.get("pricing_workload_manifest", pd.DataFrame())
    timing = pricing_bundle.get("pricing_timing_summary", pd.DataFrame())
    reuse = pricing_bundle.get("pricing_reuse_proxy_summary", pd.DataFrame())
    recomputation = pricing_bundle.get("pricing_recomputation_summary", pd.DataFrame())
    deferred = list(pricing_bundle.get("hpc_deferred_workloads", []))
    run_id = str(pricing_bundle.get("run_id", ""))
    if manifest is None or len(manifest) == 0:
        return _empty_common_frame()
    rows: List[Dict[str, Any]] = []
    for r in manifest.itertuples(index=False):
        variant = str(r.workload_variant_label)
        t = timing.loc[timing["workload_variant_label"] == variant] if len(timing) else pd.DataFrame()
        u = reuse.loc[reuse["workload_variant_label"] == variant] if len(reuse) else pd.DataFrame()
        rc = recomputation.loc[recomputation["workload_variant_label"] == variant] if len(recomputation) else pd.DataFrame()
        det = hashlib.sha256(f"{run_id}|{variant}|{int(r.contract_count)}".encode()).hexdigest()[:16]
        row = _base_row(
            workload_family="pricing_workloads",
            workload_variant=variant,
            workload_spine_id=WORKLOAD_SPINE_OPTION_PRICING,
            deterministic_label=f"pricing::{det}",
            source_dataset_labels="pricing.py;analytic_pricing.py;rates_data",
            source_outputs_used="pricing_workload_manifest;pricing_timing_summary;pricing_reuse_proxy_summary;pricing_recomputation_summary",
            execution_environment=env,
            mac_executable_now=True,
            deferred_to_hpc=(str(r.deferred_hpc_notes).strip() != "") or len(deferred) > 0,
            unavailable_fields=["n_dates_or_periods", "scenario_count", "cache_proxy_locality_hint", "cache_proxy_alignment_penalty"],
            metric_lineage=(
                "direct:n_entities,batch_size,parameter_grid_width,timing_p*;"
                "derived:n_rows,feature_dim_*,reuse_proxy_count,reconstruction_proxy_count;"
                "proxy:cache_proxy_reuse_density"
            ),
            notes=(
                "pricing adapter compares model-family and batch/Greeks variants; "
                "reconstruction proxies are derived from repeated repricing structures"
            ),
        )
        row["n_rows"] = int(r.repeated_pricing_call_count)
        row["n_entities"] = int(r.contract_count)
        row["n_dates_or_periods"] = 0
        row["join_width"] = int(r.batch_size)
        row["feature_dim_before"] = int(r.parameter_grid_width)
        row["feature_dim_after"] = int(r.parameter_grid_width) + int(r.greeks_count)
        row["scenario_count"] = 0
        row["batch_size"] = int(r.batch_size)
        row["parameter_grid_width"] = int(r.parameter_grid_width)
        row["timing_p50"] = _safe_mean(t.get("timing_ms_p50", pd.Series(dtype=float)))
        row["timing_p90"] = _safe_mean(t.get("timing_ms_p90", pd.Series(dtype=float)))
        row["timing_p99"] = _safe_mean(t.get("timing_ms_p99", pd.Series(dtype=float)))
        row["timing_p999"] = row["timing_p99"]
        marker_count = (
            float(u["repeated_parameter_structure_markers"].iloc[0])
            + float(u["repeated_batch_family_markers"].iloc[0])
            if len(u)
            else 0.0
        )
        row["reuse_proxy_count"] = int(marker_count + int(r.repeated_pricing_call_count))
        row["reconstruction_proxy_count"] = (
            int(rc["repeated_pricing_call_count"].iloc[0]) if len(rc) else int(r.repeated_pricing_call_count)
        )
        if len(u):
            density = marker_count / max(1.0, float(u["row_count"].iloc[0]))
        else:
            density = 0.0
        row["cache_proxy_reuse_density"] = float(density)
        row["cache_proxy_locality_hint"] = None
        row["cache_proxy_alignment_penalty"] = None
        rows.append(row)
    return pd.DataFrame(rows)


def build_unified_workload_observation_table(
    *,
    event_comparison_result: Optional[Mapping[str, Any]] = None,
    cache_study_result: Optional[Mapping[str, Any]] = None,
    feature_panel_bundle: Optional[Mapping[str, Any]] = None,
    portfolio_risk_bundle: Optional[Mapping[str, Any]] = None,
    pricing_bundle: Optional[Mapping[str, Any]] = None,
    execution_environment: str = "",
) -> Any:
    """Build one canonical observation table across event/panel/risk/pricing families."""
    import pandas as pd

    env = execution_environment or _environment_label()
    parts = [
        adapt_event_workload_to_common_schema(
            event_comparison_result=event_comparison_result,
            cache_study_result=cache_study_result,
            execution_environment=env,
        ),
        adapt_feature_panel_workload_to_common_schema(
            feature_panel_bundle,
            execution_environment=env,
        ),
        adapt_portfolio_risk_workload_to_common_schema(
            portfolio_risk_bundle,
            execution_environment=env,
        ),
        adapt_pricing_workload_to_common_schema(
            pricing_bundle,
            execution_environment=env,
        ),
    ]
    parts = [p for p in parts if p is not None and len(p)]
    if not parts:
        return _empty_common_frame()
    df = pd.concat(parts, ignore_index=True)
    for col in COMMON_SCHEMA_COLUMNS:
        if col not in df.columns:
            df[col] = None
    numeric_cols = [
        "n_rows",
        "n_entities",
        "n_dates_or_periods",
        "join_width",
        "feature_dim_before",
        "feature_dim_after",
        "scenario_count",
        "batch_size",
        "parameter_grid_width",
        "timing_p50",
        "timing_p90",
        "timing_p99",
        "timing_p999",
        "reuse_proxy_count",
        "reconstruction_proxy_count",
        "cache_proxy_reuse_density",
        "cache_proxy_locality_hint",
        "cache_proxy_alignment_penalty",
        "workload_spine_rank",
    ]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "mac_executable_now" in df.columns:
        df["mac_executable_now"] = df["mac_executable_now"].apply(_to_bool)
    if "deferred_to_hpc" in df.columns:
        df["deferred_to_hpc"] = df["deferred_to_hpc"].apply(_to_bool)
    return df[list(COMMON_SCHEMA_COLUMNS)].copy()


def compare_workload_families_by_shape(unified_observations: Any) -> Any:
    """Cross-family shape comparison (rows/entities/join/dimensionality)."""
    if unified_observations is None or len(unified_observations) == 0:
        return _empty_common_frame().head(0)
    grp = unified_observations.groupby("workload_family", dropna=False).agg(
        variant_count=("workload_variant", "nunique"),
        n_rows_mean=("n_rows", "mean"),
        n_entities_mean=("n_entities", "mean"),
        join_width_mean=("join_width", "mean"),
        feature_dim_before_mean=("feature_dim_before", "mean"),
        feature_dim_after_mean=("feature_dim_after", "mean"),
    )
    out = grp.reset_index()
    out["shape_complexity_score"] = (
        0.30 * out["n_rows_mean"].rank(pct=True)
        + 0.25 * out["n_entities_mean"].rank(pct=True)
        + 0.20 * out["join_width_mean"].fillna(0.0).rank(pct=True)
        + 0.25 * out["feature_dim_after_mean"].fillna(0.0).rank(pct=True)
    )
    return out


def compare_workload_families_by_timing(unified_observations: Any) -> Any:
    """Cross-family timing comparison."""
    if unified_observations is None or len(unified_observations) == 0:
        return _empty_common_frame().head(0)
    grp = unified_observations.groupby("workload_family", dropna=False).agg(
        timing_p50_mean=("timing_p50", "mean"),
        timing_p90_mean=("timing_p90", "mean"),
        timing_p99_mean=("timing_p99", "mean"),
        timing_p999_mean=("timing_p999", "mean"),
    )
    out = grp.reset_index()
    out["timing_pressure_score"] = (
        0.25 * out["timing_p50_mean"].fillna(0.0).rank(pct=True)
        + 0.35 * out["timing_p90_mean"].fillna(0.0).rank(pct=True)
        + 0.30 * out["timing_p99_mean"].fillna(0.0).rank(pct=True)
        + 0.10 * out["timing_p999_mean"].fillna(0.0).rank(pct=True)
    )
    return out


def compare_workload_families_by_reuse_proxy(unified_observations: Any) -> Any:
    """Cross-family reuse/reconstruction proxy comparison."""
    if unified_observations is None or len(unified_observations) == 0:
        return _empty_common_frame().head(0)
    grp = unified_observations.groupby("workload_family", dropna=False).agg(
        reuse_proxy_count_mean=("reuse_proxy_count", "mean"),
        reconstruction_proxy_count_mean=("reconstruction_proxy_count", "mean"),
        cache_proxy_reuse_density_mean=("cache_proxy_reuse_density", "mean"),
    )
    out = grp.reset_index()
    out["reuse_intensity_score"] = (
        0.40 * out["reuse_proxy_count_mean"].fillna(0.0).rank(pct=True)
        + 0.35 * out["reconstruction_proxy_count_mean"].fillna(0.0).rank(pct=True)
        + 0.25 * out["cache_proxy_reuse_density_mean"].fillna(0.0).rank(pct=True)
    )
    return out


def compare_workload_families_by_dimension(unified_observations: Any) -> Any:
    """Cross-family dimension comparison."""
    if unified_observations is None or len(unified_observations) == 0:
        return _empty_common_frame().head(0)
    grp = unified_observations.groupby("workload_family", dropna=False).agg(
        feature_dim_before_mean=("feature_dim_before", "mean"),
        feature_dim_after_mean=("feature_dim_after", "mean"),
        join_width_mean=("join_width", "mean"),
        parameter_grid_width_mean=("parameter_grid_width", "mean"),
    )
    out = grp.reset_index()
    out["dimension_pressure_score"] = (
        0.35 * out["feature_dim_after_mean"].fillna(0.0).rank(pct=True)
        + 0.35 * out["join_width_mean"].fillna(0.0).rank(pct=True)
        + 0.30 * out["parameter_grid_width_mean"].fillna(0.0).rank(pct=True)
    )
    return out


def summarize_cross_family_similarity(unified_observations: Any) -> Any:
    """Approximate structural similarity across workload families."""
    import pandas as pd
    import numpy as np

    if unified_observations is None or len(unified_observations) == 0:
        return pd.DataFrame(
            columns=["workload_family_a", "workload_family_b", "similarity_score", "distance", "notes"]
        )
    fam = unified_observations.groupby("workload_family", dropna=False).agg(
        n_rows=("n_rows", "mean"),
        n_entities=("n_entities", "mean"),
        feature_dim_after=("feature_dim_after", "mean"),
        join_width=("join_width", "mean"),
        scenario_count=("scenario_count", "mean"),
        batch_size=("batch_size", "mean"),
        parameter_grid_width=("parameter_grid_width", "mean"),
        timing_p90=("timing_p90", "mean"),
        reuse_proxy_count=("reuse_proxy_count", "mean"),
        reconstruction_proxy_count=("reconstruction_proxy_count", "mean"),
    )
    fam = fam.fillna(0.0)
    vals = fam.values.astype(float)
    min_v = vals.min(axis=0)
    max_v = vals.max(axis=0)
    span = np.where((max_v - min_v) <= 1e-12, 1.0, max_v - min_v)
    scaled = (vals - min_v) / span
    labels = fam.index.tolist()
    rows: List[Dict[str, Any]] = []
    for i, a in enumerate(labels):
        for j, b in enumerate(labels):
            if j <= i:
                continue
            d = float(np.sqrt(((scaled[i] - scaled[j]) ** 2).sum()))
            sim = 1.0 / (1.0 + d)
            rows.append(
                {
                    "workload_family_a": a,
                    "workload_family_b": b,
                    "similarity_score": sim,
                    "distance": d,
                    "notes": "similarity is normalized structural approximation, not final workload clustering engine",
                }
            )
    return pd.DataFrame(rows).sort_values("similarity_score", ascending=False).reset_index(drop=True)


def rank_workload_families_for_cache_study_value(unified_observations: Any) -> Any:
    """Rank workload families for guided-cache follow-up value."""
    import pandas as pd

    if unified_observations is None or len(unified_observations) == 0:
        return pd.DataFrame(columns=["workload_family", "cache_study_value_score", "rank", "notes"])
    shape = compare_workload_families_by_shape(unified_observations)
    timing = compare_workload_families_by_timing(unified_observations)
    reuse = compare_workload_families_by_reuse_proxy(unified_observations)
    dim = compare_workload_families_by_dimension(unified_observations)
    merged = (
        shape.merge(timing[["workload_family", "timing_pressure_score"]], on="workload_family", how="left")
        .merge(reuse[["workload_family", "reuse_intensity_score"]], on="workload_family", how="left")
        .merge(dim[["workload_family", "dimension_pressure_score"]], on="workload_family", how="left")
    )
    merged["cache_study_value_score"] = (
        0.25 * merged["shape_complexity_score"]
        + 0.30 * merged["reuse_intensity_score"]
        + 0.25 * merged["timing_pressure_score"]
        + 0.20 * merged["dimension_pressure_score"]
    )
    merged["rank"] = merged["cache_study_value_score"].rank(method="dense", ascending=False).astype(int)
    merged["notes"] = "ranking layered on unified schema; score uses direct+derived+proxy fields"
    return merged[["workload_family", "cache_study_value_score", "rank", "notes"]].sort_values("rank").reset_index(drop=True)


def rank_workload_variants_for_reuse_potential(unified_observations: Any) -> Any:
    """Rank variants by reuse-potential proxies."""
    if unified_observations is None or len(unified_observations) == 0:
        return _empty_common_frame().head(0)
    df = unified_observations.copy()
    df["reuse_potential_score"] = (
        0.65 * df["reuse_proxy_count"].fillna(0.0).rank(pct=True)
        + 0.35 * df["cache_proxy_reuse_density"].fillna(0.0).rank(pct=True)
    )
    df["rank"] = df["reuse_potential_score"].rank(method="dense", ascending=False).astype(int)
    return df[
        ["workload_family", "workload_variant", "reuse_potential_score", "rank", "notes"]
    ].sort_values("rank").reset_index(drop=True)


def rank_workload_variants_for_reconstruction_repetition(unified_observations: Any) -> Any:
    """Rank variants by reconstruction-repetition proxies."""
    if unified_observations is None or len(unified_observations) == 0:
        return _empty_common_frame().head(0)
    df = unified_observations.copy()
    df["reconstruction_repetition_score"] = (
        0.75 * df["reconstruction_proxy_count"].fillna(0.0).rank(pct=True)
        + 0.25 * df["reuse_proxy_count"].fillna(0.0).rank(pct=True)
    )
    df["rank"] = df["reconstruction_repetition_score"].rank(method="dense", ascending=False).astype(int)
    return df[
        ["workload_family", "workload_variant", "reconstruction_repetition_score", "rank", "notes"]
    ].sort_values("rank").reset_index(drop=True)


def rank_workload_variants_for_mac_vs_hpc_priority(unified_observations: Any) -> Any:
    """Rank variants for Mac->HPC escalation priority."""
    if unified_observations is None or len(unified_observations) == 0:
        return _empty_common_frame().head(0)
    df = unified_observations.copy()
    df["max_dimension"] = df[["feature_dim_after", "join_width", "parameter_grid_width"]].fillna(0.0).max(axis=1)
    df["mac_hpc_priority_score"] = (
        0.35 * df["timing_p99"].fillna(0.0).rank(pct=True)
        + 0.25 * df["n_rows"].fillna(0.0).rank(pct=True)
        + 0.20 * df["max_dimension"].fillna(0.0).rank(pct=True)
        + 0.10 * df["reuse_proxy_count"].fillna(0.0).rank(pct=True)
        + 0.10 * df["deferred_to_hpc"].astype(int)
    )
    df["rank"] = df["mac_hpc_priority_score"].rank(method="dense", ascending=False).astype(int)
    q1 = _quantile(df["mac_hpc_priority_score"], 0.66)
    q2 = _quantile(df["mac_hpc_priority_score"], 0.33)
    df["priority_label"] = df["mac_hpc_priority_score"].apply(
        lambda x: "high" if x >= q1 else ("medium" if x >= q2 else "low")
    )
    return df[
        ["workload_family", "workload_variant", "mac_hpc_priority_score", "priority_label", "rank", "notes"]
    ].sort_values("rank").reset_index(drop=True)


def export_unified_workload_rankings(unified_observations: Any) -> Dict[str, Any]:
    """Compute all ranking tables on top of unified schema."""
    family_rank = rank_workload_families_for_cache_study_value(unified_observations)
    reuse_rank = rank_workload_variants_for_reuse_potential(unified_observations)
    recon_rank = rank_workload_variants_for_reconstruction_repetition(unified_observations)
    mac_hpc_rank = rank_workload_variants_for_mac_vs_hpc_priority(unified_observations)

    combined_rows: List[Dict[str, Any]] = []
    for r in family_rank.itertuples(index=False):
        combined_rows.append(
            {
                "ranking_axis": "family_cache_study_value",
                "workload_family": r.workload_family,
                "workload_variant": "",
                "score": float(r.cache_study_value_score),
                "rank": int(r.rank),
                "priority_label": "",
                "notes": str(r.notes),
            }
        )
    for axis, frame, score_col in (
        ("variant_reuse_potential", reuse_rank, "reuse_potential_score"),
        ("variant_reconstruction_repetition", recon_rank, "reconstruction_repetition_score"),
        ("variant_mac_vs_hpc_priority", mac_hpc_rank, "mac_hpc_priority_score"),
    ):
        if frame is None or len(frame) == 0:
            continue
        for r in frame.itertuples(index=False):
            combined_rows.append(
                {
                    "ranking_axis": axis,
                    "workload_family": str(r.workload_family),
                    "workload_variant": str(r.workload_variant),
                    "score": float(getattr(r, score_col)),
                    "rank": int(r.rank),
                    "priority_label": str(getattr(r, "priority_label", "")),
                    "notes": str(r.notes),
                }
            )
    import pandas as pd

    return {
        "family_rankings": family_rank,
        "reuse_rankings": reuse_rank,
        "reconstruction_rankings": recon_rank,
        "mac_hpc_rankings": mac_hpc_rank,
        "unified_rankings": pd.DataFrame(combined_rows).sort_values(
            ["ranking_axis", "rank"]
        ).reset_index(drop=True),
    }


def run_unified_observability_bundle(
    *,
    event_comparison_result: Optional[Mapping[str, Any]] = None,
    cache_study_result: Optional[Mapping[str, Any]] = None,
    feature_panel_bundle: Optional[Mapping[str, Any]] = None,
    portfolio_risk_bundle: Optional[Mapping[str, Any]] = None,
    pricing_bundle: Optional[Mapping[str, Any]] = None,
    run_id: str = "",
    execution_environment: str = "",
) -> Dict[str, Any]:
    """Build unified table first, then rankings/similarity on top."""
    import pandas as pd

    env = execution_environment or _environment_label()
    rid = run_id or f"unified_observability::{_now_iso()}"
    unified_obs = build_unified_workload_observation_table(
        event_comparison_result=event_comparison_result,
        cache_study_result=cache_study_result,
        feature_panel_bundle=feature_panel_bundle,
        portfolio_risk_bundle=portfolio_risk_bundle,
        pricing_bundle=pricing_bundle,
        execution_environment=env,
    )
    family_shape = compare_workload_families_by_shape(unified_obs)
    family_timing = compare_workload_families_by_timing(unified_obs)
    family_reuse = compare_workload_families_by_reuse_proxy(unified_obs)
    family_dim = compare_workload_families_by_dimension(unified_obs)
    family_dim = family_dim.rename(
        columns={"feature_dim_after_mean": "dimension_feature_dim_after_mean"}
    )
    family_summary = (
        family_shape.merge(
            family_timing[
                ["workload_family", "timing_p90_mean", "timing_pressure_score"]
            ],
            on="workload_family",
            how="left",
        )
        .merge(
            family_reuse[
                [
                    "workload_family",
                    "reuse_proxy_count_mean",
                    "reconstruction_proxy_count_mean",
                    "reuse_intensity_score",
                ]
            ],
            on="workload_family",
            how="left",
        )
        .merge(
            family_dim[
                [
                    "workload_family",
                    "dimension_feature_dim_after_mean",
                    "dimension_pressure_score",
                ]
            ],
            on="workload_family",
            how="left",
        )
    )
    timing_summary = unified_obs[
        ["workload_family", "workload_variant", "timing_p50", "timing_p90", "timing_p99", "timing_p999"]
    ].copy()
    reuse_summary = unified_obs[
        [
            "workload_family",
            "workload_variant",
            "reuse_proxy_count",
            "reconstruction_proxy_count",
            "cache_proxy_reuse_density",
        ]
    ].copy()
    rankings = export_unified_workload_rankings(unified_obs)
    similarity = summarize_cross_family_similarity(unified_obs)

    deferred_list = (
        unified_obs.loc[unified_obs["deferred_to_hpc"] == True, "workload_variant"].dropna().astype(str).tolist()
        if len(unified_obs)
        else []
    )
    manifest = {
        "run_id": rid,
        "generated_at_utc": _now_iso(),
        "execution_environment": env,
        "common_schema_columns": list(COMMON_SCHEMA_COLUMNS),
        "source_families_used": {
            "event": event_comparison_result is not None or cache_study_result is not None,
            "feature_panel": feature_panel_bundle is not None,
            "portfolio_risk": portfolio_risk_bundle is not None,
            "pricing": pricing_bundle is not None,
        },
        "metric_policy": {
            "direct": "values measured directly in source family manifests/summaries",
            "derived": "computed from direct values under explicit formulas",
            "proxy": "cache-related proxies valid on Mac but not PMU proof",
        },
        "deferred_to_hpc_variants": deferred_list,
        "row_count": int(len(unified_obs)),
        "family_count": int(_safe_nunique(unified_obs["workload_family"])) if len(unified_obs) else 0,
    }
    return {
        "run_id": rid,
        "unified_workload_observations": unified_obs,
        "unified_workload_family_summary": family_summary,
        "unified_workload_timing_summary": timing_summary,
        "unified_workload_reuse_proxy_summary": reuse_summary,
        "unified_workload_rankings": rankings["unified_rankings"],
        "unified_workload_similarity_summary": similarity,
        "unified_workload_manifest": manifest,
        "unified_workload_rankings_manifest": {
            "family_rankings": rankings["family_rankings"].to_dict(orient="records"),
            "reuse_rankings": rankings["reuse_rankings"].to_dict(orient="records"),
            "reconstruction_rankings": rankings["reconstruction_rankings"].to_dict(orient="records"),
            "mac_hpc_rankings": rankings["mac_hpc_rankings"].to_dict(orient="records"),
        },
        "unified_workload_similarity_manifest": {
            "pair_count": int(len(similarity)),
            "top_pairs": similarity.head(10).to_dict(orient="records") if len(similarity) else [],
            "notes": "cross-family structural similarity is approximate and schema-constrained",
        },
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


def _plot_bar(
    frame: Any,
    *,
    x: str,
    y: str,
    title: str,
    output_path: Path,
    hue: str = "",
) -> Optional[Path]:
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
            frame.pivot_table(index=x, columns=hue, values=y, aggfunc="mean").plot(
                kind="bar", ax=ax
            )
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
    lines.extend([f"- {b}" for b in bullets])
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def export_unified_observability_bundle(
    *,
    bundle: Mapping[str, Any],
    output_dir: str | Path,
) -> Dict[str, str]:
    """Export unified observability primary CSV/JSON first, then markdown/plots."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    csv_obs = out / "unified_workload_observations.csv"
    csv_family = out / "unified_workload_family_summary.csv"
    csv_timing = out / "unified_workload_timing_summary.csv"
    csv_reuse = out / "unified_workload_reuse_proxy_summary.csv"
    csv_rank = out / "unified_workload_rankings.csv"
    csv_sim = out / "unified_workload_similarity_summary.csv"

    bundle["unified_workload_observations"].to_csv(csv_obs, index=False)
    bundle["unified_workload_family_summary"].to_csv(csv_family, index=False)
    bundle["unified_workload_timing_summary"].to_csv(csv_timing, index=False)
    bundle["unified_workload_reuse_proxy_summary"].to_csv(csv_reuse, index=False)
    bundle["unified_workload_rankings"].to_csv(csv_rank, index=False)
    bundle["unified_workload_similarity_summary"].to_csv(csv_sim, index=False)

    json_manifest = out / "unified_workload_manifest.json"
    json_rank_manifest = out / "unified_workload_rankings_manifest.json"
    json_sim_manifest = out / "unified_workload_similarity_manifest.json"
    json_manifest.write_text(
        json.dumps(bundle["unified_workload_manifest"], indent=2),
        encoding="utf-8",
    )
    json_rank_manifest.write_text(
        json.dumps(bundle["unified_workload_rankings_manifest"], indent=2),
        encoding="utf-8",
    )
    json_sim_manifest.write_text(
        json.dumps(bundle["unified_workload_similarity_manifest"], indent=2),
        encoding="utf-8",
    )

    md_summary = out / "unified_workload_summary.md"
    md_rank = out / "unified_workload_rankings_summary.md"
    md_sim = out / "unified_workload_similarity_summary.md"

    fam = bundle["unified_workload_family_summary"]
    bullets_summary = [
        (
            f"{r.workload_family}: variants={int(r.variant_count)} "
            f"rows_mean={float(r.n_rows_mean):.1f} timing_p90_mean={float(r.timing_p90_mean):.2f}"
        )
        for r in fam.itertuples(index=False)
    ]
    _write_md(md_summary, title="Unified Workload Summary", bullets=bullets_summary)

    ranking = bundle["unified_workload_rankings"]
    bullets_rank = [
        (
            f"{r.ranking_axis}: rank={int(r.rank)} family={r.workload_family} "
            f"variant={r.workload_variant} score={float(r.score):.4f}"
        )
        for r in ranking.head(80).itertuples(index=False)
    ]
    _write_md(md_rank, title="Unified Workload Rankings Summary", bullets=bullets_rank)

    sim = bundle["unified_workload_similarity_summary"]
    bullets_sim = [
        (
            f"{r.workload_family_a} ~ {r.workload_family_b}: "
            f"similarity={float(r.similarity_score):.4f} distance={float(r.distance):.4f}"
        )
        for r in sim.head(40).itertuples(index=False)
    ]
    _write_md(md_sim, title="Unified Workload Similarity Summary", bullets=bullets_sim)

    plot_timing = out / "plot_cross_family_timing_comparison.png"
    plot_dim = out / "plot_cross_family_dimension_comparison.png"
    plot_reuse = out / "plot_cross_family_reuse_proxy_comparison.png"
    plot_rank = out / "plot_unified_workload_rankings.png"
    plot_sim = out / "plot_unified_workload_similarity.png"
    plot_hpc = out / "plot_mac_vs_hpc_escalation_priority.png"

    _plot_bar(
        bundle["unified_workload_family_summary"],
        x="workload_family",
        y="timing_p90_mean",
        title="Cross-Family Timing Comparison",
        output_path=plot_timing,
    )
    _plot_bar(
        bundle["unified_workload_family_summary"],
        x="workload_family",
        y="dimension_feature_dim_after_mean",
        title="Cross-Family Dimension Comparison",
        output_path=plot_dim,
    )
    _plot_bar(
        bundle["unified_workload_family_summary"],
        x="workload_family",
        y="reuse_proxy_count_mean",
        title="Reuse-Proxy Comparison",
        output_path=plot_reuse,
    )
    _plot_bar(
        bundle["unified_workload_rankings"].head(20),
        x="workload_family",
        y="score",
        hue="ranking_axis",
        title="Unified Ranking Comparison",
        output_path=plot_rank,
    )
    _plot_bar(
        bundle["unified_workload_similarity_summary"].head(20),
        x="workload_family_a",
        y="similarity_score",
        hue="workload_family_b",
        title="Cross-Family Similarity",
        output_path=plot_sim,
    )
    _plot_bar(
        bundle["unified_workload_rankings"]
        .loc[bundle["unified_workload_rankings"]["ranking_axis"] == "variant_mac_vs_hpc_priority"]
        .head(20),
        x="workload_variant",
        y="score",
        hue="priority_label",
        title="Mac-vs-HPC Escalation Priority",
        output_path=plot_hpc,
    )

    return {
        "unified_workload_observations_csv": str(csv_obs),
        "unified_workload_family_summary_csv": str(csv_family),
        "unified_workload_timing_summary_csv": str(csv_timing),
        "unified_workload_reuse_proxy_summary_csv": str(csv_reuse),
        "unified_workload_rankings_csv": str(csv_rank),
        "unified_workload_similarity_summary_csv": str(csv_sim),
        "unified_workload_manifest_json": str(json_manifest),
        "unified_workload_rankings_manifest_json": str(json_rank_manifest),
        "unified_workload_similarity_manifest_json": str(json_sim_manifest),
        "unified_workload_summary_md": str(md_summary),
        "unified_workload_rankings_summary_md": str(md_rank),
        "unified_workload_similarity_summary_md": str(md_sim),
        "plot_cross_family_timing_comparison": str(plot_timing),
        "plot_cross_family_dimension_comparison": str(plot_dim),
        "plot_cross_family_reuse_proxy_comparison": str(plot_reuse),
        "plot_unified_workload_rankings": str(plot_rank),
        "plot_unified_workload_similarity": str(plot_sim),
        "plot_mac_vs_hpc_escalation_priority": str(plot_hpc),
    }

