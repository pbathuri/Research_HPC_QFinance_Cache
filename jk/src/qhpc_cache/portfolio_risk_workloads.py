"""Canonical portfolio-risk workload family (historical + slice scenarios).

This layer builds two locked workload layers:
  A) historical risk on broad universes
  B) deterministic portfolio-slice scenario recomputation
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from qhpc_cache.historical_returns import align_return_panel, compute_simple_returns
from qhpc_cache.historical_risk import compute_historical_cvar, compute_historical_var
from qhpc_cache.workload_signatures import (
    model_family_label,
    portfolio_family_label,
    workload_family_label,
)


RISK_WORKLOAD_LARGE_UNIVERSE = "large_universe_historical_risk"
RISK_WORKLOAD_SLICE_SCENARIO = "portfolio_slice_scenario_risk"

LOCKED_SCENARIO_FAMILIES: Tuple[str, ...] = (
    "baseline_historical",
    "event_conditioned",
    "volatility_stress",
    "rates_shift_aware",
    "broad_market_drawdown",
)


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


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _workload_family_label(*, stage: str, n_symbols: int, model_phase: str) -> str:
    pf = portfolio_family_label(universe_name=stage, n_symbols=n_symbols, book_tag=model_phase)
    mf = model_family_label(engine_or_model="historical_risk", path_bucket=stage, phase=model_phase)
    return workload_family_label(
        pipeline_stage=stage,
        portfolio_family=pf,
        model_family=mf,
        event_stress=True,
    )


def _mac_degrade_daily_panel(
    daily_panel: Any,
    *,
    permno_column: str,
    date_column: str,
    mac_row_limit: int,
) -> Tuple[Any, List[str]]:
    import pandas as pd

    if daily_panel is None or len(daily_panel) == 0:
        return daily_panel, []
    if platform.system().lower() != "darwin":
        return daily_panel, []
    if len(daily_panel) <= mac_row_limit:
        return daily_panel, []

    df = daily_panel.copy()
    df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
    n_perm = max(1, _safe_nunique(df[permno_column])) if permno_column in df.columns else 1
    per_perm_cap = max(80, mac_row_limit // n_perm)
    kept = []
    deferred = 0
    if permno_column in df.columns:
        for _, grp in df.sort_values(date_column).groupby(permno_column, dropna=False):
            if len(grp) > per_perm_cap:
                deferred += len(grp) - per_perm_cap
                kept.append(grp.tail(per_perm_cap))
            else:
                kept.append(grp)
        out = pd.concat(kept, ignore_index=True) if kept else df.head(0).copy()
    else:
        out = df.tail(mac_row_limit).copy()
        deferred = len(df) - len(out)
    notes = [f"mac_scope_degraded_portfolio_risk rows={len(df)} limit={mac_row_limit} per_perm_cap={per_perm_cap}"]
    if deferred > 0:
        notes.append(f"hpc_deferred::portfolio_risk_rows={deferred}")
    return out, notes


def build_historical_risk_panel(
    daily_panel: Any,
    *,
    rates_frame: Optional[Any] = None,
    event_tags: Optional[Any] = None,
    permno_column: str = "permno",
    date_column: str = "date",
    close_column: str = "close",
    start_date: str = "",
    end_date: str = "",
    panel_key: str = "portfolio_risk_panel",
) -> Dict[str, Any]:
    """Build deterministic return panel and optional contextual joins."""
    import pandas as pd

    df = daily_panel.copy()
    df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
    if start_date:
        df = df.loc[df[date_column] >= pd.to_datetime(start_date)]
    if end_date:
        df = df.loc[df[date_column] <= pd.to_datetime(end_date)]
    df = df.dropna(subset=[permno_column, date_column, close_column]).copy()

    if rates_frame is not None and len(rates_frame) > 0:
        from qhpc_cache.rates_data import align_rates_to_daily_universe

        df = align_rates_to_daily_universe(rates_frame, df, date_column_daily=date_column)

    if event_tags is not None and len(event_tags) > 0:
        from qhpc_cache.feature_panel import attach_event_tags_to_feature_panel

        df = attach_event_tags_to_feature_panel(df, event_tags, permno_column=permno_column, date_column=date_column)

    sym_col = "symbol"
    if sym_col not in df.columns:
        df[sym_col] = df[permno_column].astype(str)
    ret_long = compute_simple_returns(
        df,
        close_column=close_column,
        symbol_column=sym_col,
        date_column=date_column,
    )
    wide_returns = align_return_panel(
        ret_long,
        date_column=date_column,
        symbol_column=sym_col,
        value_column="simple_return",
    )
    d0 = str(wide_returns.index.min())[:10] if len(wide_returns) else ""
    d1 = str(wide_returns.index.max())[:10] if len(wide_returns) else ""
    symbols = [str(c) for c in wide_returns.columns]
    det = hashlib.sha256(
        json.dumps({"panel_key": panel_key, "symbols": sorted(symbols), "d0": d0, "d1": d1}, sort_keys=True).encode()
    ).hexdigest()[:18]
    return {
        "daily_panel": df,
        "returns_long": ret_long,
        "returns_wide": wide_returns,
        "panel_key": panel_key,
        "deterministic_label": det,
        "date_range_start": d0,
        "date_range_end": d1,
        "n_rows": int(len(df)),
        "n_dates": int(len(wide_returns.index)),
        "n_securities": int(len(wide_returns.columns)),
        "rates_attached": bool("risk_free_rate" in df.columns),
        "event_tags_attached": bool(any(str(c).startswith(("event_", "qhpc_")) for c in df.columns)),
    }


def _portfolio_return_series(wide_returns: Any, symbols: Sequence[str], weights: Sequence[float]) -> Any:
    import pandas as pd

    cols = [str(s) for s in symbols if str(s) in wide_returns.columns]
    if not cols:
        return pd.Series(dtype=float)
    w = pd.Series(list(weights)[: len(cols)], index=cols, dtype=float)
    w = w / max(1e-12, float(w.sum()))
    sub = wide_returns[cols].astype(float).fillna(0.0)
    return sub.mul(w, axis=1).sum(axis=1)


def compute_large_universe_historical_var(
    returns_wide: Any,
    *,
    confidence_level: float = 0.95,
) -> float:
    """Historical VaR on broad-universe equal-weight aggregated returns."""
    if returns_wide is None or len(returns_wide) == 0:
        return 0.0
    port = returns_wide.astype(float).fillna(0.0).mean(axis=1)
    return compute_historical_var(port.tolist(), confidence_level=confidence_level)


def compute_large_universe_historical_cvar(
    returns_wide: Any,
    *,
    confidence_level: float = 0.95,
) -> float:
    """Historical CVaR on broad-universe equal-weight aggregated returns."""
    if returns_wide is None or len(returns_wide) == 0:
        return 0.0
    port = returns_wide.astype(float).fillna(0.0).mean(axis=1)
    return compute_historical_cvar(port.tolist(), confidence_level=confidence_level)


def summarize_large_universe_risk(
    returns_wide: Any,
    *,
    confidence_level: float = 0.95,
    workload_label: str = RISK_WORKLOAD_LARGE_UNIVERSE,
) -> Tuple[Any, Any]:
    """Summarize broad-universe historical risk and VaR/CVaR structure."""
    import pandas as pd
    from qhpc_cache.historical_returns import compute_rolling_volatility

    if returns_wide is None or len(returns_wide) == 0:
        empty_a = pd.DataFrame(
            [
                {
                    "risk_workload_variant_label": workload_label,
                    "n_securities": 0,
                    "n_dates": 0,
                    "n_rows": 0,
                    "rolling_vol_p90": 0.0,
                    "drawdown_loss": 0.0,
                    "workload_family_label": _workload_family_label(
                        stage="portfolio_risk",
                        n_symbols=0,
                        model_phase="large_universe",
                    ),
                }
            ]
        )
        empty_b = pd.DataFrame(
            [
                {
                    "risk_workload_variant_label": workload_label,
                    "var_loss_on_return": 0.0,
                    "cvar_loss_on_return": 0.0,
                    "cvar_over_var_ratio": 0.0,
                    "confidence_level": confidence_level,
                }
            ]
        )
        return empty_a, empty_b

    port = returns_wide.astype(float).fillna(0.0).mean(axis=1)
    var_loss = compute_historical_var(port.tolist(), confidence_level=confidence_level)
    cvar_loss = compute_historical_cvar(port.tolist(), confidence_level=confidence_level)

    # Volatility and drawdown-aware summary on cumulative portfolio path.
    vol = compute_rolling_volatility(port.to_frame("portfolio_ret"), window=21)["portfolio_ret"]
    pseudo_price = (1.0 + port.fillna(0.0)).cumprod()
    from qhpc_cache.historical_risk import compute_event_window_drawdown

    drawdown_loss = compute_event_window_drawdown(pseudo_price.tolist())
    hist_summary = pd.DataFrame(
        [
            {
                "risk_workload_variant_label": workload_label,
                "n_securities": int(len(returns_wide.columns)),
                "n_dates": int(len(returns_wide.index)),
                "n_rows": int(len(returns_wide) * len(returns_wide.columns)),
                "rolling_vol_p90": _quantile(vol.dropna(), 0.90),
                "drawdown_loss": float(drawdown_loss),
                "workload_family_label": _workload_family_label(
                    stage="portfolio_risk",
                    n_symbols=int(len(returns_wide.columns)),
                    model_phase="large_universe",
                ),
            }
        ]
    )
    var_cvar = pd.DataFrame(
        [
            {
                "risk_workload_variant_label": workload_label,
                "var_loss_on_return": var_loss,
                "cvar_loss_on_return": cvar_loss,
                "cvar_over_var_ratio": cvar_loss / max(1e-12, var_loss) if var_loss > 0 else 0.0,
                "confidence_level": confidence_level,
            }
        ]
    )
    return hist_summary, var_cvar


def build_portfolio_slice(
    available_symbols: Sequence[str],
    *,
    slice_id: str,
    start_index: int,
    slice_size: int,
) -> Dict[str, Any]:
    """Deterministic contiguous slice from sorted symbols with equal weights."""
    symbols = sorted(str(s) for s in set(available_symbols))
    if not symbols:
        return {"slice_id": slice_id, "symbols": [], "weights": [], "slice_marker": ""}
    n = len(symbols)
    idx = [symbols[(start_index + i) % n] for i in range(min(slice_size, n))]
    w = [1.0 / max(1, len(idx))] * len(idx)
    marker = hashlib.sha256(",".join(idx).encode()).hexdigest()[:14]
    return {
        "slice_id": slice_id,
        "symbols": idx,
        "weights": w,
        "weighting_label": "equal_weight",
        "aggregation_label": "weighted_sum_returns",
        "slice_marker": marker,
        "slice_size": len(idx),
    }


def build_portfolio_slice_family(
    returns_wide: Any,
    *,
    family_id: str = "deterministic_slice_family",
    n_slices: int = 8,
    slice_size: int = 40,
) -> Any:
    """Build deterministic family of repeated portfolio slices."""
    import pandas as pd

    symbols = [str(c) for c in returns_wide.columns] if returns_wide is not None else []
    out: List[Dict[str, Any]] = []
    for i in range(n_slices):
        s = build_portfolio_slice(
            symbols,
            slice_id=f"{family_id}::slice_{i:02d}",
            start_index=i * max(1, slice_size // 2),
            slice_size=slice_size,
        )
        for sym, w in zip(s["symbols"], s["weights"]):
            out.append(
                {
                    "family_id": family_id,
                    "slice_id": s["slice_id"],
                    "symbol": sym,
                    "weight": w,
                    "slice_marker": s["slice_marker"],
                    "weighting_label": s["weighting_label"],
                    "aggregation_label": s["aggregation_label"],
                    "slice_size": s["slice_size"],
                }
            )
    return pd.DataFrame(out)


def _event_conditioned_dates(event_tags: Any, *, date_column: str = "date") -> Any:
    import pandas as pd

    if event_tags is None or len(event_tags) == 0 or date_column not in event_tags.columns:
        return pd.DatetimeIndex([])
    tag_cols = [c for c in event_tags.columns if c not in ("permno", date_column)]
    if not tag_cols:
        return pd.DatetimeIndex([])
    t = event_tags.copy()
    t[date_column] = pd.to_datetime(t[date_column], errors="coerce").dt.normalize()
    active = (t[tag_cols].fillna(0).astype(float).sum(axis=1) > 0).astype(int)
    return pd.DatetimeIndex(sorted(t.loc[active == 1, date_column].dropna().unique()))


def _scenario_series(
    base_returns: Any,
    *,
    scenario_family: str,
    market_returns: Any,
    event_dates: Any,
    rates_frame: Optional[Any],
) -> Any:
    import pandas as pd

    s = base_returns.copy().astype(float).dropna()
    if len(s) == 0:
        return s
    if scenario_family == "baseline_historical":
        return s
    if scenario_family == "event_conditioned":
        if event_dates is not None and len(event_dates) > 0:
            out = s.loc[s.index.normalize().isin(event_dates)]
            return out if len(out) >= 10 else s.tail(max(10, len(s) // 3))
        return s.loc[s.abs() >= s.abs().quantile(0.80)]
    if scenario_family == "volatility_stress":
        vol = market_returns.rolling(21, min_periods=5).std().reindex(s.index).bfill().fillna(0.0)
        hi = vol >= vol.quantile(0.75)
        out = s.loc[hi]
        out = out if len(out) >= 10 else s.tail(max(10, len(s) // 3))
        return out * 1.25
    if scenario_family == "rates_shift_aware":
        if rates_frame is None or len(rates_frame) == 0:
            return s
        rf = rates_frame.copy()
        dcol = "date" if "date" in rf.columns else rf.columns[0]
        rcol = "risk_free_rate" if "risk_free_rate" in rf.columns else rf.columns[1]
        rf[dcol] = pd.to_datetime(rf[dcol], errors="coerce").dt.normalize()
        rr = pd.to_numeric(rf[rcol], errors="coerce").fillna(0.0)
        rs = pd.Series(rr.values, index=rf[dcol]).groupby(level=0).mean().reindex(s.index.normalize()).ffill().fillna(0.0)
        adj = 0.5 * (rs - float(rs.mean()))
        return s - adj.values
    if scenario_family == "broad_market_drawdown":
        thresh = market_returns.quantile(0.15)
        out = s.loc[market_returns.reindex(s.index).fillna(0.0) <= thresh]
        return out if len(out) >= 10 else s.nsmallest(max(10, len(s) // 4))
    return s


def compute_portfolio_slice_var(
    slice_returns: Sequence[float],
    *,
    confidence_level: float = 0.95,
) -> float:
    return compute_historical_var(slice_returns, confidence_level=confidence_level)


def compute_portfolio_slice_cvar(
    slice_returns: Sequence[float],
    *,
    confidence_level: float = 0.95,
) -> float:
    return compute_historical_cvar(slice_returns, confidence_level=confidence_level)


def run_portfolio_scenario_recomputation(
    *,
    returns_wide: Any,
    slice_family: Any,
    scenario_families: Sequence[str] = LOCKED_SCENARIO_FAMILIES,
    confidence_level: float = 0.95,
    event_tags: Optional[Any] = None,
    rates_frame: Optional[Any] = None,
) -> Tuple[Any, Any]:
    """Recompute slice risk across deterministic scenario families."""
    import pandas as pd

    if returns_wide is None or len(returns_wide) == 0 or slice_family is None or len(slice_family) == 0:
        return pd.DataFrame(), pd.DataFrame()
    market_returns = returns_wide.astype(float).fillna(0.0).mean(axis=1)
    event_dates = _event_conditioned_dates(event_tags) if event_tags is not None else pd.DatetimeIndex([])

    scenario_rows: List[Dict[str, Any]] = []
    timing_rows: List[Dict[str, Any]] = []
    for sid, g in slice_family.groupby("slice_id", dropna=False):
        symbols = g["symbol"].astype(str).tolist()
        weights = g["weight"].astype(float).tolist()
        slice_base = _portfolio_return_series(returns_wide, symbols, weights).dropna()
        for scenario_family in scenario_families:
            t0 = time.perf_counter()
            sret = _scenario_series(
                slice_base,
                scenario_family=scenario_family,
                market_returns=market_returns,
                event_dates=event_dates,
                rates_frame=rates_frame,
            )
            vals = sret.dropna().astype(float).tolist()
            if len(vals) < 8:
                continue
            var_loss = compute_portfolio_slice_var(vals, confidence_level=confidence_level)
            cvar_loss = compute_portfolio_slice_cvar(vals, confidence_level=confidence_level)
            scenario_rows.append(
                {
                    "slice_id": sid,
                    "scenario_family": scenario_family,
                    "n_samples": int(len(vals)),
                    "slice_size": int(g["slice_size"].iloc[0]),
                    "aggregation_width": int(len(symbols)),
                    "var_loss_on_return": var_loss,
                    "cvar_loss_on_return": cvar_loss,
                    "cvar_over_var_ratio": cvar_loss / max(1e-12, var_loss) if var_loss > 0 else 0.0,
                    "slice_marker": str(g["slice_marker"].iloc[0]),
                    "weighting_label": str(g["weighting_label"].iloc[0]),
                    "aggregation_label": str(g["aggregation_label"].iloc[0]),
                    "risk_workload_variant_label": RISK_WORKLOAD_SLICE_SCENARIO,
                    "workload_family_label": _workload_family_label(
                        stage="portfolio_risk",
                        n_symbols=int(len(symbols)),
                        model_phase=f"slice::{scenario_family}",
                    ),
                }
            )
            timing_rows.append(
                {
                    "slice_id": sid,
                    "scenario_family": scenario_family,
                    "timing_ms": (time.perf_counter() - t0) * 1000.0,
                    "n_samples": int(len(vals)),
                }
            )
    return pd.DataFrame(scenario_rows), pd.DataFrame(timing_rows)


def summarize_portfolio_slice_risk(
    *,
    slice_family: Any,
    scenario_summary: Any,
) -> Any:
    """Aggregate risk summaries per slice."""
    import pandas as pd

    if slice_family is None or len(slice_family) == 0:
        return pd.DataFrame()
    base = slice_family.groupby("slice_id", dropna=False).agg(
        n_securities=("symbol", "nunique"),
        slice_size=("slice_size", "max"),
        slice_marker=("slice_marker", "first"),
        weighting_label=("weighting_label", "first"),
        aggregation_label=("aggregation_label", "first"),
    )
    base = base.reset_index()
    if scenario_summary is None or len(scenario_summary) == 0:
        base["scenario_count"] = 0
        base["var_mean"] = 0.0
        base["cvar_mean"] = 0.0
        base["risk_workload_variant_label"] = RISK_WORKLOAD_SLICE_SCENARIO
        return base
    agg = scenario_summary.groupby("slice_id", dropna=False).agg(
        scenario_count=("scenario_family", "nunique"),
        recomputation_count=("scenario_family", "size"),
        var_mean=("var_loss_on_return", "mean"),
        cvar_mean=("cvar_loss_on_return", "mean"),
        cvar_over_var_ratio_mean=("cvar_over_var_ratio", "mean"),
    )
    out = base.merge(agg.reset_index(), on="slice_id", how="left").fillna(0)
    out["risk_workload_variant_label"] = RISK_WORKLOAD_SLICE_SCENARIO
    return out


def compare_large_universe_vs_portfolio_slice_risk(
    *,
    historical_risk_summary: Any,
    portfolio_slice_summary: Any,
) -> Any:
    """Compare broad-universe risk structures vs portfolio-slice structures."""
    import pandas as pd

    if historical_risk_summary is None or len(historical_risk_summary) == 0:
        return pd.DataFrame()
    h = historical_risk_summary.copy()
    if portfolio_slice_summary is None or len(portfolio_slice_summary) == 0:
        h["slice_count"] = 0
        h["slice_var_mean"] = 0.0
        h["slice_cvar_mean"] = 0.0
        return h
    return pd.DataFrame(
        [
            {
                "large_universe_n_securities": int(h["n_securities"].iloc[0]),
                "large_universe_n_dates": int(h["n_dates"].iloc[0]),
                "large_universe_rolling_vol_p90": float(h["rolling_vol_p90"].iloc[0]),
                "slice_count": int(portfolio_slice_summary["slice_id"].nunique()),
                "slice_security_mean": float(portfolio_slice_summary["n_securities"].mean()),
                "slice_var_mean": float(portfolio_slice_summary["var_mean"].mean()),
                "slice_cvar_mean": float(portfolio_slice_summary["cvar_mean"].mean()),
            }
        ]
    )


def compare_var_vs_cvar_structures(
    *,
    historical_var_cvar_summary: Any,
    portfolio_scenario_summary: Any,
) -> Any:
    """Compare VaR/CVaR relationships across broad and slice scenarios."""
    import pandas as pd

    hist_ratio = (
        float(historical_var_cvar_summary["cvar_over_var_ratio"].iloc[0])
        if historical_var_cvar_summary is not None and len(historical_var_cvar_summary)
        else 0.0
    )
    slice_ratio = (
        float(portfolio_scenario_summary["cvar_over_var_ratio"].mean())
        if portfolio_scenario_summary is not None and len(portfolio_scenario_summary)
        else 0.0
    )
    return pd.DataFrame(
        [
            {"risk_scope": "large_universe", "cvar_over_var_ratio": hist_ratio},
            {"risk_scope": "portfolio_slice_scenarios", "cvar_over_var_ratio": slice_ratio},
        ]
    )


def compare_scenario_families(portfolio_scenario_summary: Any) -> Any:
    """Compare scenario family risk structures."""
    if portfolio_scenario_summary is None or len(portfolio_scenario_summary) == 0:
        return portfolio_scenario_summary.head(0) if portfolio_scenario_summary is not None else None
    grp = portfolio_scenario_summary.groupby("scenario_family", dropna=False).agg(
        slice_count=("slice_id", "nunique"),
        recomputation_count=("slice_id", "size"),
        var_mean=("var_loss_on_return", "mean"),
        cvar_mean=("cvar_loss_on_return", "mean"),
        cvar_over_var_ratio_mean=("cvar_over_var_ratio", "mean"),
        aggregation_width_mean=("aggregation_width", "mean"),
    )
    return grp.reset_index()


def summarize_risk_recomputation_patterns(
    portfolio_scenario_summary: Any,
    *,
    timing_summary: Any,
) -> Any:
    """Summarize repeated recomputation structures."""
    import pandas as pd

    if portfolio_scenario_summary is None or len(portfolio_scenario_summary) == 0:
        return pd.DataFrame(
            [
                {
                    "recomputation_count": 0,
                    "slice_count": 0,
                    "scenario_count": 0,
                    "repeated_slice_construction_markers": 0,
                    "repeated_covariance_window_markers": 0,
                    "repeated_aggregation_markers": 0,
                    "timing_p90_ms": 0.0,
                }
            ]
        )
    s = portfolio_scenario_summary.copy()
    slice_repeats = int((s["slice_marker"].value_counts() > 1).sum())
    cov_repeats = int(len(s))  # each run reuses fixed historical window convention
    agg_repeats = int((s["aggregation_label"].value_counts() > 1).sum())
    timing_p90 = _quantile(timing_summary["timing_ms"], 0.90) if timing_summary is not None and len(timing_summary) else 0.0
    return pd.DataFrame(
        [
            {
                "recomputation_count": int(len(s)),
                "slice_count": int(s["slice_id"].nunique()),
                "scenario_count": int(s["scenario_family"].nunique()),
                "repeated_slice_construction_markers": slice_repeats,
                "repeated_covariance_window_markers": cov_repeats,
                "repeated_aggregation_markers": agg_repeats,
                "timing_p90_ms": timing_p90,
            }
        ]
    )


def summarize_risk_reuse_proxies(
    portfolio_scenario_summary: Any,
    *,
    recomputation_patterns: Any,
) -> Any:
    """Build risk-side reuse proxy summary table."""
    import pandas as pd

    if portfolio_scenario_summary is None or len(portfolio_scenario_summary) == 0:
        return pd.DataFrame(
            [
                {
                    "risk_workload_variant_label": RISK_WORKLOAD_SLICE_SCENARIO,
                    "repeated_slice_construction_markers": 0,
                    "repeated_covariance_window_markers": 0,
                    "repeated_aggregation_markers": 0,
                    "reuse_density": 0.0,
                }
            ]
        )
    rp = recomputation_patterns.iloc[0]
    reuse_density = (
        float(rp["repeated_slice_construction_markers"])
        + float(rp["repeated_covariance_window_markers"])
        + float(rp["repeated_aggregation_markers"])
    ) / max(1.0, float(rp["recomputation_count"]))
    return pd.DataFrame(
        [
            {
                "risk_workload_variant_label": RISK_WORKLOAD_SLICE_SCENARIO,
                "repeated_slice_construction_markers": int(rp["repeated_slice_construction_markers"]),
                "repeated_covariance_window_markers": int(rp["repeated_covariance_window_markers"]),
                "repeated_aggregation_markers": int(rp["repeated_aggregation_markers"]),
                "reuse_density": reuse_density,
            }
        ]
    )


def rank_risk_workloads_for_cache_study_value(
    *,
    historical_risk_summary: Any,
    portfolio_slice_summary: Any,
    recomputation_patterns: Any,
) -> Any:
    """Rank broad-vs-slice risk workload families for cache-study value."""
    import pandas as pd

    rows = [
        {
            "risk_workload_variant_label": RISK_WORKLOAD_LARGE_UNIVERSE,
            "n_securities": int(historical_risk_summary["n_securities"].iloc[0]) if len(historical_risk_summary) else 0,
            "recomputation_count": 1,
            "aggregation_width_mean": float(historical_risk_summary["n_securities"].iloc[0]) if len(historical_risk_summary) else 0.0,
            "reuse_proxy": 0.2,
        },
        {
            "risk_workload_variant_label": RISK_WORKLOAD_SLICE_SCENARIO,
            "n_securities": int(_safe_mean(portfolio_slice_summary["n_securities"])) if portfolio_slice_summary is not None and len(portfolio_slice_summary) else 0,
            "recomputation_count": int(recomputation_patterns["recomputation_count"].iloc[0]) if recomputation_patterns is not None and len(recomputation_patterns) else 0,
            "aggregation_width_mean": float(_safe_mean(portfolio_slice_summary["n_securities"])) if portfolio_slice_summary is not None and len(portfolio_slice_summary) else 0.0,
            "reuse_proxy": float(
                (
                    recomputation_patterns["repeated_slice_construction_markers"].iloc[0]
                    + recomputation_patterns["repeated_covariance_window_markers"].iloc[0]
                    + recomputation_patterns["repeated_aggregation_markers"].iloc[0]
                )
                / max(1, recomputation_patterns["recomputation_count"].iloc[0])
            )
            if recomputation_patterns is not None and len(recomputation_patterns)
            else 0.0,
        },
    ]
    df = pd.DataFrame(rows)
    df["cache_study_value_score"] = (
        0.35 * df["recomputation_count"].rank(pct=True)
        + 0.25 * df["aggregation_width_mean"].rank(pct=True)
        + 0.20 * df["n_securities"].rank(pct=True)
        + 0.20 * df["reuse_proxy"].rank(pct=True)
    )
    df["rank"] = df["cache_study_value_score"].rank(method="dense", ascending=False).astype(int)
    return df.sort_values("rank").reset_index(drop=True)


def export_large_universe_risk_outputs(
    *,
    historical_risk_summary: Any,
    historical_var_cvar_summary: Any,
    output_dir: str | Path,
) -> Dict[str, str]:
    """Export large-universe risk outputs (CSV subset)."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    p1 = out / "historical_risk_summary.csv"
    p2 = out / "historical_var_cvar_summary.csv"
    historical_risk_summary.to_csv(p1, index=False)
    historical_var_cvar_summary.to_csv(p2, index=False)
    return {"historical_risk_summary_csv": str(p1), "historical_var_cvar_summary_csv": str(p2)}


