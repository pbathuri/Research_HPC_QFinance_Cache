"""CRSP-backed daily feature panels (Phase 2 — after event alignment).

Expects a long daily panel with at least ``permno`` (or ``symbol``), ``date``, ``close``.
Uses ``alpha_features`` / ``historical_returns`` where possible; adds regime and event-tag columns.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING

from qhpc_cache.data_models import DatasetRegistryEntry, FeaturePanelManifest
from qhpc_cache.data_registry import register_dataset

if TYPE_CHECKING:
    import pandas as pd


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def deterministic_panel_label(*, panel_key: str, permnos: Sequence[str], date_start: str, date_end: str) -> str:
    payload = {"panel_key": panel_key, "permnos": sorted(str(p) for p in permnos), "d0": date_start, "d1": date_end}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:18]


def build_daily_feature_panel(
    ohlcv_long: "pd.DataFrame",
    *,
    permno_column: str = "permno",
    date_column: str = "date",
    close_column: str = "close",
    volume_column: Optional[str] = "volume",
    mom_lookback: int = 21,
    vol_window: int = 21,
    dd_window: int = 63,
    fast_ma: int = 10,
    slow_ma: int = 50,
    z_window: int = 60,
    downside_window: int = 21,
) -> Tuple["pd.DataFrame", List[str]]:
    """Build interpretable features on a CRSP-like daily long panel (e.g. ``crsp.dsf``-shaped)."""
    import numpy as np
    import pandas as pd

    from qhpc_cache.alpha_features import (
        moving_average_spread_feature,
        price_momentum_feature,
        rolling_z_score_feature,
    )

    df = ohlcv_long.copy()
    df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
    df = df.dropna(subset=[date_column, close_column, permno_column])
    df = df.sort_values([permno_column, date_column])

    df["daily_ret"] = df.groupby(permno_column, group_keys=False)[close_column].pct_change()

    df = price_momentum_feature(
        df.rename(columns={permno_column: "symbol"}),
        lookback=mom_lookback,
        close_column=close_column,
        symbol_column="symbol",
        date_column=date_column,
    ).rename(columns={"symbol": permno_column})

    df = moving_average_spread_feature(
        df.rename(columns={permno_column: "symbol"}),
        fast_window=fast_ma,
        slow_window=slow_ma,
        close_column=close_column,
        symbol_column="symbol",
        date_column=date_column,
    ).rename(columns={"symbol": permno_column})

    df = rolling_z_score_feature(
        df.rename(columns={permno_column: "symbol"}),
        value_column="daily_ret",
        window=z_window,
        symbol_column="symbol",
        date_column=date_column,
        output_column="ret_z_score",
    ).rename(columns={"symbol": permno_column})

    # Rolling realized vol (annualized) from daily returns
    df["rolling_vol"] = (
        df.groupby(permno_column, group_keys=False)["daily_ret"]
        .transform(lambda s: s.rolling(vol_window, min_periods=max(5, vol_window // 3)).std() * (252.0**0.5))
    )

    neg = df["daily_ret"].where(df["daily_ret"] < 0.0)
    df["downside_vol"] = (
        neg.groupby(df[permno_column]).transform(
            lambda s: s.rolling(downside_window, min_periods=max(5, downside_window // 4)).std() * (252.0**0.5)
        )
    )

    # Drawdown vs rolling window high (per permno)
    roll_hi = df.groupby(permno_column, group_keys=False)[close_column].transform(
        lambda s: s.rolling(dd_window, min_periods=max(5, dd_window // 4)).max()
    )
    df["rolling_max_dd"] = df[close_column].astype(float) / roll_hi - 1.0

    # Stress regime: high vol vs trailing median
    med_vol = df.groupby(permno_column, group_keys=False)["rolling_vol"].transform(
        lambda s: s.rolling(252, min_periods=20).median()
    )
    df["stress_high_vol"] = (df["rolling_vol"] > med_vol * 1.5).astype(int)

    feat_cols = [
        "momentum",
        "ma_spread",
        "ret_z_score",
        "rolling_vol",
        "downside_vol",
        "rolling_max_dd",
        "stress_high_vol",
    ]
    if volume_column and volume_column in df.columns:
        df["vol_z"] = df.groupby(permno_column, group_keys=False)[volume_column].transform(
            lambda s: (s - s.rolling(60, min_periods=10).mean()) / s.rolling(60, min_periods=10).std().replace(0, np.nan)
        )
        feat_cols.append("vol_z")

    return df, feat_cols


def attach_event_tags_to_feature_panel(
    panel: "pd.DataFrame",
    event_tags: "pd.DataFrame",
    *,
    permno_column: str = "permno",
    date_column: str = "date",
    tag_columns: Optional[Sequence[str]] = None,
) -> "pd.DataFrame":
    """Left-merge pre-built event tag columns (from Phase 1) on ``permno`` + calendar ``date``."""
    import pandas as pd

    p = panel.copy()
    p["_d"] = pd.to_datetime(p[date_column], errors="coerce", utc=True).dt.tz_localize(None).dt.normalize()
    t = event_tags.copy()
    if date_column not in t.columns:
        raise ValueError("event_tags must include date_column")
    t["_d"] = pd.to_datetime(t[date_column], errors="coerce", utc=True).dt.tz_localize(None).dt.normalize()
    if tag_columns is None:
        tag_columns = [c for c in t.columns if c not in (permno_column, date_column, "_d")]
    cols = [permno_column, "_d"] + [c for c in tag_columns if c in t.columns]
    sub = t[cols].drop_duplicates()
    out = p.merge(sub, on=[permno_column, "_d"], how="left")
    out = out.drop(columns=["_d"], errors="ignore")
    return out


def attach_rates_context_to_feature_panel(
    panel: "pd.DataFrame",
    rates_frame: "pd.DataFrame",
    *,
    date_column: str = "date",
) -> "pd.DataFrame":
    """Attach risk-free column(s) via left merge on date (see ``rates_data.align_rates_to_daily_universe``)."""
    from qhpc_cache.rates_data import align_rates_to_daily_universe

    return align_rates_to_daily_universe(rates_frame, panel, date_column_daily=date_column)


def compute_condensed_feature_panel(
    panel: "pd.DataFrame",
    feature_columns: Sequence[str],
    *,
    n_components: int = 8,
    prefix: str = "pca_",
) -> Tuple["pd.DataFrame", int]:
    """Optional PCA condensation; falls back to passthrough if sklearn missing."""
    out, k, _ = compute_condensed_feature_panel_with_meta(
        panel,
        feature_columns,
        n_components=n_components,
        prefix=prefix,
    )
    return out, k


def compute_condensed_feature_panel_with_meta(
    panel: "pd.DataFrame",
    feature_columns: Sequence[str],
    *,
    n_components: int = 8,
    prefix: str = "pca_",
) -> Tuple["pd.DataFrame", int, Dict[str, Any]]:
    """Optional PCA condensation with metadata for comparison layers."""
    import numpy as np

    cols = [c for c in feature_columns if c in panel.columns]
    if not cols:
        return panel, 0, {
            "condensation_method": "none_no_features",
            "explained_variance_ratio_sum": 0.0,
            "sklearn_used": False,
            "condensation_skipped": True,
            "skip_reason": "no_feature_columns",
            "n_input_features": 0,
            "n_output_features": 0,
        }
    X = panel[cols].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0).values
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    X = np.clip(X, -1e6, 1e6)
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd = np.where(sd < 1e-12, 1.0, sd)
    X = (X - mu) / sd
    try:
        from sklearn.decomposition import PCA

        k = min(n_components, X.shape[1], max(1, X.shape[0] // 2))
        pca = PCA(n_components=k, random_state=42)
        Z = pca.fit_transform(X)
        out = panel.copy()
        for i in range(Z.shape[1]):
            out[f"{prefix}{i}"] = Z[:, i]
        return out, Z.shape[1], {
            "condensation_method": "pca",
            "explained_variance_ratio_sum": float(np.sum(pca.explained_variance_ratio_)),
            "sklearn_used": True,
            "condensation_skipped": False,
            "skip_reason": "",
            "n_input_features": int(X.shape[1]),
            "n_output_features": int(Z.shape[1]),
        }
    except Exception as exc:
        return panel, len(cols), {
            "condensation_method": "none_passthrough",
            "explained_variance_ratio_sum": 0.0,
            "sklearn_used": False,
            "condensation_skipped": True,
            "skip_reason": f"pca_unavailable_or_failed:{type(exc).__name__}",
            "n_input_features": int(X.shape[1]),
            "n_output_features": int(len(cols)),
        }


def build_feature_panel_with_observability(
    ohlcv_long: "pd.DataFrame",
    *,
    panel_key: str,
    rates_frame: Optional["pd.DataFrame"] = None,
    event_tags: Optional["pd.DataFrame"] = None,
    manifest_alignment_path: str = "",
    run_id: str = "",
    record_observability: bool = True,
    **build_kw: Any,
) -> Tuple["pd.DataFrame", Dict[str, Any]]:
    """Convenience: build panel, optional rates/tags/condense, manifest dict, observability row."""
    import pandas as pd

    from qhpc_cache.cache_workload_mapping import record_spine_pipeline_observation
    from qhpc_cache.workload_signatures import WORKLOAD_SPINE_FEATURE_PANEL

    permno_column = build_kw.get("permno_column", "permno")
    date_column = build_kw.get("date_column", "date")

    panel, feat_cols = build_daily_feature_panel(ohlcv_long, **build_kw)
    n_before = len(feat_cols)
    if event_tags is not None and len(event_tags):
        n_tag = len([c for c in event_tags.columns if c not in (permno_column, date_column)])
        panel = attach_event_tags_to_feature_panel(panel, event_tags, permno_column=permno_column, date_column=date_column)
        n_before += max(0, n_tag)
    rates_ok = False
    if rates_frame is not None and len(rates_frame):
        panel = attach_rates_context_to_feature_panel(panel, rates_frame, date_column=date_column)
        rates_ok = True
    panel2, k = compute_condensed_feature_panel(panel, feat_cols, n_components=8)
    permnos = panel2[permno_column].dropna().unique().tolist()[:5000]
    d0 = str(panel2[date_column].min())[:10]
    d1 = str(panel2[date_column].max())[:10]
    det = deterministic_panel_label(panel_key=panel_key, permnos=permnos, date_start=d0, date_end=d1)
    n_after = int(k) if k else n_before
    manifest: Dict[str, Any] = {
        "panel_key": panel_key,
        "deterministic_label": det,
        "n_securities": int(panel2[permno_column].nunique()),
        "n_dates": int(pd.to_datetime(panel2[date_column]).dt.normalize().nunique()),
        "n_rows": len(panel2),
        "date_range_start": d0,
        "date_range_end": d1,
        "feature_count_before": n_before,
        "feature_count_after": n_after,
        "feature_columns": feat_cols,
        "rates_attached": rates_ok,
        "event_tags_attached": event_tags is not None and len(event_tags) > 0,
        "alignment_manifest_ref": manifest_alignment_path,
        "created_at_utc": _utc(),
    }
    if record_observability:
        record_spine_pipeline_observation(
            run_id=run_id or f"fp_{det}",
            workload_spine_id=WORKLOAD_SPINE_FEATURE_PANEL,
            pipeline_phase="feature_panel",
            source_datasets="crsp.dsf;crsp.stocknames;rates;aligned_event_tags",
            row_count_primary=len(ohlcv_long),
            row_count_after_join=len(panel2),
            join_width_estimate=len(panel2.columns),
            feature_dim_before=n_before,
            feature_dim_after=n_after,
            notes=json.dumps({"panel_key": panel_key, "det": det})[:500],
        )
    return panel2, manifest


def manifest_from_build_dict(
    build: Dict[str, Any],
    *,
    panel_key: str,
    storage_path: str,
) -> FeaturePanelManifest:
    """Build ``FeaturePanelManifest`` from ``build_feature_panel_with_observability`` output."""
    return FeaturePanelManifest(
        panel_key=panel_key,
        deterministic_label=str(build.get("deterministic_label", "")),
        n_securities=int(build.get("n_securities", 0)),
        n_dates=int(build.get("n_dates", 0)),
        n_rows=int(build.get("n_rows", 0)),
        date_range_start=str(build.get("date_range_start", "")),
        date_range_end=str(build.get("date_range_end", "")),
        feature_count_before_condense=int(build.get("feature_count_before", 0)),
        feature_count_after_condense=int(build.get("feature_count_after", 0)),
        rates_attached=bool(build.get("rates_attached", False)),
        event_tags_attached=bool(build.get("event_tags_attached", False)),
        alignment_manifest_ref=str(build.get("alignment_manifest_ref", "")),
        storage_path=storage_path,
        created_at_utc=str(build.get("created_at_utc", "")),
        feature_columns=list(build.get("feature_columns", [])),
        extra={k: v for k, v in build.items() if k not in ("feature_columns",)},
    )


def register_feature_panel(
    *,
    data_root: str,
    manifest: FeaturePanelManifest,
    primary_path: str | Path,
    batch_identifier: str = "feature_panel",
) -> None:
    """Register a feature panel artifact.

    Kept in the owning feature-panel module so the canonical panel path carries
    its storage and registry contract together.
    """
    path = Path(primary_path)
    disk = path.stat().st_size if path.exists() else 0
    t0 = time.perf_counter()
    entry = DatasetRegistryEntry(
        registry_key=f"feature_panel::{manifest.panel_key}::{manifest.deterministic_label}",
        provider="qhpc_feature_panel",
        dataset_kind="feature_panel_crsp",
        date_range_start=(manifest.date_range_start or "unknown")[:10],
        date_range_end=(manifest.date_range_end or "unknown")[:10],
        symbol_coverage=f"n_permno~{manifest.n_securities}",
        schema_label="qhpc.feature_panel.v1",
        row_count=manifest.n_rows,
        local_paths=[str(path)],
        completion_status="complete" if manifest.n_rows > 0 else "empty",
        estimated_disk_usage_bytes=disk,
        realized_disk_usage_bytes=disk,
        ingestion_runtime_seconds=time.perf_counter() - t0,
        checkpoint_label="analytics_ready",
        batch_identifier=batch_identifier,
        parent_dataset_label=manifest.alignment_manifest_ref or "crsp_dsf",
        source_backend="pandas_pipeline",
        notes=json.dumps(manifest.to_dict(), default=str)[:1800],
        wrds_source_table="crsp.dsf+msf",
        wrds_dataset_role="canonical",
    )
    register_dataset(data_root, entry)