def export_portfolio_slice_outputs(
    *,
    portfolio_slice_summary: Any,
    portfolio_scenario_summary: Any,
    output_dir: str | Path,
) -> Dict[str, str]:
    """Export portfolio-slice outputs (CSV subset)."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    p1 = out / "portfolio_slice_summary.csv"
    p2 = out / "portfolio_scenario_summary.csv"
    portfolio_slice_summary.to_csv(p1, index=False)
    portfolio_scenario_summary.to_csv(p2, index=False)
    return {"portfolio_slice_summary_csv": str(p1), "portfolio_scenario_summary_csv": str(p2)}


def run_portfolio_risk_workload_bundle(
    *,
    daily_panel: Any,
    rates_frame: Optional[Any] = None,
    event_tags: Optional[Any] = None,
    confidence_level: float = 0.95,
    panel_key: str = "portfolio_risk_workload",
    n_slices: int = 8,
    slice_size: int = 40,
    mac_row_limit: int = 2_000_000,
    run_id: str = "",
    record_observability: bool = True,
) -> Dict[str, Any]:
    """Build full risk workload bundle: historical base + slice scenario layer."""
    import pandas as pd

    panel_used, deferred_notes = _mac_degrade_daily_panel(
        daily_panel,
        permno_column="permno",
        date_column="date",
        mac_row_limit=mac_row_limit,
    )

    t0 = time.perf_counter()
    panel_bundle = build_historical_risk_panel(
        panel_used,
        rates_frame=rates_frame,
        event_tags=event_tags,
        panel_key=panel_key,
    )
    t_hist = (time.perf_counter() - t0) * 1000.0
    returns_wide = panel_bundle["returns_wide"]
    historical_risk_summary, historical_var_cvar_summary = summarize_large_universe_risk(
        returns_wide,
        confidence_level=confidence_level,
        workload_label=RISK_WORKLOAD_LARGE_UNIVERSE,
    )

    t1 = time.perf_counter()
    slice_family = build_portfolio_slice_family(
        returns_wide,
        family_id=f"{panel_key}::slice_family",
        n_slices=n_slices,
        slice_size=slice_size,
    )
    scenario_summary, scenario_timing = run_portfolio_scenario_recomputation(
        returns_wide=returns_wide,
        slice_family=slice_family,
        confidence_level=confidence_level,
        event_tags=event_tags,
        rates_frame=rates_frame,
    )
    t_slice = (time.perf_counter() - t1) * 1000.0
    slice_summary = summarize_portfolio_slice_risk(
        slice_family=slice_family,
        scenario_summary=scenario_summary,
    )

    cmp_scope = compare_large_universe_vs_portfolio_slice_risk(
        historical_risk_summary=historical_risk_summary,
        portfolio_slice_summary=slice_summary,
    )
    cmp_var_cvar = compare_var_vs_cvar_structures(
        historical_var_cvar_summary=historical_var_cvar_summary,
        portfolio_scenario_summary=scenario_summary,
    )
    scenario_family_cmp = compare_scenario_families(scenario_summary)
    recomputation_patterns = summarize_risk_recomputation_patterns(
        scenario_summary,
        timing_summary=scenario_timing,
    )
    reuse_proxy_summary = summarize_risk_reuse_proxies(
        scenario_summary,
        recomputation_patterns=recomputation_patterns,
    )
    rankings = rank_risk_workloads_for_cache_study_value(
        historical_risk_summary=historical_risk_summary,
        portfolio_slice_summary=slice_summary,
        recomputation_patterns=recomputation_patterns,
    )

    timing_summary = pd.DataFrame(
        [
            {"risk_workload_variant_label": RISK_WORKLOAD_LARGE_UNIVERSE, "timing_ms": t_hist},
            {"risk_workload_variant_label": RISK_WORKLOAD_SLICE_SCENARIO, "timing_ms": t_slice},
            {
                "risk_workload_variant_label": "slice_scenario_inner_recompute",
                "timing_ms": _safe_mean(scenario_timing["timing_ms"]) if scenario_timing is not None and len(scenario_timing) else 0.0,
            },
        ]
    )

    workload_manifest = pd.DataFrame(
        [
            {
                "workload_variant_label": RISK_WORKLOAD_LARGE_UNIVERSE,
                "panel_key": panel_bundle["panel_key"],
                "deterministic_label": panel_bundle["deterministic_label"],
                "n_rows": panel_bundle["n_rows"],
                "n_securities": panel_bundle["n_securities"],
                "n_dates": panel_bundle["n_dates"],
                "scenario_count": 1,
                "slice_count": 0,
                "rates_attached": panel_bundle["rates_attached"],
                "event_tags_attached": panel_bundle["event_tags_attached"],
                "workload_family_label": _workload_family_label(
                    stage="portfolio_risk",
                    n_symbols=panel_bundle["n_securities"],
                    model_phase="large_universe",
                ),
            },
            {
                "workload_variant_label": RISK_WORKLOAD_SLICE_SCENARIO,
                "panel_key": panel_bundle["panel_key"],
                "deterministic_label": panel_bundle["deterministic_label"],
                "n_rows": int(len(scenario_summary)),
                "n_securities": int(_safe_mean(slice_summary["n_securities"])) if len(slice_summary) else 0,
                "n_dates": panel_bundle["n_dates"],
                "scenario_count": int(_safe_nunique(scenario_summary["scenario_family"])) if len(scenario_summary) else 0,
                "slice_count": int(_safe_nunique(slice_summary["slice_id"])) if len(slice_summary) else 0,
                "rates_attached": panel_bundle["rates_attached"],
                "event_tags_attached": panel_bundle["event_tags_attached"],
                "workload_family_label": _workload_family_label(
                    stage="portfolio_risk",
                    n_symbols=int(_safe_mean(slice_summary["n_securities"])) if len(slice_summary) else 0,
                    model_phase="slice_scenario",
                ),
            },
        ]
    )

    if record_observability:
        from qhpc_cache.cache_workload_mapping import record_spine_pipeline_observation
        from qhpc_cache.workload_signatures import WORKLOAD_SPINE_PORTFOLIO_RISK

        record_spine_pipeline_observation(
            run_id=run_id or f"portfolio_risk::{panel_bundle['deterministic_label']}",
            workload_spine_id=WORKLOAD_SPINE_PORTFOLIO_RISK,
            pipeline_phase="portfolio_risk_workloads",
            source_datasets="crsp.dsf;rates;event_tags;feature_panel_outputs",
            row_count_primary=int(len(panel_used) if panel_used is not None else 0),
            row_count_after_join=int(len(returns_wide) * max(1, len(returns_wide.columns))),
            join_width_estimate=int(len(returns_wide.columns)),
            feature_dim_before=int(len(returns_wide.columns)),
            feature_dim_after=int(len(slice_summary)),
            reuse_alignment_opportunities=int(recomputation_patterns["recomputation_count"].iloc[0]) if len(recomputation_patterns) else 0,
            notes=json.dumps({"deferred_hpc_workloads": len(deferred_notes), "scenario_count": int(_safe_nunique(scenario_summary["scenario_family"])) if len(scenario_summary) else 0})[:500],
        )

    return {
        "workload_manifest": workload_manifest,
        "historical_risk_summary": historical_risk_summary,
        "historical_var_cvar_summary": historical_var_cvar_summary,
        "portfolio_slice_manifest": slice_family,
        "portfolio_slice_summary": slice_summary,
        "portfolio_scenario_summary": scenario_summary,
        "portfolio_risk_timing_summary": timing_summary,
        "portfolio_risk_reuse_proxy_summary": reuse_proxy_summary,
        "portfolio_risk_rankings": rankings,
        "comparison_large_vs_slice": cmp_scope,
        "comparison_var_vs_cvar": cmp_var_cvar,
        "comparison_scenario_families": scenario_family_cmp,
        "recomputation_patterns": recomputation_patterns,
        "deferred_hpc_workloads": deferred_notes,
        "metadata": {
            "run_at_utc": _now_iso(),
            "panel_key": panel_bundle["panel_key"],
            "deterministic_label": panel_bundle["deterministic_label"],
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


def export_portfolio_risk_workload_bundle(
    *,
    bundle: Mapping[str, Any],
    output_dir: str | Path,
) -> Dict[str, str]:
    """Export primary CSV/JSON artifacts, then secondary markdown/plots."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Primary CSV outputs
    csv_workload_manifest = out / "portfolio_risk_workload_manifest.csv"
    csv_hist_risk = out / "historical_risk_summary.csv"
    csv_hist_var_cvar = out / "historical_var_cvar_summary.csv"
    csv_slice_summary = out / "portfolio_slice_summary.csv"
    csv_scenario_summary = out / "portfolio_scenario_summary.csv"
    csv_timing = out / "portfolio_risk_timing_summary.csv"
    csv_reuse = out / "portfolio_risk_reuse_proxy_summary.csv"
    csv_rankings = out / "portfolio_risk_rankings.csv"

    bundle["workload_manifest"].to_csv(csv_workload_manifest, index=False)
    bundle["historical_risk_summary"].to_csv(csv_hist_risk, index=False)
    bundle["historical_var_cvar_summary"].to_csv(csv_hist_var_cvar, index=False)
    bundle["portfolio_slice_summary"].to_csv(csv_slice_summary, index=False)
    bundle["portfolio_scenario_summary"].to_csv(csv_scenario_summary, index=False)
    bundle["portfolio_risk_timing_summary"].to_csv(csv_timing, index=False)
    bundle["portfolio_risk_reuse_proxy_summary"].to_csv(csv_reuse, index=False)
    bundle["portfolio_risk_rankings"].to_csv(csv_rankings, index=False)

    # Primary JSON outputs
    json_workload_manifest = out / "portfolio_risk_workload_manifest.json"
    json_slice_manifest = out / "portfolio_slice_manifest.json"
    json_comparison_manifest = out / "portfolio_risk_comparison_manifest.json"

    json_workload_manifest.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "workloads": bundle["workload_manifest"].to_dict(orient="records"),
                "deferred_hpc_workloads": list(bundle.get("deferred_hpc_workloads", [])),
                "metadata": dict(bundle.get("metadata", {})),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    json_slice_manifest.write_text(
        bundle["portfolio_slice_manifest"].to_json(orient="records", indent=2),
        encoding="utf-8",
    )
    json_comparison_manifest.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "large_vs_slice": bundle["comparison_large_vs_slice"].to_dict(orient="records"),
                "var_vs_cvar": bundle["comparison_var_vs_cvar"].to_dict(orient="records"),
                "scenario_family_comparison": bundle["comparison_scenario_families"].to_dict(orient="records"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Secondary markdown outputs
    md_risk = out / "portfolio_risk_summary.md"
    md_scenario = out / "portfolio_scenario_summary.md"
    md_rank = out / "portfolio_risk_rankings_summary.md"

    bullets_risk = [
        (
            f"{r.risk_workload_variant_label}: n_sec={int(r.n_securities)} "
            f"n_dates={int(r.n_dates)} rolling_vol_p90={float(r.rolling_vol_p90):.4f}"
        )
        for r in bundle["historical_risk_summary"].itertuples(index=False)
    ]
    _write_md(md_risk, title="Portfolio Risk Summary", bullets=bullets_risk)
    bullets_scenario = [
        (
            f"{r.scenario_family}: slices={int(r.slice_count)} "
            f"var_mean={float(r.var_mean):.4f} cvar_mean={float(r.cvar_mean):.4f}"
        )
        for r in bundle["comparison_scenario_families"].itertuples(index=False)
    ]
    _write_md(md_scenario, title="Portfolio Scenario Summary", bullets=bullets_scenario)
    bullets_rank = [
        f"rank={int(r.rank)} {r.risk_workload_variant_label}: score={float(r.cache_study_value_score):.4f}"
        for r in bundle["portfolio_risk_rankings"].itertuples(index=False)
    ]
    _write_md(md_rank, title="Portfolio Risk Rankings Summary", bullets=bullets_rank)

    # Secondary plots
    plot_var_cvar = out / "plot_var_cvar_comparison.png"
    plot_large_vs_slice = out / "plot_large_universe_vs_slice_risk_comparison.png"
    plot_scenario = out / "plot_scenario_family_comparison.png"
    plot_timing = out / "plot_risk_timing_comparison.png"
    plot_rank = out / "plot_risk_workload_rankings.png"
    plot_reuse = out / "plot_recomputation_reuse_proxy.png"

    _plot_bar(
        bundle["comparison_var_vs_cvar"],
        x="risk_scope",
        y="cvar_over_var_ratio",
        title="VaR / CVaR Structure Comparison",
        output_path=plot_var_cvar,
    )
    _plot_bar(
        bundle["comparison_large_vs_slice"],
        x="slice_count",
        y="slice_cvar_mean",
        title="Large-Universe vs Slice Risk Comparison",
        output_path=plot_large_vs_slice,
    )
    _plot_bar(
        bundle["comparison_scenario_families"],
        x="scenario_family",
        y="cvar_mean",
        title="Scenario Family Comparison",
        output_path=plot_scenario,
    )
    _plot_bar(
        bundle["portfolio_risk_timing_summary"],
        x="risk_workload_variant_label",
        y="timing_ms",
        title="Risk Timing Comparison",
        output_path=plot_timing,
    )
    _plot_bar(
        bundle["portfolio_risk_rankings"],
        x="risk_workload_variant_label",
        y="cache_study_value_score",
        title="Risk Workload Rankings",
        output_path=plot_rank,
    )
    _plot_bar(
        bundle["portfolio_risk_reuse_proxy_summary"],
        x="risk_workload_variant_label",
        y="reuse_density",
        title="Recomputation / Reuse Proxy",
        output_path=plot_reuse,
    )

    return {
        "portfolio_risk_workload_manifest_csv": str(csv_workload_manifest),
        "historical_risk_summary_csv": str(csv_hist_risk),
        "historical_var_cvar_summary_csv": str(csv_hist_var_cvar),
        "portfolio_slice_summary_csv": str(csv_slice_summary),
        "portfolio_scenario_summary_csv": str(csv_scenario_summary),
        "portfolio_risk_timing_summary_csv": str(csv_timing),
        "portfolio_risk_reuse_proxy_summary_csv": str(csv_reuse),
        "portfolio_risk_rankings_csv": str(csv_rankings),
        "portfolio_risk_workload_manifest_json": str(json_workload_manifest),
        "portfolio_slice_manifest_json": str(json_slice_manifest),
        "portfolio_risk_comparison_manifest_json": str(json_comparison_manifest),
        "portfolio_risk_summary_md": str(md_risk),
        "portfolio_scenario_summary_md": str(md_scenario),
        "portfolio_risk_rankings_summary_md": str(md_rank),
        "plot_var_cvar_comparison": str(plot_var_cvar),
        "plot_large_universe_vs_slice_risk_comparison": str(plot_large_vs_slice),
        "plot_scenario_family_comparison": str(plot_scenario),
        "plot_risk_timing_comparison": str(plot_timing),
        "plot_risk_workload_rankings": str(plot_rank),
        "plot_recomputation_reuse_proxy": str(plot_reuse),
    }
